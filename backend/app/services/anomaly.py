"""
Wraps the trained Isolation Forest + Random Forest anomaly ensemble and
adds a live SHAP TreeExplainer over the Random Forest so every flagged
donation gets a genuine per-instance explanation — this is what lets the
system surface *unknown* fraud patterns (via the unsupervised Isolation
Forest score as an input feature) while still explaining *why* in
human terms (via SHAP on the supervised head).
"""
from functools import lru_cache

import numpy as np
import pandas as pd
import shap

from app.utils.model_loader import load_anomaly


@lru_cache(maxsize=1)
def _get_explainer():
    bundle = load_anomaly()
    return shap.TreeExplainer(bundle["rf"])


def score_donor_pattern(donor_features: dict) -> dict:
    """
    donor_features must contain all keys in bundle['feature_names']
    (see routers/anomaly.py _FIELD_MAP for the canonical mapping from a
    donor's rolling behavioural stats to these model features).
    """
    bundle = load_anomaly()
    iso, rf, scaler = bundle["iso_forest"], bundle["rf"], bundle["scaler"]
    feature_cols = bundle["feature_names"]

    X = pd.DataFrame([donor_features])[feature_cols]
    Xs = scaler.transform(X)

    iso_raw = -iso.score_samples(Xs)[0]
    iso_pred = iso.predict(Xs)[0]
    Xs_aug = np.hstack([Xs, [[iso_raw]]])

    proba = float(rf.predict_proba(Xs_aug)[0, 1])

    explainer = _get_explainer()
    shap_values = explainer.shap_values(Xs_aug)
    # Newer shap versions return a single ndarray shaped
    # (n_samples, n_features, n_classes); older versions return a
    # list [class0_array, class1_array]. Handle both.
    if isinstance(shap_values, list):
        sv = shap_values[1][0]
    else:
        arr = np.asarray(shap_values)
        sv = arr[0, :, 1] if arr.ndim == 3 else arr[0]
    shap_map = {feat: round(float(v), 4) for feat, v in zip(feature_cols + ["iso_forest_score"], sv)}
    top_shap = dict(sorted(shap_map.items(), key=lambda kv: -abs(kv[1]))[:6])

    is_anomaly = proba >= 0.5
    novel_pattern = bool(iso_pred == -1 and proba < 0.5)  # iso flags it, supervised head doesn't -> unseen pattern

    return {
        "is_anomaly": is_anomaly,
        "anomaly_probability": round(proba, 4),
        "isolation_forest_score": round(float(iso_raw), 4),
        "novel_unseen_pattern": novel_pattern,
        "shap_explanation": top_shap,
    }
