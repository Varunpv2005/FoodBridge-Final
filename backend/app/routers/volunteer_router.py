from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import require_role
from app.models_db import User, Delivery, DeliveryStatus, DeliveryStop, Donation, DonationStatus, LocationPing
from app.schemas_v2 import DeliveryOut, LocationUpdate
from app.services.ws_manager import manager
from app.services.routing import refresh_delivery_route
from app.services.delivery_view import add_latest_location
from app.services.deviation import ROUTE_DEVIATION_THRESHOLD_METERS, deviation_event_allowed, distance_to_route_meters, is_route_deviated
from app.services.geo import haversine_km
from app.services.evaluation import record_location as record_evaluation_location, sync_experiment

ROUTE_RECALCULATION_COOLDOWN_SECONDS = 60
ARRIVAL_THRESHOLD_METERS = 100.0

router = APIRouter()


async def broadcast_delivery_status(db: Session, delivery: Delivery, event_type: str = "delivery_status"):
    message = {"type": event_type, "delivery_id": delivery.id, "status": delivery.status.value,
               "timestamp": datetime.utcnow().isoformat()}
    channels = {"admin", delivery.id, f"volunteer:{delivery.volunteer_id}"}
    for stop in delivery.stops:
        channels.add(f"ngo:{stop.ngo_id}")
        donation = db.query(Donation).filter(Donation.id == stop.donation_id).first()
        if donation:
            channels.add(f"donor:{donation.donor_id}")
    for channel in channels:
        await manager.broadcast(channel, message)


async def broadcast_donation_status(db: Session, donation: Donation):
    message = {"type": "donation_status", "donation_id": donation.id,
               "status": donation.status.value, "timestamp": datetime.utcnow().isoformat()}
    channels = {"admin", f"donor:{donation.donor_id}"}
    if donation.matched_ngo_id:
        channels.add(f"ngo:{donation.matched_ngo_id}")
    delivery_stop = db.query(DeliveryStop).filter(DeliveryStop.donation_id == donation.id).first()
    if delivery_stop:
        delivery = db.query(Delivery).filter(Delivery.id == delivery_stop.delivery_id).first()
        if delivery:
            channels.update({delivery.id, f"volunteer:{delivery.volunteer_id}"})
    for channel in channels:
        await manager.broadcast(channel, message)


async def record_location(db: Session, volunteer: User, payload: LocationUpdate,
                          delivery_id: str = None):
    delivery_query = db.query(Delivery).filter(
        Delivery.volunteer_id == volunteer.id,
        Delivery.status == DeliveryStatus.en_route,
    )
    if delivery_id:
        delivery_query = delivery_query.filter(Delivery.id == delivery_id)
    delivery = delivery_query.order_by(Delivery.created_at.desc()).first()
    if not delivery:
        raise HTTPException(409, "No active delivery is authorized for this location update.")

    volunteer.lat, volunteer.lng = payload.lat, payload.lng
    db.add(volunteer)
    ping = LocationPing(volunteer_id=volunteer.id,
                        delivery_id=delivery.id if delivery else None,
                        lat=payload.lat, lng=payload.lng)
    db.add(ping)
    deviation_event = None
    if delivery and delivery.route_geojson and not delivery.route_error:
        position = (payload.lat, payload.lng)
        distance_from_route = distance_to_route_meters(position, delivery.route_geojson)
        deviated = is_route_deviated(position, delivery.route_geojson, ROUTE_DEVIATION_THRESHOLD_METERS)
        now = datetime.utcnow()
        last_event = delivery.route_deviation_at or delivery.route_recalculated_at
        if deviated and deviation_event_allowed(delivery.route_deviated, last_event, now, ROUTE_RECALCULATION_COOLDOWN_SECONDS):
            delivery.route_deviated = True
            delivery.route_deviation_at = now
            refresh_delivery_route(db, delivery, force=True)
            deviation_event = {
                "type": "route_deviation",
                "delivery_id": delivery.id,
                "volunteer_id": volunteer.id,
                "distance_from_route_meters": round(distance_from_route, 1) if distance_from_route is not None else None,
                "threshold_meters": ROUTE_DEVIATION_THRESHOLD_METERS,
                "route_geojson": delivery.route_geojson,
                "total_distance_km": delivery.total_distance_km,
                "estimated_travel_minutes": delivery.estimated_travel_minutes,
                "route_error": delivery.route_error,
                "timestamp": now.isoformat(),
            }
        elif not deviated and delivery.route_deviated:
            delivery.route_deviated = False
            deviation_event = {
                "type": "route_recovered",
                "delivery_id": delivery.id,
                "volunteer_id": volunteer.id,
                "distance_from_route_meters": round(distance_from_route, 1) if distance_from_route is not None else None,
                "threshold_meters": ROUTE_DEVIATION_THRESHOLD_METERS,
                "timestamp": now.isoformat(),
            }
        db.add(delivery)
    db.commit()
    record_evaluation_location(db, delivery, payload.timestamp)
    db.commit()

    message = {"type": "location_update", "volunteer_id": volunteer.id,
               "lat": payload.lat, "lng": payload.lng,
               "accuracy": payload.accuracy,
               "timestamp": (payload.timestamp or datetime.utcnow()).isoformat()}
    channels = {"admin"}
    if delivery:
        message["delivery_id"] = delivery.id
        channels.update({delivery.id, f"volunteer:{volunteer.id}"})
        for stop in delivery.stops:
            channels.add(f"ngo:{stop.ngo_id}")
            donation = db.query(Donation).filter(Donation.id == stop.donation_id).first()
            if donation:
                channels.add(f"donor:{donation.donor_id}")
    if deviation_event:
        for channel in channels:
            await manager.broadcast(channel, deviation_event)
    for channel in channels:
        await manager.broadcast(channel, message)
    return message


@router.get("/deliveries", response_model=List[DeliveryOut])
def my_deliveries(db: Session = Depends(get_db), volunteer: User = Depends(require_role("volunteer"))):
    deliveries = (db.query(Delivery).filter(Delivery.volunteer_id == volunteer.id)
                  .order_by(Delivery.created_at.desc()).all())
    for delivery in deliveries:
        refresh_delivery_route(db, delivery)
    db.commit()
    for delivery in deliveries:
        for stop in delivery.stops:
            donation = db.query(Donation).filter(Donation.id == stop.donation_id).first()
            donor = db.query(User).filter(User.id == donation.donor_id).first() if donation else None
            ngo = db.query(User).filter(User.id == stop.ngo_id).first()
            stop.food_type = donation.food_type if donation else None
            stop.quantity_plates = donation.quantity_plates if donation else None
            stop.donor_name = donor.name if donor else None
            stop.pickup_address = donation.pickup_address if donation else None
            stop.ngo_name = ngo.name if ngo else None
        add_latest_location(db, delivery)
    return deliveries


@router.post("/deliveries/{delivery_id}/start", response_model=DeliveryOut)
async def start_delivery(delivery_id: str, db: Session = Depends(get_db),
                         volunteer: User = Depends(require_role("volunteer"))):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id, Delivery.volunteer_id == volunteer.id).first()
    if not delivery:
        raise HTTPException(404, "Delivery not found.")
    if delivery.status != DeliveryStatus.planned:
        raise HTTPException(409, "Delivery is not available to start.")
    delivery.status = DeliveryStatus.en_route
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    await broadcast_delivery_status(db, delivery)
    return delivery


@router.post("/location")
async def update_location(payload: LocationUpdate, db: Session = Depends(get_db),
                           volunteer: User = Depends(require_role("volunteer"))):
    """Real-device GPS endpoint (used instead of the simulator once phones are in the loop)."""
    if not payload.delivery_id:
        raise HTTPException(422, "delivery_id is required for a location update.")
    await record_location(db, volunteer, payload, payload.delivery_id)
    return {"status": "ok"}


@router.post("/stops/{stop_id}/arrive")
async def mark_stop_arrived(stop_id: str, db: Session = Depends(get_db),
                            volunteer: User = Depends(require_role("volunteer"))):
    stop = (db.query(DeliveryStop)
            .join(Delivery, Delivery.id == DeliveryStop.delivery_id)
            .filter(DeliveryStop.id == stop_id,
                    Delivery.volunteer_id == volunteer.id)
            .first())
    if not stop:
        raise HTTPException(404, "Stop not found.")
    delivery = db.query(Delivery).filter(Delivery.id == stop.delivery_id).first()
    if delivery.status != DeliveryStatus.en_route:
        raise HTTPException(409, "Delivery is not in progress.")
    if stop.status == "completed":
        raise HTTPException(409, "Stop is already completed.")
    next_stop = next((item for item in delivery.stops if item.status != "completed"), None)
    if next_stop and next_stop.id != stop.id:
        raise HTTPException(409, "Complete the stops in sequence.")
    latest_ping = (db.query(LocationPing)
                   .filter(LocationPing.delivery_id == delivery.id,
                           LocationPing.volunteer_id == volunteer.id)
                   .order_by(LocationPing.timestamp.desc())
                   .first())
    if not latest_ping:
        raise HTTPException(409, "A current GPS position is required before confirming arrival.")
    distance_to_stop = haversine_km(latest_ping.lat, latest_ping.lng, stop.lat, stop.lng) * 1000
    if distance_to_stop > ARRIVAL_THRESHOLD_METERS:
        raise HTTPException(409, "The volunteer is not within the arrival proximity threshold.")
    stop.status = "completed"
    stop.arrived_at = datetime.utcnow()
    db.add(stop)
    refresh_delivery_route(db, delivery, force=True)

    donation = db.query(Donation).filter(Donation.id == stop.donation_id).first()
    if stop.stop_type == "dropoff":
        if donation:
            donation.status = DonationStatus.delivered
            db.add(donation)
    else:
        if donation and donation.status == DonationStatus.assigned_volunteer:
            donation.status = DonationStatus.picked_up
            db.add(donation)

    db.commit()
    arrival_event = {
        "type": "arrival_detected", "delivery_id": delivery.id, "stop_id": stop.id,
        "donation_id": stop.donation_id, "volunteer_id": volunteer.id,
        "distance_meters": round(distance_to_stop, 1),
        "threshold_meters": ARRIVAL_THRESHOLD_METERS,
        "timestamp": datetime.utcnow().isoformat(),
    }
    stop_event = {
        "type": "stop_completed", "delivery_id": delivery.id, "stop_id": stop.id,
        "donation_id": stop.donation_id, "volunteer_id": volunteer.id,
        "status": stop.status, "timestamp": datetime.utcnow().isoformat(),
    }
    stop_channels = {"admin", delivery.id, f"volunteer:{volunteer.id}", f"ngo:{stop.ngo_id}"}
    if donation:
        stop_channels.add(f"donor:{donation.donor_id}")
    for channel in stop_channels:
        await manager.broadcast(channel, arrival_event)
        await manager.broadcast(channel, stop_event)
    if donation:
        await broadcast_donation_status(db, donation)

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
        await broadcast_delivery_status(db, delivery, "delivery_completed")
        for completed_stop in delivery.stops:
            completed_donation = db.query(Donation).filter(Donation.id == completed_stop.donation_id).first()
            if completed_donation:
                sync_experiment(db, completed_donation)
        db.commit()
    else:
        await broadcast_delivery_status(db, delivery)

    return {"status": "ok"}
