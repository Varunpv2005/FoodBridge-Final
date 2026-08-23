from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import require_role
from app.models_db import User, Delivery, DeliveryStatus, DeliveryStop, Donation, DonationStatus, LocationPing
from app.schemas_v2 import DeliveryOut, LocationUpdate
from app.services.ws_manager import manager

router = APIRouter()


@router.get("/deliveries", response_model=List[DeliveryOut])
def my_deliveries(db: Session = Depends(get_db), volunteer: User = Depends(require_role("volunteer"))):
    return (db.query(Delivery).filter(Delivery.volunteer_id == volunteer.id)
            .order_by(Delivery.created_at.desc()).all())


@router.post("/deliveries/{delivery_id}/start", response_model=DeliveryOut)
def start_delivery(delivery_id: str, db: Session = Depends(get_db),
                    volunteer: User = Depends(require_role("volunteer"))):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id, Delivery.volunteer_id == volunteer.id).first()
    if not delivery:
        raise HTTPException(404, "Delivery not found.")
    delivery.status = DeliveryStatus.en_route
    db.add(delivery)
    db.commit()
    db.refresh(delivery)  # background GPS simulation; swap for real device pings in production
    return delivery


@router.post("/location")
async def update_location(payload: LocationUpdate, db: Session = Depends(get_db),
                           volunteer: User = Depends(require_role("volunteer"))):
    """Real-device GPS endpoint (used instead of the simulator once phones are in the loop)."""
    volunteer.lat, volunteer.lng = payload.lat, payload.lng
    db.add(volunteer)
    ping = LocationPing(volunteer_id=volunteer.id, lat=payload.lat, lng=payload.lng)
    db.add(ping)
    db.commit()
    await manager.broadcast("admin", {"type": "location_update", "volunteer_id": volunteer.id,
                                       "lat": payload.lat, "lng": payload.lng,
                                       "timestamp": datetime.utcnow().isoformat()})
    return {"status": "ok"}


@router.post("/stops/{stop_id}/arrive")
def mark_stop_arrived(stop_id: str, db: Session = Depends(get_db),
                       volunteer: User = Depends(require_role("volunteer"))):
    stop = db.query(DeliveryStop).filter(DeliveryStop.id == stop_id).first()
    if not stop:
        raise HTTPException(404, "Stop not found.")
    stop.status = "completed"
    stop.arrived_at = datetime.utcnow()
    db.add(stop)

    if stop.stop_type == "dropoff":
        donation = db.query(Donation).filter(Donation.id == stop.donation_id).first()
        if donation:
            donation.status = DonationStatus.delivered
            db.add(donation)

    db.commit()

    delivery = db.query(Delivery).filter(Delivery.id == stop.delivery_id).first()
    remaining = [s for s in delivery.stops if s.status != "completed"]
    if not remaining:
        delivery.status = DeliveryStatus.completed
        delivery.completed_at = datetime.utcnow()
        db.add(delivery)
        vol = db.query(User).filter(User.id == delivery.volunteer_id).first()
        if vol:
            vol.volunteer_is_available = True
            db.add(vol)
        db.commit()

    return {"status": "ok"}
