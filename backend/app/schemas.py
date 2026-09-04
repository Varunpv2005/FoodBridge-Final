from pydantic import BaseModel, Field
from typing import List, Optional


class SentimentRequest(BaseModel):
    comment_text: str = Field(..., example="Food arrived late and was cold.")


class SentimentResponse(BaseModel):
    label: str
    confidence: float
    probabilities: dict


class MatchingRequest(BaseModel):
    distance_km: float = Field(..., example=2.0)
    capacity_available_plates: int = Field(..., example=50)
    food_type_match_score: float = Field(..., ge=0, le=1, example=0.9)
    sentiment_score: float = Field(..., ge=0, le=1, example=0.8)
    time_overlap_minutes: int = Field(..., example=120)
    occupancy_pct: float = Field(..., ge=0, le=100, example=40.0)
    donor_trust_score: float = Field(..., example=75)
    food_safety_score_pct: float = Field(..., ge=0, le=100, example=90.0)
    quantity_plates: int = Field(..., example=50)
    has_cold_storage: bool = Field(..., example=True)
    ngo_tier_encoded: int = Field(..., example=1)
    hour_of_day: int = Field(..., ge=0, le=23, example=14)
    day_of_week: str = Field(..., example="Monday")
    month: str = Field(..., example="Jan")
    is_festival_day: bool = Field(False)
    weather_score: float = Field(..., ge=0, le=1, example=0.9)


class MatchingResponse(BaseModel):
    match_success_probability: float
    recommendation: str
    shap_explanation: dict
    plain_english_reason: str


class AnomalyRequest(BaseModel):
    quantity_plates: int = Field(..., example=45)
    session_duration_sec: int = Field(..., example=120)
    account_age_days: int = Field(..., example=400)
    donations_per_week: float = Field(..., example=3.0)
    avg_quantity_plates: float = Field(..., example=40.0)
    std_quantity: float = Field(..., example=10.0)
    hour_std_dev: float = Field(..., example=3.0)
    location_variance_m: float = Field(..., example=500.0)
    expiry_fill_rate: float = Field(..., ge=0, le=1, example=0.9)
    pickup_rate: float = Field(..., ge=0, le=1, example=0.7)
    inter_donation_gap_min: float = Field(..., example=3000.0)
    unique_devices_used: int = Field(..., example=1)
    unique_ip_count: int = Field(..., example=1)
    hour_of_day: int = Field(..., ge=0, le=23, example=13)
    day_of_week: int = Field(..., ge=0, le=6, example=2)
    donations_last_1hr: int = Field(..., example=0)
    donations_last_3hr: int = Field(..., example=1)
    donations_last_24hr: int = Field(..., example=2)
    time_since_last_donation_min: float = Field(..., example=1500.0)
    rolling_avg_7day: float = Field(..., example=3.0)
    deviation_from_avg: float = Field(..., example=0.5)
    distance_from_centroid_m: float = Field(..., example=800.0)
    gps_accuracy_m: float = Field(..., example=30.0)
    location_count_24hr: int = Field(..., example=2)
    volunteer_views: int = Field(..., example=3)
    pickup_attempts: int = Field(..., example=1)
    has_expiry: bool = Field(True)
    is_expired_or_flagged: bool = Field(False)
    is_weekend: bool = Field(False)
    is_night_submission: bool = Field(False)
    is_same_location_repeated: bool = Field(False)
    is_residential_area: bool = Field(True)
    successful_pickup: bool = Field(True)
    expiry_before_pickup: bool = Field(False)


class AnomalyResponse(BaseModel):
    is_anomaly: bool
    anomaly_probability: float
    isolation_forest_score: float
    top_contributing_features: dict
    recommendation: str


class ImageQualityResponse(BaseModel):
    label: str
    confidence: float
    recommendation: str


class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    language: str = Field("en", pattern="^(en|hi|kn)$")


class AssistantResponse(BaseModel):
    language: str
    intent: str
    reply: str


class DemandForecastPoint(BaseModel):
    forecast_date: str
    predicted_demand: float
    xgboost_prediction: float
    lstm_prediction: float


class DemandForecastResponse(BaseModel):
    region: str
    food_type: str
    model_weights: dict
    forecasts: List[DemandForecastPoint]
    metrics: dict
    data_source: str
    sequence_length: int


class RiskEstimationRequest(BaseModel):
    food_type: str = Field(..., pattern="^(rice|curry|bread|dairy|snacks|mixed)$", example="rice")
    hours_since_cooked: float = Field(..., ge=0, le=48, example=2.0)
    ambient_temp_c: float = Field(..., ge=-10, le=50, example=30.0)
    has_cold_storage: bool = Field(False, example=False)
    freshness_score: Optional[float] = Field(None, ge=0, le=1, example=0.75)
    quantity_plates: int = Field(30, ge=1, le=1000, example=30)


class RiskEstimationResponse(BaseModel):
    risk_score: int = Field(..., ge=0, le=100, example=45)
    risk_level: str = Field(..., pattern="^(Low|Medium|High)$", example="Medium")
    reasons: List[str] = Field(..., example=["Cooked 2-4 hours ago", "Warm temperature (30 C)"])
    recommendation: str
    hours_remaining: Optional[float] = None
    spoil_by: Optional[str] = None
    urgency: Optional[str] = None
