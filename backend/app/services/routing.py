"""
Decides which volunteer delivers a newly-matched donation, and whether it
can be *consolidated* into an already-running multi-stop delivery instead
of dispatching a brand-new volunteer trip — this is the "multi-stop
vehicle routing when more than one NGO is on the way" requirement.

Strategy:
  1. Look at every delivery currently `planned` or `en_route`. For each,
     check the assigned volunteer has spare plate-capacity and that
     inserting this donation's pickup+dropoff only adds a small detour
     (< CONSOLIDATION_DETOUR_KM extra distance vs. the existing route).
     If found, attach as new stops and re-solve the route (nearest-
     neighbour + 2-opt) over the combined stop set.
  2. Otherwise, pick the nearest available/free-capacity volunteer and
     start a brand-new delivery with just this donation's pickup+dropoff.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models_db import Delivery, DeliveryStop, User, DeliveryStatus, Donation
from app.services.geo import haversine_km, solve_route

CONSOLIDATION_DETOUR_KM = 6.0


def _delivery_current_load(db: Session, delivery: Delivery) -> int:
    total = 0
    for stop in delivery.stops:
        if stop.stop_type == "pickup":
            donation = db.query(Donation).filter(Donation.id == stop.donation_id).first()
            if donation:
                total += donation.quantity_plates
    return total


def _existing_stop_points(delivery: Delivery):
    return [{"id": s.id, "lat": s.lat, "lng": s.lng} for s in delivery.stops if s.stop_type == "dropoff"]


def try_consolidate(db: Session, donation: Donation, ngo: User) -> Optional[Delivery]:
    active = (db.query(Delivery)
              .filter(Delivery.status.in_([DeliveryStatus.planned, DeliveryStatus.en_route]))
              .all())

    for delivery in active:
        volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first()
        if not volunteer:
            continue
        current_load = _delivery_current_load(db, delivery)
        if current_load + donation.quantity_plates > volunteer.volunteer_capacity_plates:
            continue

        existing_dropoffs = _existing_stop_points(delivery)
        volunteer_start = (volunteer.lat, volunteer.lng)
        before = solve_route(volunteer_start, existing_dropoffs)["total_distance_km"] if existing_dropoffs else 0.0

        candidate_dropoffs = existing_dropoffs + [{"id": f"new-{ngo.id}", "lat": ngo.lat, "lng": ngo.lng}]
        after = solve_route(volunteer_start, candidate_dropoffs)["total_distance_km"]

        if (after - before) <= CONSOLIDATION_DETOUR_KM:
            _add_stops_and_replan(db, delivery, donation, ngo, volunteer)
            return delivery
    return None


def _add_stops_and_replan(db: Session, delivery: Delivery, donation: Donation, ngo: User, volunteer: User):
    max_seq = max((s.sequence for s in delivery.stops), default=-1)
    pickup_stop = DeliveryStop(
        delivery_id=delivery.id, donation_id=donation.id, ngo_id=ngo.id,
        sequence=max_seq + 1, stop_type="pickup",
        lat=donation.pickup_lat, lng=donation.pickup_lng, status="pending",
    )
    dropoff_stop = DeliveryStop(
        delivery_id=delivery.id, donation_id=donation.id, ngo_id=ngo.id,
        sequence=max_seq + 2, stop_type="dropoff",
        lat=ngo.lat, lng=ngo.lng, status="pending",
    )
    db.add(pickup_stop)
    db.add(dropoff_stop)
    db.flush()
    _replan_route(db, delivery, volunteer)


def _replan_route(db: Session, delivery: Delivery, volunteer: User):
    stops = [{"id": s.id, "lat": s.lat, "lng": s.lng} for s in
             sorted(delivery.stops, key=lambda s: s.sequence)]
    result = solve_route((volunteer.lat, volunteer.lng), stops)

    id_to_stop = {s.id: s for s in delivery.stops}
    for i, stop_id in enumerate(result["order"]):
        id_to_stop[stop_id].sequence = i
        for leg in result["legs"]:
            if leg["stop_id"] == stop_id:
                id_to_stop[stop_id].eta_minutes = leg["eta_minutes"]
    delivery.route_geojson = result["polyline"]
    delivery.total_distance_km = result["total_distance_km"]
    db.add(delivery)


def assign_volunteer(db: Session, donation: Donation, ngo: User) -> Delivery:
    consolidated = try_consolidate(db, donation, ngo)
    if consolidated:
        db.commit()
        db.refresh(consolidated)
        return consolidated

    candidates = (db.query(User)
                  .filter(User.role == "volunteer",
                          User.volunteer_is_available == True,  # noqa: E712
                          User.volunteer_capacity_plates >= donation.quantity_plates)
                  .all())
    if not candidates:
        raise ValueError("No available volunteer with sufficient capacity.")

    volunteer = min(candidates, key=lambda v: haversine_km(donation.pickup_lat, donation.pickup_lng, v.lat, v.lng))

    delivery = Delivery(volunteer_id=volunteer.id, status=DeliveryStatus.planned)
    db.add(delivery)
    db.flush()

    pickup_stop = DeliveryStop(
        delivery_id=delivery.id, donation_id=donation.id, ngo_id=ngo.id,
        sequence=0, stop_type="pickup", lat=donation.pickup_lat, lng=donation.pickup_lng, status="pending",
    )
    dropoff_stop = DeliveryStop(
        delivery_id=delivery.id, donation_id=donation.id, ngo_id=ngo.id,
        sequence=1, stop_type="dropoff", lat=ngo.lat, lng=ngo.lng, status="pending",
    )
    db.add(pickup_stop)
    db.add(dropoff_stop)
    db.flush()

    _replan_route(db, delivery, volunteer)
    volunteer.volunteer_is_available = False
    db.add(volunteer)
    db.commit()
    db.refresh(delivery)
    return delivery
