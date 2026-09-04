from sqlalchemy.orm import Session

from app.models_db import Delivery, DeliveryStop, Donation, LocationPing, User
from app.services.ngo_requests import request_state


def add_latest_location(db: Session, delivery: Delivery) -> Delivery:
    ping = (db.query(LocationPing)
        .filter(LocationPing.delivery_id == delivery.id,
            LocationPing.volunteer_id == delivery.volunteer_id)
        .order_by(LocationPing.timestamp.desc())
        .first())
    delivery.latest_location_lat = ping.lat if ping else None
    delivery.latest_location_lng = ping.lng if ping else None
    delivery.latest_location_timestamp = ping.timestamp if ping else None
    return delivery


def add_delivery_state(db: Session, donation: Donation) -> Donation:
    donor = db.query(User).filter(User.id == donation.donor_id).first()
    donation.donor_name = donor.name if donor else None
    donation.ngo_request_status, donation.ngo_request_history = request_state(db, donation)
    ngo = db.query(User).filter(User.id == donation.matched_ngo_id).first() if donation.matched_ngo_id else None
    donation.matched_ngo_name = ngo.name if ngo else None
    donation.matched_ngo_lat = ngo.lat if ngo else None
    donation.matched_ngo_lng = ngo.lng if ngo else None
    stop = db.query(DeliveryStop).filter(DeliveryStop.donation_id == donation.id).first()
    if not stop:
        return donation
    delivery = db.query(Delivery).filter(Delivery.id == stop.delivery_id).first()
    if not delivery:
        return donation
    add_latest_location(db, delivery)
    donation.delivery_id = delivery.id
    donation.delivery_status = delivery.status.value
    donation.volunteer_id = delivery.volunteer_id
    volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first()
    donation.volunteer_name = volunteer.name if volunteer else None
    donation.delivery_route = delivery.route_geojson
    donation.delivery_distance_km = delivery.total_distance_km
    donation.delivery_travel_minutes = getattr(delivery, "estimated_travel_minutes", None)
    donation.delivery_urgent_stop_count = getattr(delivery, "urgent_stop_count", 0)
    donation.delivery_late_stop_count = getattr(delivery, "expected_late_stop_count", 0)
    donation.delivery_completed_at = delivery.completed_at
    donation.delivery_eta_minutes = max((s.eta_minutes or 0 for s in delivery.stops), default=0) or None
    donation.latest_location_lat = delivery.latest_location_lat
    donation.latest_location_lng = delivery.latest_location_lng
    donation.latest_location_timestamp = delivery.latest_location_timestamp
    donation.delivery_stops = [
        {"lat": stop.lat, "lng": stop.lng, "stop_type": stop.stop_type, "status": stop.status, "sequence": stop.sequence}
        for stop in sorted(delivery.stops, key=lambda item: item.sequence)
    ]
    return donation
