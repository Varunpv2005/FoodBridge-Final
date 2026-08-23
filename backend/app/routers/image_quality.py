import io
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image
from app.schemas import ImageQualityResponse
from app.utils.model_loader import load_image_quality

router = APIRouter()


def extract_features(arr: np.ndarray) -> np.ndarray:
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


@router.post("/predict", response_model=ImageQualityResponse)
async def predict_image_quality(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file (jpg/png).")

    bundle = load_image_quality()
    mlp, scaler, img_size = bundle["mlp"], bundle["scaler"], bundle["img_size"]

    raw = await file.read()
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB").resize((img_size, img_size))
    except Exception:
        raise HTTPException(400, "Could not read image file.")

    arr = np.array(img)
    feats = extract_features(arr).reshape(1, -1)
    feats_s = scaler.transform(feats)

    proba = mlp.predict_proba(feats_s)[0]
    pred = int(np.argmax(proba))  # 1 = fresh/safe, 0 = spoiled
    label = "Safe to donate" if pred == 1 else "Do not donate - spoilage risk"
    confidence = float(proba[pred])

    rec = ("Approved for pickup and NGO matching." if pred == 1
           else "Donation blocked. Donor notified to re-check food condition.")

    return ImageQualityResponse(label=label, confidence=round(confidence, 4), recommendation=rec)
