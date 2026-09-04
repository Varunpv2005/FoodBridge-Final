"""Demand forecasting runtime and the small LSTM used by the offline trainer."""
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np


MODEL_PATH = Path(__file__).resolve().parents[3] / "ml" / "models" / "demand_forecast_model.joblib"
FEATURE_NAMES = [
    "lag_1", "lag_7", "lag_14", "lag_28",
    "rolling_mean_7", "rolling_mean_14", "rolling_mean_28",
    "day_of_week", "month",
]


class NumpyLSTM:
    """A compact single-feature LSTM for offline, reproducible forecasting."""

    def __init__(self, input_size: int = 1, hidden_size: int = 16, seed: int = 42):
        self.input_size = input_size
        self.hidden_size = hidden_size
        rng = np.random.default_rng(seed)
        scale = 1 / np.sqrt(input_size + hidden_size)
        self.W = rng.normal(0, scale, (input_size + hidden_size, hidden_size * 4))
        self.b = np.zeros(hidden_size * 4)
        self.Wy = rng.normal(0, scale, (hidden_size, 1))
        self.by = np.zeros(1)

    @staticmethod
    def _sigmoid(values):
        return 1 / (1 + np.exp(-np.clip(values, -30, 30)))

    def forward(self, sequence, cache=False):
        hidden = np.zeros(self.hidden_size)
        cell = np.zeros(self.hidden_size)
        states = []
        for value in sequence:
            gates = self.W.T @ np.concatenate(([float(value)], hidden)) + self.b
            input_gate, forget_gate, output_gate, candidate = np.split(gates, 4)
            input_gate = self._sigmoid(input_gate)
            forget_gate = self._sigmoid(forget_gate)
            output_gate = self._sigmoid(output_gate)
            candidate = np.tanh(candidate)
            cell = forget_gate * cell + input_gate * candidate
            hidden = output_gate * np.tanh(cell)
            if cache:
                states.append((hidden.copy(), cell.copy(), input_gate, forget_gate, output_gate, candidate))
        prediction = float((hidden @ self.Wy + self.by)[0])
        return (prediction, states) if cache else prediction

    def predict(self, sequences):
        return np.asarray([self.forward(sequence) for sequence in sequences], dtype=float)

    def fit(self, sequences, targets, epochs=120, learning_rate=0.01):
        for _ in range(epochs):
            for sequence, target in zip(sequences, targets):
                prediction, states = self.forward(sequence, cache=True)
                error = prediction - float(target)
                grad_wy = states[-1][0][:, None] * error
                grad_by = np.array([error])
                grad_w = np.zeros_like(self.W)
                grad_b = np.zeros_like(self.b)
                grad_hidden = self.Wy[:, 0] * error
                grad_cell = np.zeros(self.hidden_size)
                next_hidden = np.zeros(self.hidden_size)
                next_cell = np.zeros(self.hidden_size)

                for index in range(len(sequence) - 1, -1, -1):
                    hidden, cell, input_gate, forget_gate, output_gate, candidate = states[index]
                    previous_cell = states[index - 1][1] if index else np.zeros(self.hidden_size)
                    previous_hidden = states[index - 1][0] if index else np.zeros(self.hidden_size)
                    tanh_cell = np.tanh(cell)
                    grad_output = grad_hidden * tanh_cell * output_gate * (1 - output_gate)
                    grad_cell_total = grad_cell + grad_hidden * output_gate * (1 - tanh_cell ** 2)
                    grad_input = grad_cell_total * candidate * input_gate * (1 - input_gate)
                    grad_forget = grad_cell_total * previous_cell * forget_gate * (1 - forget_gate)
                    grad_candidate = grad_cell_total * input_gate * (1 - candidate ** 2)
                    grad_cell = grad_cell_total * forget_gate
                    gate_gradient = np.concatenate((grad_input, grad_forget, grad_output, grad_candidate))
                    gate_input = np.concatenate(([float(sequence[index])], previous_hidden))
                    grad_w += np.outer(gate_input, gate_gradient)
                    grad_b += gate_gradient
                    grad_hidden = self.W[:self.input_size, :] @ gate_gradient
                    grad_hidden = np.zeros(self.hidden_size) + self.W[self.input_size:, :] @ gate_gradient
                    next_hidden, next_cell = previous_hidden, previous_cell

                self.Wy -= learning_rate * np.clip(grad_wy, -5, 5)
                self.by -= learning_rate * np.clip(grad_by, -5, 5)
                self.W -= learning_rate * np.clip(grad_w, -5, 5)
                self.b -= learning_rate * np.clip(grad_b, -5, 5)
        return self

    def state(self):
        return {
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "W": self.W,
            "b": self.b,
            "Wy": self.Wy,
            "by": self.by,
        }

    @classmethod
    def from_state(cls, state):
        model = cls(state["input_size"], state["hidden_size"])
        for key in ("W", "b", "Wy", "by"):
            setattr(model, key, state[key])
        return model


def build_feature_row(series: np.ndarray, target_date: date) -> np.ndarray:
    """Build features using observations strictly before target_date."""
    return np.asarray([
        series[-1], series[-7], series[-14], series[-28],
        series[-7:].mean(), series[-14:].mean(), series[-28:].mean(),
        target_date.weekday(), target_date.month,
    ], dtype=float)


def make_sequences(values: np.ndarray, sequence_length: int):
    sequences = []
    targets = []
    for index in range(sequence_length, len(values)):
        sequences.append(values[index - sequence_length:index])
        targets.append(values[index])
    return np.asarray(sequences, dtype=float), np.asarray(targets, dtype=float)


def mean_absolute_error(actual, predicted):
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(predicted))))


def root_mean_squared_error(actual, predicted):
    return float(np.sqrt(np.mean((np.asarray(actual) - np.asarray(predicted)) ** 2)))


@lru_cache(maxsize=1)
def load_forecast_model():
    artifact = joblib.load(MODEL_PATH)
    artifact["lstm"] = NumpyLSTM.from_state(artifact["lstm_state"])
    return artifact


def _next_xgb_prediction(model, history, target_date):
    row = build_feature_row(np.asarray(history, dtype=float), target_date)
    return float(model.predict(row.reshape(1, -1))[0])


def forecast_demand(horizon: int = 7, region: Optional[str] = None, food_type: Optional[str] = None) -> Dict[str, Any]:
    if region or food_type:
        raise ValueError("This trained forecast currently supports the aggregate series only (all regions and food types).")
    artifact = load_forecast_model()
    horizon = max(1, min(int(horizon), 14))
    history = list(artifact["history"])
    last_date = date.fromisoformat(artifact["last_date"])
    lstm = artifact["lstm"]
    scale = artifact["lstm_scale"]
    sequence_length = artifact["sequence_length"]
    forecasts: List[Dict[str, Any]] = []

    for step in range(1, horizon + 1):
        target_date = last_date + timedelta(days=step)
        xgb_prediction = _next_xgb_prediction(artifact["xgb"], history, target_date)
        scaled_history = (np.asarray(history) - scale["mean"]) / scale["std"]
        lstm_scaled = lstm.forward(scaled_history[-sequence_length:])
        lstm_prediction = float(lstm_scaled * scale["std"] + scale["mean"])
        ensemble_prediction = max(0.0, float(
            artifact["weights"]["xgboost"] * xgb_prediction
            + artifact["weights"]["lstm"] * lstm_prediction
        ))
        history.append(ensemble_prediction)
        forecasts.append({
            "forecast_date": target_date.isoformat(),
            "predicted_demand": round(ensemble_prediction, 2),
            "xgboost_prediction": round(max(0.0, xgb_prediction), 2),
            "lstm_prediction": round(max(0.0, lstm_prediction), 2),
        })

    return {
        "region": "All regions",
        "food_type": "All food types",
        "model_weights": artifact["weights"],
        "forecasts": forecasts,
        "metrics": artifact["metrics"],
        "data_source": artifact["data_source"],
        "sequence_length": sequence_length,
    }


def get_aggregate_demand_signal() -> Optional[Dict[str, float]]:
    """Return aggregate demand pressure without implying NGO-specific demand."""
    try:
        artifact = load_forecast_model()
        baseline = float(np.mean(artifact["history"]))
        if baseline <= 0:
            return None
        predicted = float(forecast_demand(horizon=1)["forecasts"][0]["predicted_demand"])
        return {
            "predicted_plates": predicted,
            "baseline_plates": baseline,
            "pressure_ratio": predicted / baseline,
        }
    except (FileNotFoundError, KeyError, ValueError):
        return None