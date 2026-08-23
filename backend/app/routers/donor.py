import os
import uuid
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import require_role, get_current_user
from app.models_db import User, Donation, DonationStatus, Feedback
from app.schemas_v2 import DonationOut, FeedbackCreate, FeedbackOut
from app.services.quality import classify_image_bytes, predict_degradation
from app.services.behavior import build_anomaly_features
from app.services.anomaly import score_donor_pattern
from app.services.assignment import assign_ngo
from app.services.routing import assign_volunteer
from app.services.ws_manager import manager

router = APIRouter()
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/donations", response_model=DonationOut)
async def create_donation(
    food_type: str = Form(...),
    quantity_plates: int = Form(...),
    pickup_lat: float = Form(...),
    pickup_lng: float = Form(...),
    pickup_address: str = Form(""),
    hours_since_cooked: float = Form(0.5),
    ambient_temp_c: float = Form(30.0),
    has_cold_storage: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    donor: User = Depends(require_role("donor")),
):
    raw = await file.read()
    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    fname = f"{uuid.uuid4()}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(raw)

    donation = Donation(
        donor_id=donor.id, food_type=food_type, quantity_plates=quantity_plates,
        image_path=fname, pickup_lat=pickup_lat, pickup_lng=pickup_lng,
        pickup_address=pickup_address,
        cooked_at=datetime.utcnow() - timedelta(hours=hours_since_cooked),
    )

    # 1. CNN-style image quality check
    quality = classify_image_bytes(raw)
    donation.quality_label = quality["label"]
    donation.quality_confidence = quality["confidence"]

    if not quality["is_fresh"]:
        donation.status = DonationStatus.rejected_quality
        db.add(donation)
        db.commit()
        db.refresh(donation)
        return donation

    # 2. Degradation timeline
    degradation = predict_degradation(
        food_type, quality["freshness_score"], hours_since_cooked, ambient_temp_c, has_cold_storage,
    )
    donation.degradation_hours = degradation["hours_remaining"]
    donation.spoil_by = degradation["spoil_by"]

    # 3. Anomaly / unknown-pattern check on the donor's behavioural history
    anomaly_features = build_anomaly_features(db, donor, quantity_plates, has_expiry=True)
    anomaly_result = score_donor_pattern(anomaly_features)
    donation.anomaly_flag = anomaly_result["is_anomaly"]
    donation.anomaly_probability = anomaly_result["anomaly_probability"]
    donation.anomaly_shap = anomaly_result["shap_explanation"]

    if anomaly_result["is_anomaly"]:
        donation.status = DonationStatus.flagged_anomaly
        db.add(donation)
        db.commit()
        db.refresh(donation)
        await manager.broadcast("admin", {"type": "anomaly_flagged", "donation_id": donation.id})
        return donation

    # 4. NGO assignment (multi-criteria weighted matching + SHAP + degradation feasibility)
    # Persist now so donation.id exists -- assign_volunteer() below needs a real id
    # to create delivery_stops rows (this was previously missing and caused a
    # NOT NULL constraint failure on delivery_stops.donation_id for every
    # successfully-matched donation).
    db.add(donation)
    db.flush()

    ngos = db.query(User).filter(User.role == "ngo").all()
    match = assign_ngo(donation, ngos)
    if not match:
        donation.status = DonationStatus.pending_match
        db.add(donation)
        db.commit()
        db.refresh(donation)
        return donation

    ngo = db.query(User).filter(User.id == match["ngo_id"]).first()
    donation.matched_ngo_id = ngo.id
    donation.match_probability = match["probability"]
    donation.match_shap = match["shap"]
    donation.match_reason = match["reason"]
    donation.status = DonationStatus.matched
    ngo.ngo_capacity_available = max(0, ngo.ngo_capacity_available - quantity_plates)
    db.add(ngo)

    # 5. Volunteer assignment + multi-stop routing
    try:
        delivery = assign_volunteer(db, donation, ngo)
        donation.status = DonationStatus.assigned_volunteer
        db.add(donation)
        db.commit()
        db.refresh(donation)
        await manager.broadcast("admin", {"type": "donation_assigned", "donation_id": donation.id,
                                           "delivery_id": delivery.id})
    except ValueError:
        db.add(donation)
        db.commit()
        db.refresh(donation)

    return donation


@router.get("/donations", response_model=List[DonationOut])
def list_my_donations(db: Session = Depends(get_db), donor: User = Depends(require_role("donor"))):
    return (db.query(Donation).filter(Donation.donor_id == donor.id)
            .order_by(Donation.created_at.desc()).all())


@router.get("/donations/{donation_id}", response_model=DonationOut)
def get_donation(donation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(404, "Donation not found.")
    return donation



