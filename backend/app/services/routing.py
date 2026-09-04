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
from datetime import datetime, timedelta
from itertools import permutations
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models_db import Delivery, DeliveryStop, User, DeliveryStatus, Donation
from app.services.geo import haversine_km, road_metrics, solve_route

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
        before_result = solve_route(volunteer_start, existing_dropoffs) if existing_dropoffs else None
        if before_result and before_result.get("route_error"):
            continue
        before = before_result["total_distance_km"] if before_result else 0.0

        candidate_dropoffs = existing_dropoffs + [{"id": f"new-{ngo.id}", "lat": ngo.lat, "lng": ngo.lng}]
        after_result = solve_route(volunteer_start, candidate_dropoffs)
        if after_result.get("route_error"):
            continue
        after = after_result["total_distance_km"]

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


def _donation_window(donation):
    if not donation:
        return None
    if donation.spoil_by is not None:
        return donation.spoil_by
    if donation.cooked_at is not None and donation.degradation_hours is not None:
        return donation.cooked_at + timedelta(hours=donation.degradation_hours)
    return None


def _stop_groups(db: Session, stops: List[dict]):
    groups: Dict[str, List[dict]] = {}
    order = []
    for stop in stops:
        group_key = stop["donation_id"]
        if group_key not in groups:
            groups[group_key] = []
            order.append(group_key)
        groups[group_key].append(stop)
    return [groups[key] for key in order]


def _route_assessment(db: Session, result: dict, ordered_stops: List[dict], now: datetime):
    legs = {leg["stop_id"]: leg for leg in result.get("legs", [])}
    details = {}
    total_lateness_minutes = 0.0
    risk_exposure = 0.0
    urgent_count = 0
    late_count = 0

    for stop in ordered_stops:
        donation = db.query(Donation).filter(Donation.id == stop["donation_id"]).first()
        leg = legs.get(stop["id"])
        eta_minutes = leg.get("eta_minutes") if leg else None
        deadline = _donation_window(donation)
        arrival = now + timedelta(minutes=eta_minutes) if eta_minutes is not None else None
        remaining_minutes = None
        lateness_minutes = None
        if deadline is not None and arrival is not None:
            remaining_minutes = round((deadline - arrival).total_seconds() / 60.0, 1)
            lateness_minutes = round(max(0.0, -remaining_minutes), 1)
            total_lateness_minutes += lateness_minutes
            if lateness_minutes > 0:
                late_count += 1

        risk_score = getattr(donation, "risk_score", None) if donation else None
        if ((remaining_minutes is not None and remaining_minutes <= 60)
            or (risk_score is not None and risk_score >= 70)):
            urgency = "high"
        elif ((remaining_minutes is not None and remaining_minutes <= 180)
              or (risk_score is not None and risk_score >= 40)):
            urgency = "medium"
        elif remaining_minutes is not None or risk_score is not None:
            urgency = "low"
        else:
            urgency = "unknown"
        if urgency == "high":
            urgent_count += 1
        if risk_score is not None and eta_minutes is not None:
            risk_exposure += (float(risk_score) / 100.0) * (eta_minutes / 60.0)

        details[stop["id"]] = {
            "estimated_arrival": arrival.isoformat() if arrival is not None else None,
            "food_window_deadline": deadline.isoformat() if deadline is not None else None,
            "remaining_food_window_minutes": remaining_minutes,
            "lateness_minutes": lateness_minutes,
            "urgency": urgency,
            "risk_score": risk_score,
        }

    duration_minutes = max((leg.get("eta_minutes", 0.0) for leg in result.get("legs", [])), default=0.0)
    # One hour of road time equals one km of cost; lateness is penalized at 20 km/hour
    # because exceeding a food window is materially worse than a short detour.
    cost = (result.get("total_distance_km", 0.0)
            + duration_minutes / 60.0
            + (total_lateness_minutes / 60.0) * 20.0
            + risk_exposure * 2.0)
    return {
        "cost": round(cost, 6),
        "details": details,
        "duration_minutes": round(duration_minutes, 1),
        "urgent_count": urgent_count,
        "late_count": late_count,
        "total_lateness_minutes": round(total_lateness_minutes, 1),
    }


def _expiry_aware_route(db: Session, start, stops: List[dict]):
    """Choose a Google-routable order using expiry-aware operational costs."""
    if not stops:
        return solve_route(start, stops), {}

    ordered = sorted(stops, key=lambda stop: stop["sequence"])
    completed_count = 0
    while completed_count < len(ordered) and ordered[completed_count]["status"] == "completed":
        completed_count += 1
    if any(stop["status"] == "completed" for stop in ordered[completed_count:]):
        # An inconsistent persisted order is left untouched rather than reordered.
        result = solve_route(start, ordered)
        return result, _route_assessment(db, result, ordered, datetime.utcnow()) if not result.get("route_error") else {}

    completed = ordered[:completed_count]
    pending = ordered[completed_count:]
    groups = _stop_groups(db, pending)
    candidate_orders = permutations(groups) if len(groups) <= 6 else [tuple(groups)]
    best = None
    now = datetime.utcnow()
    for candidate_groups in candidate_orders:
        candidate_stops = completed + [stop for group in candidate_groups for stop in group]
        result = solve_route(start, candidate_stops)
        if result.get("route_error"):
            continue
        assessment = _route_assessment(db, result, candidate_stops, now)
        candidate = (assessment["cost"], result, assessment, candidate_stops)
        if best is None or candidate[0] < best[0]:
            best = candidate

    if best is None:
        result = solve_route(start, ordered)
        return result, _route_assessment(db, result, ordered, now) if not result.get("route_error") else {}
    return best[1], best[2]


def _replan_route(db: Session, delivery: Delivery, volunteer: User):
    stops = [{"id": s.id, "donation_id": s.donation_id, "lat": s.lat, "lng": s.lng,
              "sequence": s.sequence, "status": s.status} for s in
             sorted(delivery.stops, key=lambda s: s.sequence)]
    result, assessment = _expiry_aware_route(db, (volunteer.lat, volunteer.lng), stops)

    id_to_stop = {s.id: s for s in delivery.stops}
    if result.get("route_error"):
        delivery.route_error = result["route_error"]
        db.add(delivery)
        return
    for i, stop_id in enumerate(result["order"]):
        id_to_stop[stop_id].sequence = i
        for leg in result["legs"]:
            if leg["stop_id"] == stop_id:
                id_to_stop[stop_id].eta_minutes = leg["eta_minutes"]
        if stop_id in assessment.get("details", {}):
            for attr, value in assessment["details"][stop_id].items():
                setattr(id_to_stop[stop_id], attr, value)
    delivery.route_geojson = result["polyline"]
    delivery.total_distance_km = result["total_distance_km"]
    delivery.route_error = result.get("route_error")
    delivery.estimated_travel_minutes = assessment.get("duration_minutes") if assessment else None
    delivery.urgent_stop_count = assessment.get("urgent_count", 0) if assessment else 0
    delivery.expected_late_stop_count = assessment.get("late_count", 0) if assessment else 0
    delivery.route_recalculated_at = datetime.utcnow()
    db.add(delivery)


def refresh_delivery_route(db: Session, delivery: Delivery, force: bool = False):
    route_error = getattr(delivery, "route_error", None)
    if delivery.route_geojson and delivery.total_distance_km and delivery.estimated_travel_minutes is not None and not route_error and not force:
        return
    volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first()
    if volunteer:
        _replan_route(db, delivery, volunteer)


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

    candidates = sorted(
        candidates,
        key=lambda volunteer: haversine_km(volunteer.lat, volunteer.lng, donation.pickup_lat, donation.pickup_lng),
    )[:10]
    road_options = [
        (candidate, road_metrics((candidate.lat, candidate.lng), (donation.pickup_lat, donation.pickup_lng)))
        for candidate in candidates
    ]
    road_options = [item for item in road_options if item[1]["duration_minutes"] is not None]
    if not road_options:
        raise ValueError("Google travel information is unavailable; no volunteer was assigned.")
    volunteer = min(road_options, key=lambda item: item[1]["duration_minutes"])[0]

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
