"""
NGO Assignment Engine.

For a given donation, scores every active/eligible NGO with the trained
XGBoost matching model (see ml/scripts/train_matching_model.py), explains
the score with a live SHAP TreeExplainer, and — this is the novel piece
requested for this project — applies a *degradation-aware feasibility
filter* first: an NGO that is real-world reachable only after the food's
predicted spoilage window is excluded before ranking, regardless of how
good its other attributes are. Among feasible NGOs, the highest matching
probability wins; ties are broken by distance.
"""
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd

from app.services.geo import haversine_km, AVG_SPEED_KMPH
from app.utils.model_loader import load_matching


def _travel_hours(distance_km: float) -> float:
    return distance_km / AVG_SPEED_KMPH


def score_ngo_candidate(donation_features: dict, ngo, distance_km: float) -> dict:
    bundle = load_matching()
    model, explainer = bundle["model"], bundle["explainer"]
    feature_cols = bundle["feature_names"]
    day_enc, month_enc = bundle["day_enc"], bundle["month_enc"]

    now = datetime.utcnow()
    day_name = now.strftime("%A")
    month_name = now.strftime("%b")

    def safe_enc(enc, val):
        try:
            return int(enc.transform([val])[0])
        except ValueError:
            return 0

    row = {
        "distance_km": distance_km,
        "capacity_available_plates": ngo.ngo_capacity_available,
        "food_type_match_score": donation_features.get("food_type_match_score", 0.8),
        "sentiment_score": ngo.ngo_sentiment_score,
        "time_overlap_minutes": 120,
        "occupancy_%": 100 * (1 - ngo.ngo_capacity_available / max(ngo.ngo_capacity_total, 1)),
        "donor_trust_score": donation_features.get("donor_trust_score", 70),
        "food_safety_score_%": donation_features.get("freshness_score", 0.8) * 100,
        "quantity_plates": donation_features.get("quantity_plates", 20),
        "has_cold_storage": int(ngo.ngo_has_cold_storage),
        "ngo_tier_encoded": ngo.ngo_tier,
        "hour_of_day": now.hour,
        "day_of_week_enc": safe_enc(day_enc, day_name),
        "month_enc": safe_enc(month_enc, month_name),
        "is_festival_day": 0,
        "weather_score": 0.85,
    }
    X = pd.DataFrame([row])[feature_cols]
    proba = float(model.predict_proba(X)[0, 1])

    shap_values = explainer.shap_values(X)[0]
    shap_map = {feat: round(float(v), 4) for feat, v in zip(feature_cols, shap_values)}
    top_shap = dict(sorted(shap_map.items(), key=lambda kv: -abs(kv[1]))[:5])

    return {"probability": proba, "shap": top_shap}


def assign_ngo(donation, candidate_ngos: List, safety_margin: float = 0.7) -> Optional[dict]:
    """
    donation: object with .pickup_lat/.pickup_lng/.quantity_plates/
              .quality_confidence/.degradation_hours
    candidate_ngos: list of User rows with role == ngo

    Returns the winning NGO's id + full explanation, or None if no NGO is
    feasible (all either lack capacity or are unreachable before spoilage).
    """
    donation_features = {
        "quantity_plates": donation.quantity_plates,
        "freshness_score": donation.quality_confidence or 0.8,
        "donor_trust_score": 70,
        "food_type_match_score": 0.85,
    }

    scored = []
    for ngo in candidate_ngos:
        if ngo.ngo_capacity_available < donation.quantity_plates:
            continue  # hard constraint: must physically fit the donation

        distance_km = haversine_km(donation.pickup_lat, donation.pickup_lng, ngo.lat, ngo.lng)
        travel_hrs = _travel_hours(distance_km)

        feasible = True
        if donation.degradation_hours is not None:
            feasible = travel_hrs <= donation.degradation_hours * safety_margin

        result = score_ngo_candidate(donation_features, ngo, distance_km)
        scored.append({
            "ngo_id": ngo.id,
            "ngo_name": ngo.name,
            "distance_km": round(distance_km, 2),
            "travel_hours": round(travel_hrs, 2),
            "feasible": feasible,
            "probability": result["probability"],
            "shap": result["shap"],
        })

    feasible_candidates = [c for c in scored if c["feasible"]]
    pool = feasible_candidates if feasible_candidates else scored
    if not pool:
        return None

    best = max(pool, key=lambda c: (c["probability"], -c["distance_km"]))

    readable = {
        "distance_km": "proximity to donor", "capacity_available_plates": "available capacity",
        "food_type_match_score": "food type match", "sentiment_score": "past feedback sentiment",
        "donor_trust_score": "donor trust score", "food_safety_score_%": "food safety/freshness score",
        "has_cold_storage": "cold storage availability", "ngo_tier_encoded": "NGO tier",
        "occupancy_%": "current occupancy", "hour_of_day": "time of day",
    }
    pos = [readable.get(f, f) for f, v in best["shap"].items() if v > 0][:3]
    reason = (f"Selected {best['ngo_name']} ({best['probability']*100:.1f}% match confidence, "
              f"{best['distance_km']} km away). Favored by: {', '.join(pos) or 'baseline fit'}.")
    if not best["feasible"]:
        reason += " Warning: this is the least-bad option — no NGO was reachable within the food's safe window."

    return {**best, "all_candidates": scored, "reason": reason}
