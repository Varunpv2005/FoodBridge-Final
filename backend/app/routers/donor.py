import os
import uuid
import time
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import require_role, get_current_user
from app.models_db import User, Donation, DonationStatus, Feedback, DeliveryStop, Delivery
from app.schemas_v2 import DonationOut, FeedbackCreate, FeedbackOut
from app.services.quality import classify_image_bytes, predict_degradation
from app.services.risk import estimate_risk
from app.services.behavior import build_anomaly_features
from app.services.anomaly import score_donor_pattern
from app.services.ws_manager import manager
from app.services.delivery_view import add_delivery_state
from app.services.ngo_requests import create_request_queue
from app.services.evaluation import ensure_experiment, sync_experiment

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
    evaluation_trial: bool = Form(False),
    db: Session = Depends(get_db),
    donor: User = Depends(require_role("donor")),
):
    request_started = time.perf_counter()
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

    risk = estimate_risk(
        food_type, hours_since_cooked, ambient_temp_c, has_cold_storage,
        freshness_score=quality["freshness_score"], quantity_plates=quantity_plates,
    )
    donation.risk_score = risk["risk_score"]
    donation.risk_level = risk["risk_level"]
    donation.risk_reasons = risk["reasons"]
    donation.risk_recommendation = risk["recommendation"]

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
    record = ensure_experiment(db, donation, controlled=evaluation_trial)
    record.donation_creation_ms = round((time.perf_counter() - request_started) * 1000, 3)

    ngos = db.query(User).filter(User.role == "ngo").all()
    requests = create_request_queue(db, donation, ngos)
    sync_experiment(db, donation)
    if not requests:
        db.add(donation)
        db.commit()
        db.refresh(donation)
        return donation

    ngo = db.query(User).filter(User.id == requests[0].ngo_id).first()
    db.commit()
    db.refresh(donation)
    event = {"type": "donation_request", "donation_id": donation.id,
             "ngo_id": ngo.id, "status": donation.status.value,
             "timestamp": datetime.utcnow().isoformat()}
    await manager.broadcast(f"ngo:{ngo.id}", event)
    await manager.broadcast(f"donor:{donation.donor_id}", event)
    await manager.broadcast("admin", event)

    return donation


@router.get("/donations", response_model=List[DonationOut])
def list_my_donations(db: Session = Depends(get_db), donor: User = Depends(require_role("donor"))):
    donations = (db.query(Donation).filter(Donation.donor_id == donor.id)
                 .order_by(Donation.created_at.desc()).all())
    return [add_delivery_state(db, donation) for donation in donations]


@router.get("/donations/{donation_id}", response_model=DonationOut)
def get_donation(donation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(404, "Donation not found.")
    if user.role.value == "admin":
        return add_delivery_state(db, donation)
    if user.role.value == "donor" and donation.donor_id == user.id:
        return add_delivery_state(db, donation)
    if user.role.value == "ngo" and donation.matched_ngo_id == user.id:
        return add_delivery_state(db, donation)
    if user.role.value == "volunteer":
        assigned = (db.query(DeliveryStop)
                    .join(Delivery, Delivery.id == DeliveryStop.delivery_id)
                    .filter(DeliveryStop.donation_id == donation.id,
                            Delivery.volunteer_id == user.id)
                    .first())
        if assigned:
            return add_delivery_state(db, donation)
    raise HTTPException(403, "You are not authorized to view this donation.")



