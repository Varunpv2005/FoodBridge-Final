"""
Full relational schema for FoodBridge: users (4 roles), donations, the
NGO-matching decision trail, multi-stop deliveries, live location pings,
and the feedback loop that continuously updates trust/sentiment scores.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Enum, JSON
)
from sqlalchemy.orm import relationship

from app.db import Base


def gen_id():
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    donor = "donor"
    ngo = "ngo"
    volunteer = "volunteer"
    admin = "admin"


class DonationStatus(str, enum.Enum):
    pending_quality_check = "pending_quality_check"
    rejected_quality = "rejected_quality"
    pending_match = "pending_match"
    matched = "matched"
    assigned_volunteer = "assigned_volunteer"
    picked_up = "picked_up"
    delivered = "delivered"
    expired = "expired"
    flagged_anomaly = "flagged_anomaly"


class DeliveryStatus(str, enum.Enum):
    planned = "planned"
    en_route = "en_route"
    completed = "completed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(Role), nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, default="")
    lat = Column(Float, default=12.3052)   # default seed near Mysuru, India
    lng = Column(Float, default=76.6552)
    created_at = Column(DateTime, default=datetime.utcnow)

    # role-specific extra fields, kept flat for simplicity (nullable per role)
    trust_score = Column(Float, default=70.0)        # donor: food-quality trust
    ngo_capacity_total = Column(Integer, default=100)
    ngo_capacity_available = Column(Integer, default=100)
    ngo_tier = Column(Integer, default=1)            # 0 basic,1 standard,2 premium
    ngo_has_cold_storage = Column(Boolean, default=False)
    ngo_sentiment_score = Column(Float, default=0.75)  # rolling avg from feedback
    volunteer_capacity_plates = Column(Integer, default=60)
    volunteer_is_available = Column(Boolean, default=True)
    volunteer_rating = Column(Float, default=4.5)     # rolling avg from feedback


class Donation(Base):
    __tablename__ = "donations"
    id = Column(String, primary_key=True, default=gen_id)
    donor_id = Column(String, ForeignKey("users.id"), nullable=False)
    food_type = Column(String, nullable=False)         # rice/curry/bread/mixed/dairy...
    quantity_plates = Column(Integer, nullable=False)
    image_path = Column(String, nullable=True)
    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    pickup_address = Column(String, default="")

    quality_label = Column(String, nullable=True)       # Safe to donate / spoilage risk
    quality_confidence = Column(Float, nullable=True)
    degradation_hours = Column(Float, nullable=True)    # predicted hours until unsafe
    cooked_at = Column(DateTime, default=datetime.utcnow)
    spoil_by = Column(DateTime, nullable=True)

    status = Column(Enum(DonationStatus), default=DonationStatus.pending_quality_check)
    matched_ngo_id = Column(String, ForeignKey("users.id"), nullable=True)
    match_probability = Column(Float, nullable=True)
    match_shap = Column(JSON, nullable=True)
    match_reason = Column(Text, nullable=True)

    anomaly_flag = Column(Boolean, default=False)
    anomaly_probability = Column(Float, nullable=True)
    anomaly_shap = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Delivery(Base):
    __tablename__ = "deliveries"
    id = Column(String, primary_key=True, default=gen_id)
    volunteer_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(DeliveryStatus), default=DeliveryStatus.planned)
    route_geojson = Column(JSON, nullable=True)   # ordered [[lat,lng], ...] polyline
    total_distance_km = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    stops = relationship("DeliveryStop", backref="delivery", order_by="DeliveryStop.sequence")


class DeliveryStop(Base):
    __tablename__ = "delivery_stops"
    id = Column(String, primary_key=True, default=gen_id)
    delivery_id = Column(String, ForeignKey("deliveries.id"), nullable=False)
    donation_id = Column(String, ForeignKey("donations.id"), nullable=False)
    ngo_id = Column(String, ForeignKey("users.id"), nullable=False)
    sequence = Column(Integer, nullable=False)   # 0 = pickup from donor, 1..n = NGO drop-offs
    stop_type = Column(String, default="dropoff")  # "pickup" | "dropoff"
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    eta_minutes = Column(Float, nullable=True)
    status = Column(String, default="pending")   # pending/arrived/completed
    arrived_at = Column(DateTime, nullable=True)


class LocationPing(Base):
    """Latest + historical volunteer GPS pings, for live tracking + trail."""
    __tablename__ = "location_pings"
    id = Column(String, primary_key=True, default=gen_id)
    volunteer_id = Column(String, ForeignKey("users.id"), nullable=False)
    delivery_id = Column(String, ForeignKey("deliveries.id"), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(String, primary_key=True, default=gen_id)
    donation_id = Column(String, ForeignKey("donations.id"), nullable=False)
    from_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    target_type = Column(String, nullable=False)   # "donor" | "volunteer"
    target_id = Column(String, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)        # 1-5
    comment_text = Column(Text, default="")
    sentiment_label = Column(String, nullable=True)
    sentiment_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
