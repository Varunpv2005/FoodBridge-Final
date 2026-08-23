from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import require_role
from app.models_db import User, Donation, DonationStatus
from app.schemas_v2 import DonationOut

router = APIRouter()


@router.get("/donations", response_model=List[DonationOut])
def incoming_donations(db: Session = Depends(get_db), ngo: User = Depends(require_role("ngo"))):
    return (db.query(Donation).filter(Donation.matched_ngo_id == ngo.id)
            .order_by(Donation.created_at.desc()).all())


@router.post("/donations/{donation_id}/confirm-receipt", response_model=DonationOut)
def confirm_receipt(donation_id: str, db: Session = Depends(get_db), ngo: User = Depends(require_role("ngo"))):
    donation = db.query(Donation).filter(Donation.id == donation_id, Donation.matched_ngo_id == ngo.id).first()
    if not donation:
        raise HTTPException(404, "Donation not found for this NGO.")
    donation.status = DonationStatus.delivered
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return donation


@router.get("/profile")
def profile(ngo: User = Depends(require_role("ngo"))):
    return {
        "id": ngo.id, "name": ngo.name, "capacity_total": ngo.ngo_capacity_total,
        "capacity_available": ngo.ngo_capacity_available, "tier": ngo.ngo_tier,
        "has_cold_storage": ngo.ngo_has_cold_storage, "sentiment_score": ngo.ngo_sentiment_score,
        "lat": ngo.lat, "lng": ngo.lng,
    }
