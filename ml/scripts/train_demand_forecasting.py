"""Train and evaluate FoodBridge demand forecasts from dated donation requests.

The source contains request quantities rather than confirmed NGO demand, so
the target is daily requested plates aggregated across all zones and foods.
This script uses chronological train/validation/test splits and saves the
trained XGBoost model, NumPy LSTM weights, ensemble weights, and metrics.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.demand_forecasting import (  # noqa: E402
    FEATURE_NAMES,
    NumpyLSTM,
    build_feature_row,
    make_sequences,
    mean_absolute_error,
    root_mean_squared_error,
)


DATA_PATH = ROOT / "ml" / "data" / "FoodBridge_XAI_Large_Datasets.xlsx"
OUT_PATH = ROOT / "ml" / "models" / "demand_forecast_model.joblib"
SEQUENCE_LENGTH = 14


def load_daily_history():
    requests = pd.read_excel(DATA_PATH, sheet_name="Donation_Requests")
    requests["available_from"] = pd.to_datetime(requests["available_from"], errors="coerce")
    requests = requests.dropna(subset=["available_from", "quantity_plates"])
    requests["date"] = requests["available_from"].dt.normalize()
    daily = requests.groupby("date")["quantity_plates"].sum()
    calendar = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(calendar, fill_value=0.0)
    return calendar, daily.to_numpy(dtype=float)


def build_xgb_dataset(calendar, values):
    rows, targets, dates = [], [], []
    for index in range(28, len(values)):
        rows.append(build_feature_row(values[:index], calendar[index].date()))
        targets.append(values[index])
        dates.append(calendar[index].date())
    return np.asarray(rows), np.asarray(targets), dates


def split_metrics(actual, predicted):
    return {
        "mae": round(mean_absolute_error(actual, predicted), 4),
        "rmse": round(root_mean_squared_error(actual, predicted), 4),
    }


def main():
    calendar, values = load_daily_history()
    if len(values) < 120:
        raise RuntimeError("At least 120 daily observations are required for a meaningful forecast experiment.")

    train_end = int(len(values) * 0.70)
    validation_end = int(len(values) * 0.85)
    xgb_x, xgb_y, xgb_dates = build_xgb_dataset(calendar, values)
    xgb_train = np.asarray([d < calendar[train_end].date() for d in xgb_dates])
    xgb_validation = np.asarray([
        calendar[train_end].date() <= d < calendar[validation_end].date() for d in xgb_dates
    ])
    xgb_test = np.asarray([d >= calendar[validation_end].date() for d in xgb_dates])

    xgb = XGBRegressor(
        objective="reg:squarederror", n_estimators=300, max_depth=4,
        learning_rate=0.03, subsample=0.85, colsample_bytree=0.9,
        random_state=42, n_jobs=1,
    )
    xgb.fit(xgb_x[xgb_train], xgb_y[xgb_train])
    xgb_validation_pred = xgb.predict(xgb_x[xgb_validation])
    xgb_test_pred = xgb.predict(xgb_x[xgb_test])

    train_values = values[:train_end]
    scale_mean = float(train_values.mean())
    scale_std = float(train_values.std() or 1.0)
    scaled_values = (values - scale_mean) / scale_std
    train_sequences, train_targets = make_sequences(scaled_values[:train_end], SEQUENCE_LENGTH)
    if len(train_sequences) < 50:
        raise RuntimeError("Not enough chronological sequences for LSTM training.")
    lstm = NumpyLSTM(hidden_size=16, seed=42)
    lstm.fit(train_sequences, train_targets, epochs=120, learning_rate=0.005)

    all_sequences, all_targets = make_sequences(scaled_values, SEQUENCE_LENGTH)
    sequence_target_indices = np.arange(SEQUENCE_LENGTH, len(values))
    validation_seq = (sequence_target_indices >= train_end) & (sequence_target_indices < validation_end)
    test_seq = sequence_target_indices >= validation_end
    lstm_validation_pred = lstm.predict(all_sequences[validation_seq]) * scale_std + scale_mean
    lstm_test_pred = lstm.predict(all_sequences[test_seq]) * scale_std + scale_mean
    lstm_validation_actual = values[sequence_target_indices[validation_seq]]
    lstm_test_actual = values[sequence_target_indices[test_seq]]

    # Select the validation-optimal convex weight, then freeze it for the test.
    validation_actual = xgb_y[xgb_validation]
    weights = np.linspace(0.0, 1.0, 21)
    best_xgb_weight = min(
        weights,
        key=lambda weight: root_mean_squared_error(
            validation_actual,
            weight * xgb_validation_pred + (1 - weight) * lstm_validation_pred,
        ),
    )
    best_lstm_weight = 1 - best_xgb_weight
    ensemble_test_pred = best_xgb_weight * xgb_test_pred + best_lstm_weight * lstm_test_pred

    metrics = {
        "xgboost": split_metrics(xgb_y[xgb_test], xgb_test_pred),
        "lstm": split_metrics(lstm_test_actual, lstm_test_pred),
        "ensemble": split_metrics(xgb_y[xgb_test], ensemble_test_pred),
        "validation": {
            "xgboost": split_metrics(validation_actual, xgb_validation_pred),
            "lstm": split_metrics(lstm_validation_actual, lstm_validation_pred),
            "ensemble": split_metrics(
                validation_actual,
                best_xgb_weight * xgb_validation_pred + best_lstm_weight * lstm_validation_pred,
            ),
        },
    }
    artifact = {
        "xgb": xgb,
        "lstm_state": lstm.state(),
        "weights": {"xgboost": round(float(best_xgb_weight), 2), "lstm": round(float(best_lstm_weight), 2)},
        "history": values.tolist(),
        "last_date": calendar[-1].date().isoformat(),
        "lstm_scale": {"mean": scale_mean, "std": scale_std},
        "sequence_length": SEQUENCE_LENGTH,
        "metrics": metrics,
        "features": FEATURE_NAMES,
        "data_source": "ml/data/FoodBridge_XAI_Large_Datasets.xlsx: Donation_Requests",
        "target": "daily sum of quantity_plates across all zones and food types",
        "date_range": [calendar[0].date().isoformat(), calendar[-1].date().isoformat()],
        "observations": int(len(values)),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, OUT_PATH)
    print(f"Source: {artifact['data_source']}")
    print(f"Daily observations: {len(values)} ({calendar[0].date()} to {calendar[-1].date()})")
    print(f"Features: {', '.join(FEATURE_NAMES)}")
    print(f"Weights: XGBoost={best_xgb_weight:.2f}, LSTM={best_lstm_weight:.2f}")
    print(f"Validation metrics: {metrics['validation']}")
    print(f"Test metrics: {metrics['xgboost']=}, {metrics['lstm']=}, {metrics['ensemble']=}")
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()