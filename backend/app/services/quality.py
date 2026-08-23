import io
from datetime import datetime, timedelta

import numpy as np
from PIL import Image

from app.utils.model_loader import load_image_quality, load_degradation


def _extract_image_features(arr: np.ndarray) -> np.ndarray:
    r, g, b = arr[..., 0].astype(float), arr[..., 1].astype(float), arr[..., 2].astype(float)
    feats = []
    for ch in (r, g, b):
        hist, _ = np.histogram(ch, bins=8, range=(0, 255), density=True)
        feats.extend(hist.tolist())
        feats.append(ch.mean())
        feats.append(ch.std())
    gray = arr.mean(axis=2)
    gx = np.abs(np.diff(gray, axis=0)).mean()
    gy = np.abs(np.diff(gray, axis=1)).mean()
    feats.extend([gx, gy, gray.std()])
    dark_ratio = (gray < 60).mean()
    feats.append(dark_ratio)
    return np.array(feats, dtype=np.float32)


def classify_image_bytes(raw: bytes):
    bundle = load_image_quality()
    mlp, scaler, img_size = bundle["mlp"], bundle["scaler"], bundle["img_size"]

    img = Image.open(io.BytesIO(raw)).convert("RGB").resize((img_size, img_size))
    arr = np.array(img)
    feats = _extract_image_features(arr).reshape(1, -1)
    proba = mlp.predict_proba(scaler.transform(feats))[0]
    pred = int(np.argmax(proba))  # 1 = fresh, 0 = spoiled
    return {
        "label": "Safe to donate" if pred == 1 else "Do not donate - spoilage risk",
        "is_fresh": bool(pred == 1),
        "confidence": float(proba[pred]),
        "freshness_score": float(proba[1]),  # P(fresh), used as degradation model input
    }


def predict_degradation(food_type: str, freshness_score: float, hours_since_cooked: float,
                          ambient_temp_c: float, has_cold_storage: bool):
    bundle = load_degradation()
    model, scaler, food_types = bundle["model"], bundle["scaler"], bundle["food_types"]
    if food_type not in food_types:
        food_type = "mixed"
    food_idx = food_types.index(food_type)

    X = np.array([[food_idx, freshness_score, hours_since_cooked, ambient_temp_c, int(has_cold_storage)]])
    hours_remaining = float(model.predict(scaler.transform(X))[0])
    hours_remaining = max(0.0, hours_remaining)

    now = datetime.utcnow()
    spoil_by = now + timedelta(hours=hours_remaining)

    if hours_remaining < 1:
        urgency = "critical"
    elif hours_remaining < 3:
        urgency = "high"
    elif hours_remaining < 6:
        urgency = "moderate"
    else:
        urgency = "low"

    return {
        "hours_remaining": round(hours_remaining, 2),
        "spoil_by": spoil_by,
        "urgency": urgency,
    }
