from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import require_role
from app.models_db import User, Donation, Delivery, DonationStatus
from app.schemas_v2 import BaselineExperimentCreate, DonationOut, DeliveryOut
from app.models_db import ExperimentRecord
from app.services.assignment import assign_ngo
from app.services.routing import assign_volunteer, refresh_delivery_route
from app.services.delivery_view import add_latest_location
from app.services.evaluation import ensure_experiment, results_snapshot, sync_experiment

router = APIRouter()


@router.get("/results")
def results(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    for donation in db.query(Donation).all():
        sync_experiment(db, donation)
    db.commit()
    return results_snapshot(db)


@router.post("/results/baseline")
def record_baseline(payload: BaselineExperimentCreate, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    record = ExperimentRecord(
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        ngo_request_count=payload.ngo_request_count,
        fallback_count=payload.fallback_count,
        route_distance_km=payload.route_distance_km,
        route_duration_minutes=payload.route_duration_minutes,
        outcome="successful" if payload.successful else "incomplete",
        experiment_type="baseline",
    )
    db.add(record)
    db.commit()
    return {"id": record.id, "experiment_type": record.experiment_type, "outcome": record.outcome}


@router.post("/results/trials/{donation_id}")
def mark_controlled_trial(donation_id: str, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(404, "Donation not found.")
    record = ensure_experiment(db, donation, controlled=True)
    db.commit()
    return {"trial_id": record.trial_id, "donation_id": donation.id, "message": "Existing observed workflow explicitly marked as a controlled trial."}


@router.get("/overview")
def overview(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    donations = db.query(Donation).all()
    deliveries = db.query(Delivery).all()
    users = db.query(User).all()

    by_status = {}
    for d in donations:
        by_status[d.status] = by_status.get(d.status, 0) + 1

    return {
        "totals": {
            "donations": len(donations),
            "deliveries": len(deliveries),
            "donors": sum(1 for u in users if u.role == "donor"),
            "ngos": sum(1 for u in users if u.role == "ngo"),
            "volunteers": sum(1 for u in users if u.role == "volunteer"),
        },
        "donations_by_status": by_status,
        "anomalies_pending": sum(1 for d in donations if d.status == DonationStatus.flagged_anomaly),
        "active_deliveries": sum(1 for d in deliveries if d.status == "en_route"),
        "total_plates_delivered": sum(d.quantity_plates for d in donations if d.status == DonationStatus.delivered),
    }


@router.get("/donations", response_model=List[DonationOut])
def all_donations(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    return db.query(Donation).order_by(Donation.created_at.desc()).all()


@router.get("/deliveries", response_model=List[DeliveryOut])
def all_deliveries(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    deliveries = db.query(Delivery).order_by(Delivery.created_at.desc()).all()
    for delivery in deliveries:
        refresh_delivery_route(db, delivery)
        add_latest_location(db, delivery)
    db.commit()
    return deliveries


@router.get("/users")
def all_users(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    users = db.query(User).all()
    return [{
        "id": u.id, "name": u.name, "email": u.email, "role": u.role,
        "lat": u.lat, "lng": u.lng, "trust_score": u.trust_score,
        "volunteer_is_available": u.volunteer_is_available,
        "ngo_capacity_available": u.ngo_capacity_available,
    } for u in users]


@router.get("/anomalies", response_model=List[DonationOut])
def anomaly_queue(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    return (db.query(Donation).filter(Donation.status == DonationStatus.flagged_anomaly)
            .order_by(Donation.created_at.desc()).all())


@router.post("/anomalies/{donation_id}/approve", response_model=DonationOut)
def approve_anomaly(donation_id: str, db: Session = Depends(get_db),
                     admin: User = Depends(require_role("admin"))):
    """Admin manually clears a flagged donation, re-running the normal match pipeline."""
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(404, "Donation not found.")

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
    ngo.ngo_capacity_available = max(0, ngo.ngo_capacity_available - donation.quantity_plates)
    db.add(ngo)

    try:
        assign_volunteer(db, donation, ngo)
        donation.status = DonationStatus.assigned_volunteer
    except ValueError:
        donation.status = DonationStatus.matched
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return donation


@router.post("/anomalies/{donation_id}/reject", response_model=DonationOut)
def reject_anomaly(donation_id: str, db: Session = Depends(get_db),
                    admin: User = Depends(require_role("admin"))):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(404, "Donation not found.")
    donation.status = DonationStatus.rejected_quality
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return donation
