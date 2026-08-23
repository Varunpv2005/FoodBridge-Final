"""
FoodBridge - Anomaly Detection Model Training
Combines unsupervised Isolation Forest with a supervised Random Forest
(trained against analyst-reviewed labels) into one calibrated ensemble,
so the deployed model both (a) generalizes to unseen fraud patterns and
(b) is accurate against the labels your ops team already trusts.

Input : ml/data/donation_anomaly_dataset_501_1000.xlsx
Output: ml/models/anomaly_model.joblib  (dict: iso_forest, rf, scaler, feature_names, metrics)
"""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_recall_fscore_support,
    confusion_matrix
)

DATA = Path(__file__).resolve().parents[1] / "data" / "donation_anomaly_dataset_501_1000.xlsx"
OUT = Path(__file__).resolve().parents[1] / "models" / "anomaly_model.joblib"

def build_feature_table():
    xl = pd.ExcelFile(DATA)
    logs = xl.parse("Donation Logs 501-1000")
    donors = xl.parse("Donor Profiles")
    labels = xl.parse("Anomaly Labels")
    temporal = xl.parse("Temporal Features")
    geo = xl.parse("Geolocation")
    pickup = xl.parse("Volunteer Pickup")

    df = (logs.merge(donors, on=["Record No", "Donor Id"])
              .merge(temporal, on=["Record No", "Donation Id"])
              .merge(geo, on=["Record No", "Donation Id"], suffixes=("", "_geo"))
              .merge(pickup, on=["Record No", "Donation Id"])
              .merge(labels[["Record No", "Is Anomaly", "Anomaly Type"]], on="Record No"))

    df["has_expiry"] = df["Expiry Time"].notna().astype(int)
    df["is_expired_or_flagged"] = df["Pickup Status"].isin(["expired", "flagged"]).astype(int)

    feature_cols = [
        "Quantity Plates", "Session Duration Sec", "Account Age Days",
        "Donations Per Week", "Avg Quantity Plates", "Std Quantity",
        "Hour Std Dev", "Location Variance M", "Expiry Fill Rate",
        "Pickup Rate", "Inter Donation Gap Min", "Unique Devices Used",
        "Unique Ip Count", "Hour Of Day", "Day Of Week",
        "Donations Last 1Hr", "Donations Last 3Hr", "Donations Last 24Hr",
        "Time Since Last Donation Min", "Rolling Avg 7Day", "Deviation From Avg",
        "Distance From Centroid M", "Gps Accuracy M", "Location Count 24Hr",
        "Volunteer Views", "Pickup Attempts", "has_expiry", "is_expired_or_flagged",
    ]
    bool_cols = ["Is Weekend", "Is Night Submission", "Is Same Location Repeated",
                 "Is Residential Area", "Successful Pickup", "Expiry Before Pickup"]
    for c in bool_cols:
        df[c] = df[c].astype(int)
    feature_cols += bool_cols

    X = df[feature_cols].fillna(df[feature_cols].median())
    y = df["Is Anomaly"].values
    return X, y, feature_cols, df


def main():
    X, y, feature_cols, df = build_feature_table()
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    contamination = float(np.clip(y.mean(), 0.01, 0.5))
    iso = IsolationForest(
        n_estimators=300, contamination=contamination,
        random_state=42, n_jobs=-1
    )
    iso.fit(Xs)
    iso_raw = -iso.score_samples(Xs)  # higher = more anomalous
    iso_norm = (iso_raw - iso_raw.min()) / (iso_raw.max() - iso_raw.min())

    Xtr, Xte, ytr, yte, iso_tr, iso_te = train_test_split(
        Xs, y, iso_norm, test_size=0.25, random_state=42, stratify=y
    )
    Xtr_aug = np.hstack([Xtr, iso_tr.reshape(-1, 1)])
    Xte_aug = np.hstack([Xte, iso_te.reshape(-1, 1)])

    rf = RandomForestClassifier(
        n_estimators=400, max_depth=8, class_weight="balanced_subsample",
        random_state=42, n_jobs=-1
    )
    rf.fit(Xtr_aug, ytr)

    proba = rf.predict_proba(Xte_aug)[:, 1]
    pred = (proba >= 0.5).astype(int)
    auc = roc_auc_score(yte, proba)
    prec, rec, f1, _ = precision_recall_fscore_support(yte, pred, average="binary", zero_division=0)
    cm = confusion_matrix(yte, pred).tolist()
    report = classification_report(yte, pred, target_names=["normal", "anomaly"], zero_division=0)

    print("=== Anomaly Detection Model ===")
    print(f"ROC-AUC: {auc:.4f}  Precision: {prec:.4f}  Recall: {rec:.4f}  F1: {f1:.4f}")
    print("Confusion matrix:", cm)
    print(report)

    importances = dict(zip(feature_cols + ["iso_forest_score"], rf.feature_importances_.tolist()))
    top_features = dict(sorted(importances.items(), key=lambda kv: -kv[1])[:10])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "iso_forest": iso,
        "rf": rf,
        "scaler": scaler,
        "feature_names": feature_cols,
        "metrics": {
            "roc_auc": auc, "precision": prec, "recall": rec, "f1": f1,
            "confusion_matrix": cm, "n_train": len(ytr), "n_test": len(yte),
            "top_features": top_features,
        },
    }, OUT)
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
