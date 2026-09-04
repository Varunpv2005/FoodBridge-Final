from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = Field(..., pattern="^(donor|ngo|volunteer|admin)$")
    phone: str = ""
    lat: float = 12.3052
    lng: float = 76.6552
    # NGO-only
    ngo_capacity_total: Optional[int] = 100
    ngo_has_cold_storage: Optional[bool] = False
    ngo_tier: Optional[int] = 1
    # Volunteer-only
    volunteer_capacity_plates: Optional[int] = 60


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


# ---------- Donation ----------
class DonationCreateMeta(BaseModel):
    food_type: str = Field(..., pattern="^(rice|curry|bread|mixed|dairy|snacks)$")
    quantity_plates: int = Field(..., gt=0)
    pickup_lat: float
    pickup_lng: float
    pickup_address: str = ""
    hours_since_cooked: float = 0.5
    ambient_temp_c: float = 30.0
    has_cold_storage: bool = False


class DonationOut(BaseModel):
    id: str
    donor_id: str
    donor_name: Optional[str] = None
    food_type: str
    quantity_plates: int
    status: str
    quality_label: Optional[str]
    quality_confidence: Optional[float]
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    risk_reasons: Optional[List[str]] = None
    risk_recommendation: Optional[str] = None
    degradation_hours: Optional[float]
    spoil_by: Optional[datetime]
    matched_ngo_id: Optional[str]
    match_probability: Optional[float]
    match_reason: Optional[str]
    match_factors: Optional[Dict[str, float]] = None
    match_explanation: Optional[List[str]] = None
    match_shap: Optional[Dict[str, float]] = None
    anomaly_flag: bool
    anomaly_probability: Optional[float] = None
    anomaly_shap: Optional[Dict[str, float]] = None
    pickup_lat: float
    pickup_lng: float
    pickup_address: Optional[str] = ""
    image_path: Optional[str] = None
    created_at: datetime
    delivery_id: Optional[str] = None
    delivery_status: Optional[str] = None
    volunteer_id: Optional[str] = None
    volunteer_name: Optional[str] = None
    matched_ngo_name: Optional[str] = None
    matched_ngo_lat: Optional[float] = None
    matched_ngo_lng: Optional[float] = None
    delivery_route: Optional[Any] = None
    delivery_distance_km: Optional[float] = None
    delivery_travel_minutes: Optional[float] = None
    delivery_urgent_stop_count: int = 0
    delivery_late_stop_count: int = 0
    delivery_eta_minutes: Optional[float] = None
    latest_location_lat: Optional[float] = None
    latest_location_lng: Optional[float] = None
    latest_location_timestamp: Optional[datetime] = None
    delivery_completed_at: Optional[datetime] = None
    delivery_stops: Optional[List[Dict[str, Any]]] = None
    ngo_request_status: Optional[str] = None
    ngo_request_history: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


# ---------- Feedback ----------
class FeedbackCreate(BaseModel):
    donation_id: str
    target_type: str = Field(..., pattern="^(donor|volunteer)$")
    target_id: str
    rating: int = Field(..., ge=1, le=5)
    comment_text: str = ""


class FeedbackOut(BaseModel):
    id: str
    donation_id: str
    target_type: str
    target_id: str
    rating: int
    comment_text: str
    sentiment_label: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Delivery ----------
class DeliveryStopOut(BaseModel):
    id: str
    donation_id: str
    ngo_id: str
    sequence: int
    stop_type: str
    lat: float
    lng: float
    eta_minutes: Optional[float]
    estimated_arrival: Optional[str] = None
    food_window_deadline: Optional[str] = None
    remaining_food_window_minutes: Optional[float] = None
    lateness_minutes: Optional[float] = None
    urgency: Optional[str] = None
    risk_score: Optional[float] = None
    status: str
    food_type: Optional[str] = None
    quantity_plates: Optional[int] = None
    donor_name: Optional[str] = None
    pickup_address: Optional[str] = None
    ngo_name: Optional[str] = None

    class Config:
        from_attributes = True


class BaselineExperimentCreate(BaseModel):
    started_at: datetime
    ended_at: Optional[datetime] = None
    successful: bool
    ngo_request_count: int = 1
    fallback_count: int = 0
    route_distance_km: Optional[float] = None
    route_duration_minutes: Optional[float] = None


class DeliveryOut(BaseModel):
    id: str
    volunteer_id: str
    status: str
    route_geojson: Optional[Any]
    total_distance_km: float
    estimated_travel_minutes: Optional[float] = None
    urgent_stop_count: int = 0
    expected_late_stop_count: int = 0
    route_error: Optional[str] = None
    latest_location_lat: Optional[float] = None
    latest_location_lng: Optional[float] = None
    latest_location_timestamp: Optional[datetime] = None
    stops: List[DeliveryStopOut]
    created_at: datetime

    class Config:
        from_attributes = True


class LocationUpdate(BaseModel):
    lat: float
    lng: float
    accuracy: Optional[float] = None
    timestamp: Optional[datetime] = None
    delivery_id: Optional[str] = None
    volunteer_id: Optional[str] = None
