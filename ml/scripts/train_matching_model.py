"""
FoodBridge - NGO Matching Model + SHAP Explainability
Trains a gradient-boosted classifier to predict match success
(Historical_Match_Training) and fits a SHAP TreeExplainer so every
live match decision can be explained feature-by-feature, matching
the "plain English reason" shown to NGOs/donors in the product.

Input : ml/data/FoodBridge_XAI_Large_Datasets.xlsx  (Historical_Match_Training)
Output: ml/models/matching_model.joblib (dict: model, explainer, encoders, feature_names, metrics)
"""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support, accuracy_score
from sklearn.preprocessing import LabelEncoder
import shap

DATA = Path(__file__).resolve().parents[1] / "data" / "FoodBridge_XAI_Large_Datasets.xlsx"
OUT = Path(__file__).resolve().parents[1] / "models" / "matching_model.joblib"


def main():
    xl = pd.ExcelFile(DATA)
    hist = xl.parse("Historical_Match_Training")

    df = hist.copy()
    day_enc, month_enc = LabelEncoder(), LabelEncoder()
    df["day_of_week_enc"] = day_enc.fit_transform(df["day_of_week"].astype(str))
    df["month_enc"] = month_enc.fit_transform(df["month"].astype(str))
    df["has_cold_storage"] = df["has_cold_storage"].astype(int)
    df["is_festival_day"] = df["is_festival_day"].astype(int)

    feature_cols = [
        "distance_km", "capacity_available_plates", "food_type_match_score",
        "sentiment_score", "time_overlap_minutes", "occupancy_%",
        "donor_trust_score", "food_safety_score_%", "quantity_plates",
        "has_cold_storage", "ngo_tier_encoded", "hour_of_day",
        "day_of_week_enc", "month_enc", "is_festival_day", "weather_score",
    ]
    X = df[feature_cols].fillna(df[feature_cols].median())
    y = df["was_successful"].astype(int).values

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
        random_state=42, n_jobs=-1,
    )
    model.fit(Xtr, ytr)

    proba = model.predict_proba(Xte)[:, 1]
    pred = (proba >= 0.5).astype(int)
    auc = roc_auc_score(yte, proba)
    acc = accuracy_score(yte, pred)
    prec, rec, f1, _ = precision_recall_fscore_support(yte, pred, average="binary", zero_division=0)

    print("=== NGO Matching Model (XGBoost) ===")
    print(f"Accuracy: {acc:.4f}  ROC-AUC: {auc:.4f}  Precision: {prec:.4f}  Recall: {rec:.4f}  F1: {f1:.4f}")

    explainer = shap.TreeExplainer(model)
    shap_values_sample = explainer.shap_values(Xte.iloc[:50])
    mean_abs_shap = dict(zip(feature_cols, np.abs(shap_values_sample).mean(axis=0).tolist()))
    top_global = dict(sorted(mean_abs_shap.items(), key=lambda kv: -kv[1])[:8])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": model,
        "explainer": explainer,
        "day_enc": day_enc,
        "month_enc": month_enc,
        "feature_names": feature_cols,
        "metrics": {
            "accuracy": acc, "roc_auc": auc, "precision": prec, "recall": rec, "f1": f1,
            "global_shap_importance": top_global, "n_train": len(ytr), "n_test": len(yte),
        },
    }, OUT)
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
