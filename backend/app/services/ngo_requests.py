from datetime import datetime

from sqlalchemy.orm import Session

from app.models_db import Donation, DonationStatus, NGORequest, User
from app.services.assignment import rank_ngo_candidates


def create_request_queue(db: Session, donation: Donation, ngos: list[User]) -> list[NGORequest]:
    candidates = rank_ngo_candidates(donation, ngos)
    now = datetime.utcnow()
    requests = []
    for rank, candidate in enumerate(candidates, start=1):
        request = NGORequest(
            donation_id=donation.id,
            ngo_id=candidate["ngo_id"],
            rank=rank,
            status="pending" if rank == 1 else "queued",
            probability=candidate["probability"],
            distance_km=candidate["distance_km"],
            reason=candidate["reason"],
            requested_at=now if rank == 1 else None,
        )
        db.add(request)
        requests.append(request)

    if requests:
        first = candidates[0]
        apply_candidate(donation, first)
        donation.status = DonationStatus.matched
    else:
        donation.status = DonationStatus.pending_match
        donation.matched_ngo_id = None
    return requests


def apply_candidate(donation: Donation, candidate: dict) -> None:
    donation.matched_ngo_id = candidate["ngo_id"]
    donation.match_probability = candidate["probability"]
    donation.match_shap = candidate["shap"]
    donation.match_reason = candidate["reason"]
    donation.match_factors = candidate["factors"]
    donation.match_explanation = candidate["explanation"]


def advance_request(db: Session, donation: Donation, rejected: NGORequest) -> NGORequest | None:
    rejected.status = "rejected"
    rejected.decided_at = datetime.utcnow()
    db.add(rejected)
    next_request = (db.query(NGORequest)
                    .filter(NGORequest.donation_id == donation.id,
                            NGORequest.status == "queued")
                    .order_by(NGORequest.rank)
                    .first())
    if not next_request:
        donation.matched_ngo_id = None
        donation.status = DonationStatus.pending_match
        return None

    next_request.status = "pending"
    next_request.requested_at = datetime.utcnow()
    next_ngo = db.query(User).filter(User.id == next_request.ngo_id).first()
    if not next_ngo:
        return advance_request(db, donation, next_request)
    apply_candidate(donation, {
        "ngo_id": next_ngo.id,
        "probability": next_request.probability,
        "shap": donation.match_shap or {},
        "reason": next_request.reason or "Next suitable NGO candidate.",
        "factors": donation.match_factors or {},
        "explanation": donation.match_explanation or [],
    })
    donation.status = DonationStatus.matched
    return next_request


def request_for_ngo(db: Session, donation_id: str, ngo_id: str) -> NGORequest | None:
    return (db.query(NGORequest)
            .filter(NGORequest.donation_id == donation_id, NGORequest.ngo_id == ngo_id)
            .first())


def request_state(db: Session, donation: Donation) -> tuple[str | None, list[dict]]:
    requests = (db.query(NGORequest)
                .filter(NGORequest.donation_id == donation.id)
                .order_by(NGORequest.rank)
                .all())
    current = next((item.status for item in requests if item.status == "pending"), None)
    history = []
    for item in requests:
        ngo = db.query(User).filter(User.id == item.ngo_id).first()
        history.append({
            "ngo_id": item.ngo_id,
            "ngo_name": ngo.name if ngo else "Unavailable NGO",
            "rank": item.rank,
            "status": item.status,
            "distance_km": item.distance_km,
            "requested_at": item.requested_at.isoformat() if item.requested_at else None,
            "decided_at": item.decided_at.isoformat() if item.decided_at else None,
        })
    return current, history
