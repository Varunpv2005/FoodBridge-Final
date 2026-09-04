from datetime import datetime
import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import require_role
from app.models_db import User, Donation, DonationStatus
from app.schemas_v2 import DonationOut
from app.services.ws_manager import manager
from app.services.routing import assign_volunteer
from app.models_db import DeliveryStop
from app.services.delivery_view import add_delivery_state
from app.services.ngo_requests import advance_request, request_for_ngo
from app.services.evaluation import sync_experiment

router = APIRouter()


@router.get("/donations", response_model=List[DonationOut])
def incoming_donations(db: Session = Depends(get_db), ngo: User = Depends(require_role("ngo"))):
    donations = (db.query(Donation).filter(Donation.matched_ngo_id == ngo.id)
                 .order_by(Donation.created_at.desc()).all())
    return [add_delivery_state(db, donation) for donation in donations]


@router.post("/donations/{donation_id}/confirm-receipt", response_model=DonationOut)
async def confirm_receipt(donation_id: str, db: Session = Depends(get_db), ngo: User = Depends(require_role("ngo"))):
    donation = db.query(Donation).filter(Donation.id == donation_id,
                                         Donation.matched_ngo_id == ngo.id).first()
    if not donation:
        raise HTTPException(404, "Donation not found for this NGO.")
    if donation.status != DonationStatus.matched:
        raise HTTPException(409, "Donation is no longer available for acceptance.")
    if db.query(DeliveryStop).filter(DeliveryStop.donation_id == donation.id).first():
        raise HTTPException(409, "Donation is already assigned.")

    request = request_for_ngo(db, donation.id, ngo.id)
    if not request or request.status != "pending":
        raise HTTPException(409, "This donation request is no longer pending.")
    request.status = "accepted"
    request.decided_at = datetime.utcnow()
    claimed = (db.query(Donation)
               .filter(Donation.id == donation.id,
                       Donation.matched_ngo_id == ngo.id,
                       Donation.status == DonationStatus.matched)
               .update({Donation.status: DonationStatus.ngo_accepted}, synchronize_session=False))
    if claimed != 1:
        raise HTTPException(409, "Donation is no longer available for acceptance.")
    donation.status = DonationStatus.ngo_accepted
    ngo.ngo_capacity_available = max(0, ngo.ngo_capacity_available - donation.quantity_plates)
    db.add(ngo)
    db.add(donation)
    sync_experiment(db, donation)
    db.commit()
    db.refresh(donation)
    accepted_event = {"type": "ngo_accepted", "donation_id": donation.id,
             "ngo_id": ngo.id, "status": donation.status.value,
             "timestamp": datetime.utcnow().isoformat()}
    await manager.broadcast(f"ngo:{ngo.id}", accepted_event)
    await manager.broadcast(f"donor:{donation.donor_id}", accepted_event)
    await manager.broadcast("admin", accepted_event)
    assignment_started = time.perf_counter()
    try:
        delivery = assign_volunteer(db, donation, ngo)
    except ValueError:
        raise HTTPException(409, "No available volunteer for this donation.")

    donation.status = DonationStatus.assigned_volunteer
    record = sync_experiment(db, donation)
    record.assignment_processing_ms = round((time.perf_counter() - assignment_started) * 1000, 3)
    db.add(ngo)
    db.add(donation)
    db.commit()
    db.refresh(donation)
    event = {"type": "delivery_assigned", "donation_id": donation.id,
             "delivery_id": delivery.id, "volunteer_id": delivery.volunteer_id,
             "status": donation.status.value, "ngo_accepted": True,
             "timestamp": datetime.utcnow().isoformat()}
    await manager.broadcast(f"ngo:{ngo.id}", event)
    await manager.broadcast(f"donor:{donation.donor_id}", event)
    await manager.broadcast(f"volunteer:{delivery.volunteer_id}", event)
    await manager.broadcast("admin", event)
    return donation


@router.post("/donations/{donation_id}/reject", response_model=DonationOut)
async def reject_donation(donation_id: str, db: Session = Depends(get_db), ngo: User = Depends(require_role("ngo"))):
    donation = db.query(Donation).filter(Donation.id == donation_id,
                                         Donation.matched_ngo_id == ngo.id).first()
    if not donation or donation.status != DonationStatus.matched:
        raise HTTPException(404, "Pending donation request not found for this NGO.")
    request = request_for_ngo(db, donation.id, ngo.id)
    if not request or request.status != "pending":
        raise HTTPException(409, "This donation request is no longer pending.")
    next_request = advance_request(db, donation, request)
    sync_experiment(db, donation)
    db.commit()
    db.refresh(donation)
    await manager.broadcast(f"donor:{donation.donor_id}", {
        "type": "ngo_rejected", "donation_id": donation.id, "ngo_id": ngo.id,
        "ngo_name": ngo.name, "next_ngo_id": next_request.ngo_id if next_request else None,
        "status": donation.status.value, "timestamp": datetime.utcnow().isoformat(),
    })
    await manager.broadcast("admin", {
        "type": "ngo_rejected", "donation_id": donation.id, "ngo_id": ngo.id,
        "next_ngo_id": next_request.ngo_id if next_request else None,
        "status": donation.status.value, "timestamp": datetime.utcnow().isoformat(),
    })
    if next_request:
        await manager.broadcast(f"ngo:{next_request.ngo_id}", {
            "type": "donation_request", "donation_id": donation.id,
            "ngo_id": next_request.ngo_id, "status": donation.status.value,
            "timestamp": datetime.utcnow().isoformat(),
        })
    return donation


@router.get("/profile")
def profile(ngo: User = Depends(require_role("ngo"))):
    return {
        "id": ngo.id, "name": ngo.name, "capacity_total": ngo.ngo_capacity_total,
        "capacity_available": ngo.ngo_capacity_available, "tier": ngo.ngo_tier,
        "has_cold_storage": ngo.ngo_has_cold_storage, "sentiment_score": ngo.ngo_sentiment_score,
        "lat": ngo.lat, "lng": ngo.lng,
    }
