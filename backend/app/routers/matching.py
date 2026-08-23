import pandas as pd
from fastapi import APIRouter
from app.schemas import MatchingRequest, MatchingResponse
from app.utils.model_loader import load_matching

router = APIRouter()


def _safe_label_transform(encoder, value: str) -> int:
    """Fall back to the most frequent class if an unseen category is sent."""
    try:
        return int(encoder.transform([value])[0])
    except ValueError:
        return 0


@router.post("/predict", response_model=MatchingResponse)
def predict_matching(req: MatchingRequest):
    bundle = load_matching()
    model, explainer = bundle["model"], bundle["explainer"]
    feature_cols = bundle["feature_names"]
    day_enc, month_enc = bundle["day_enc"], bundle["month_enc"]

    row = {
        "distance_km": req.distance_km,
        "capacity_available_plates": req.capacity_available_plates,
        "food_type_match_score": req.food_type_match_score,
        "sentiment_score": req.sentiment_score,
        "time_overlap_minutes": req.time_overlap_minutes,
        "occupancy_%": req.occupancy_pct,
        "donor_trust_score": req.donor_trust_score,
        "food_safety_score_%": req.food_safety_score_pct,
        "quantity_plates": req.quantity_plates,
        "has_cold_storage": int(req.has_cold_storage),
        "ngo_tier_encoded": req.ngo_tier_encoded,
        "hour_of_day": req.hour_of_day,
        "day_of_week_enc": _safe_label_transform(day_enc, req.day_of_week),
        "month_enc": _safe_label_transform(month_enc, req.month),
        "is_festival_day": int(req.is_festival_day),
        "weather_score": req.weather_score,
    }
    X = pd.DataFrame([row])[feature_cols]

    proba = float(model.predict_proba(X)[0, 1])
    shap_values = explainer.shap_values(X)[0]
    shap_map = {feat: round(float(v), 4) for feat, v in zip(feature_cols, shap_values)}
    top_shap = dict(sorted(shap_map.items(), key=lambda kv: -abs(kv[1]))[:5])

    recommendation = "Recommend match" if proba >= 0.5 else "Do not recommend / seek alternative NGO"

    pos = [f for f, v in top_shap.items() if v > 0][:3]
    neg = [f for f, v in top_shap.items() if v < 0][:2]
    readable = {
        "distance_km": "proximity to donor", "capacity_available_plates": "available capacity",
        "food_type_match_score": "food type match", "sentiment_score": "past feedback sentiment",
        "time_overlap_minutes": "pickup time window fit", "occupancy_%": "current occupancy",
        "donor_trust_score": "donor trust score", "food_safety_score_%": "food safety score",
        "quantity_plates": "donation quantity", "has_cold_storage": "cold storage availability",
        "ngo_tier_encoded": "NGO tier", "hour_of_day": "time of day", "day_of_week_enc": "day of week",
        "month_enc": "month/seasonality", "is_festival_day": "festival-day demand",
        "weather_score": "weather conditions",
    }
    reason_parts = [readable.get(f, f) for f in pos]
    penalty_parts = [readable.get(f, f) for f in neg]
    reason = f"Match confidence {proba*100:.1f}%. Favored by: {', '.join(reason_parts) or 'no strong positive factor'}."
    if penalty_parts:
        reason += f" Reduced by: {', '.join(penalty_parts)}."

    return MatchingResponse(
        match_success_probability=round(proba, 4),
        recommendation=recommendation,
        shap_explanation=top_shap,
        plain_english_reason=reason,
    )
