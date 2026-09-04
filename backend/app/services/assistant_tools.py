"""Authorized, read-only FoodBridge tools for the assistant."""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models_db import Delivery, DeliveryStop, Donation, User
from app.services.demand_forecasting import forecast_demand
from app.services.routing import refresh_delivery_route


def _role(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def _status(value):
    return value.value if hasattr(value, "value") else value


def _donation(db: Session, user: User, donation_id: Optional[str] = None):
    query = db.query(Donation)
    role = _role(user)
    if role == "donor":
        query = query.filter(Donation.donor_id == user.id)
    elif role == "ngo":
        query = query.filter(Donation.matched_ngo_id == user.id)
    elif role == "volunteer":
        query = (query.join(DeliveryStop, DeliveryStop.donation_id == Donation.id)
                 .join(Delivery, Delivery.id == DeliveryStop.delivery_id)
                 .filter(Delivery.volunteer_id == user.id))
    if donation_id:
        query = query.filter(Donation.id == donation_id)
    return query.order_by(Donation.created_at.desc()).first()


def _delivery(db: Session, user: User, delivery_id: Optional[str] = None):
    query = db.query(Delivery)
    role = _role(user)
    if role == "volunteer":
        query = query.filter(Delivery.volunteer_id == user.id)
    elif role in ("donor", "ngo"):
        query = (query.join(DeliveryStop, DeliveryStop.delivery_id == Delivery.id)
                 .join(Donation, Donation.id == DeliveryStop.donation_id))
        query = query.filter(Donation.donor_id == user.id if role == "donor" else Donation.matched_ngo_id == user.id)
    if delivery_id:
        query = query.filter(Delivery.id == delivery_id)
    return query.order_by(Delivery.created_at.desc()).first()


def _unavailable(message="unavailable"):
    return {"available": False, "message": message}


def _donation_summary(db, donation):
    ngo = db.query(User).filter(User.id == donation.matched_ngo_id).first() if donation.matched_ngo_id else None
    stop = db.query(DeliveryStop).filter(DeliveryStop.donation_id == donation.id).first()
    delivery = db.query(Delivery).filter(Delivery.id == stop.delivery_id).first() if stop else None
    volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first() if delivery else None
    return {
        "available": True,
        "donation_id": donation.id[:8],
        "status": _status(donation.status),
        "food_type": donation.food_type,
        "quantity_plates": donation.quantity_plates,
        "assigned_ngo": ngo.name if ngo else None,
        "assigned_volunteer": volunteer.name if volunteer else None,
        "delivery_id": delivery.id[:8] if delivery else None,
        "delivery_status": _status(delivery.status) if delivery else None,
    }


def get_my_donations(db: Session, user: User, **_):
    query = db.query(Donation)
    role = _role(user)
    if role == "donor":
        query = query.filter(Donation.donor_id == user.id)
    elif role == "ngo":
        query = query.filter(Donation.matched_ngo_id == user.id)
    elif role == "volunteer":
        query = (query.join(DeliveryStop, DeliveryStop.donation_id == Donation.id)
                 .join(Delivery, Delivery.id == DeliveryStop.delivery_id)
                 .filter(Delivery.volunteer_id == user.id))
    donations = query.order_by(Donation.created_at.desc()).limit(20).all()
    return {"available": True, "count": len(donations), "donations": [_donation_summary(db, donation) for donation in donations]}


def get_donation_status(db: Session, user: User, donation_id=None, **_):
    donation = _donation(db, user, donation_id)
    return _donation_summary(db, donation) if donation else _unavailable("No donation matching your account was found.")


def get_assigned_ngo(db: Session, user: User, donation_id=None, **_):
    donation = _donation(db, user, donation_id)
    if not donation:
        return _unavailable("No donation matching your account was found.")
    ngo = db.query(User).filter(User.id == donation.matched_ngo_id).first() if donation.matched_ngo_id else None
    return {"available": bool(ngo), "donation_id": donation.id[:8], "assigned_ngo": ngo.name if ngo else None}


def get_assigned_volunteer(db: Session, user: User, donation_id=None, **_):
    donation = _donation(db, user, donation_id)
    if not donation:
        return _unavailable("No donation matching your account was found.")
    stop = db.query(DeliveryStop).filter(DeliveryStop.donation_id == donation.id).first()
    delivery = db.query(Delivery).filter(Delivery.id == stop.delivery_id).first() if stop else None
    volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first() if delivery else None
    return {"available": bool(volunteer), "donation_id": donation.id[:8], "assigned_volunteer": volunteer.name if volunteer else None}


def get_delivery_status(db: Session, user: User, delivery_id=None, **_):
    delivery = _delivery(db, user, delivery_id)
    if not delivery:
        return _unavailable("No delivery matching your account was found.")
    return {
        "available": True,
        "delivery_id": delivery.id[:8],
        "status": _status(delivery.status),
        "stop_count": len(delivery.stops),
        "distance_km": delivery.total_distance_km,
    }


def get_current_location(db: Session, user: User, delivery_id=None, **_):
    delivery = _delivery(db, user, delivery_id) if delivery_id else None
    if _role(user) == "volunteer" and delivery is None:
        return {"available": True, "scope": "authenticated volunteer", "lat": user.lat, "lng": user.lng}
    if not delivery:
        return _unavailable("A specific authorized delivery is required for this location.")
    volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first()
    if not volunteer:
        return _unavailable("The assigned volunteer location is unavailable.")
    return {"available": True, "delivery_id": delivery.id[:8], "lat": volunteer.lat, "lng": volunteer.lng}


def get_route_eta(db: Session, user: User, delivery_id=None, **_):
    delivery = _delivery(db, user, delivery_id)
    if not delivery:
        return _unavailable("No delivery matching your account was found.")
    volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first()
    if volunteer:
        refresh_delivery_route(db, delivery)
    stops = []
    for stop in sorted(delivery.stops, key=lambda item: item.sequence):
        stops.append({
            "sequence": stop.sequence,
            "type": stop.stop_type,
            "status": stop.status,
            "eta_minutes": stop.eta_minutes,
            "estimated_arrival": getattr(stop, "estimated_arrival", None),
            "remaining_food_window_minutes": getattr(stop, "remaining_food_window_minutes", None),
            "lateness_minutes": getattr(stop, "lateness_minutes", None),
            "urgency": getattr(stop, "urgency", None),
        })
    return {
        "available": not bool(getattr(delivery, "route_error", None)),
        "delivery_id": delivery.id[:8],
        "route_error": getattr(delivery, "route_error", None),
        "estimated_travel_minutes": getattr(delivery, "estimated_travel_minutes", None),
        "stops": stops,
    }


def get_food_risk(db: Session, user: User, donation_id=None, **_):
    donation = _donation(db, user, donation_id)
    if not donation:
        return _unavailable("No donation matching your account was found.")
    if getattr(donation, "risk_score", None) is None and getattr(donation, "risk_level", None) is None:
        return {"available": False, "donation_id": donation.id[:8], "message": "Food-risk information is unavailable."}
    return {
        "available": True,
        "donation_id": donation.id[:8],
        "risk_score": getattr(donation, "risk_score", None),
        "risk_level": getattr(donation, "risk_level", None),
        "recommendation": getattr(donation, "risk_recommendation", None),
    }


def get_demand_forecast(_db: Session, _user: User, horizon=1, **_):
    try:
        forecast = forecast_demand(horizon=max(1, min(int(horizon or 1), 14)))
        return {"available": True, "scope": "aggregate across all regions and food types", "forecasts": forecast["forecasts"]}
    except (FileNotFoundError, KeyError, ValueError):
        return _unavailable("The demand forecast is unavailable.")


TOOL_HANDLERS = {
    "get_my_donations": get_my_donations,
    "get_donation_status": get_donation_status,
    "get_assigned_ngo": get_assigned_ngo,
    "get_assigned_volunteer": get_assigned_volunteer,
    "get_delivery_status": get_delivery_status,
    "get_current_location": get_current_location,
    "get_route_eta": get_route_eta,
    "get_food_risk": get_food_risk,
    "get_demand_forecast": get_demand_forecast,
}


def _tool(name, description, properties=None):
    return {"type": "function", "name": name, "description": description, "parameters": {"type": "object", "properties": properties or {}, "additionalProperties": False}}


TOOL_DEFINITIONS = [
    _tool("get_my_donations", "Read donations visible to the authenticated user."),
    _tool("get_donation_status", "Read the status of an authorized donation.", {"donation_id": {"type": "string"}}),
    _tool("get_assigned_ngo", "Read the NGO assigned to an authorized donation.", {"donation_id": {"type": "string"}}),
    _tool("get_assigned_volunteer", "Read the volunteer assigned to an authorized donation.", {"donation_id": {"type": "string"}}),
    _tool("get_delivery_status", "Read the status of an authorized delivery.", {"delivery_id": {"type": "string"}}),
    _tool("get_current_location", "Read an authenticated volunteer or authorized delivery volunteer location.", {"delivery_id": {"type": "string"}}),
    _tool("get_route_eta", "Read Google Routes-backed ETA and expiry-aware route details for an authorized delivery.", {"delivery_id": {"type": "string"}}),
    _tool("get_food_risk", "Read estimated food-risk information for an authorized donation.", {"donation_id": {"type": "string"}}),
    _tool("get_demand_forecast", "Read the existing aggregate demand forecast.", {"horizon": {"type": "integer", "minimum": 1, "maximum": 14}}),
]


def execute_tool(name: str, arguments: Dict[str, Any], db: Session, user: User):
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return _unavailable("That read-only tool is unavailable.")
    try:
        return handler(db, user, **(arguments or {}))
    except Exception:
        return _unavailable("The requested FoodBridge information is unavailable.")
