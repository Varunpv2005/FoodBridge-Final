"""
FoodBridge - Food Spoilage/Risk Estimation Service

Combines image quality classification and degradation timeline prediction
to provide a structured risk assessment with:
- numerical risk score (0-100)
- risk level (Low / Medium / High)
- clear reasons contributing to the score
- recommendation/action

NOTE: This is decision support, not laboratory food-safety certification.
The risk estimation uses the existing image quality model and degradation
timeline model from the quality service.
"""
from typing import Any, Dict, List, Optional

from app.services.quality import predict_degradation


def estimate_risk(
    food_type: str,
    hours_since_cooked: float,
    ambient_temp_c: float,
    has_cold_storage: bool,
    freshness_score: Optional[float] = None,
    quantity_plates: int = 30,
) -> Dict[str, Any]:
    """
    Estimate food spoilage/risk level based on available inputs.

    Args:
        food_type: Type of food (rice, curry, bread, dairy, snacks, mixed)
        hours_since_cooked: Hours elapsed since food was cooked
        ambient_temp_c: Ambient temperature in Celsius
        has_cold_storage: Whether food has cold storage
        freshness_score: Image freshness confidence (0-1), defaults to moderate if not provided
        quantity_plates: Number of plates (informational)

    Returns:
        Dict with:
        - risk_score (0-100)
        - risk_level ('Low', 'Medium', 'High')
        - reasons (list of strings explaining the score)
        - recommendation (string with action to take)
        - hours_remaining (predicted safe hours)
        - spoil_by (estimated spoilage time)
    """
    reasons: List[str] = []
    # 1. TIME FACTOR: How long ago was it cooked?
    if hours_since_cooked < 1:
        time_risk = 5
        reasons.append("Freshly cooked (less than 1 hour ago)")
    elif hours_since_cooked < 2:
        time_risk = 15
        reasons.append("Cooked 1-2 hours ago")
    elif hours_since_cooked < 4:
        time_risk = 35
        reasons.append("Cooked 2-4 hours ago")
    elif hours_since_cooked < 6:
        time_risk = 60
        reasons.append("Cooked 4-6 hours ago")
    else:
        time_risk = min(85, 60 + (hours_since_cooked - 6) * 5)
        reasons.append(f"Cooked {hours_since_cooked:.1f} hours ago")

    # 2. TEMPERATURE FACTOR: Ambient storage conditions
    if ambient_temp_c < 15:
        temp_risk = 5
        reasons.append("Cool ambient temperature (< 15 C) - excellent")
    elif ambient_temp_c < 22:
        temp_risk = 20
        reasons.append(f"Moderate temperature ({ambient_temp_c:.0f} C)")
    elif ambient_temp_c < 30:
        temp_risk = 50
        reasons.append(f"Warm temperature ({ambient_temp_c:.0f} C) - typical room temp")
    elif ambient_temp_c < 38:
        temp_risk = 75
        reasons.append(f"High temperature ({ambient_temp_c:.0f} C) - accelerated spoilage")
    else:
        temp_risk = 90
        reasons.append(f"Very high temperature ({ambient_temp_c:.0f} C) - high risk")

    # 3. COLD STORAGE FACTOR
    if has_cold_storage:
        storage_benefit = 0.5  # Cold storage reduces time/temperature exposure.
        reasons.append("Cold storage available — provides significant protection")
    else:
        storage_benefit = 1.0
        reasons.append("No cold storage — room temperature storage only")

    # 4. FOOD TYPE FACTOR: Baseline spoilage susceptibility
    food_baseline = {
        "rice": 80,  # High risk - Bacillus cereus
        "dairy": 85,  # Highest risk
        "curry": 75,  # High risk
        "mixed": 70,  # Moderate-high
        "snacks": 40,  # Lower risk - dried/fried
        "bread": 30,  # Lowest risk
    }
    type_risk = food_baseline.get(food_type, 70)
    reasons.append(f"{food_type.capitalize()} — baseline spoilage pattern")
    # 5. IMAGE QUALITY / FRESHNESS FACTOR, when a photo has been analyzed.
    if freshness_score is None:
        freshness_risk = None
        reasons.append("No food photo provided; visual freshness was not assessed")
    elif freshness_score < 0.3:
        freshness_risk = 70
        reasons.append("Image indicates visible spoilage risk")
    elif freshness_score < 0.6:
        freshness_risk = 40
        reasons.append("Image shows moderate freshness concerns")
    elif freshness_score < 0.8:
        freshness_risk = 20
        reasons.append("Image indicates reasonably fresh food")
    else:
        freshness_risk = 5
        reasons.append("Image shows excellent freshness")

    # Quantity affects handling exposure, but is deliberately a small factor.
    quantity_risk = min(20, max(0, quantity_plates - 50) / 5)
    if quantity_plates > 50:
        reasons.append(f"Large donation quantity ({quantity_plates} plates) may increase handling exposure")

    # CALCULATE COMPOSITE RISK SCORE
    # Transparent weighted score; photo evidence is included only when available.
    weighted_risk = (
        time_risk * 0.25 +
        temp_risk * 0.25 +
        type_risk * 0.20 +
        (freshness_risk * 0.20 if freshness_risk is not None else 0) +
        (time_risk + temp_risk) * 0.10 +
        quantity_risk * 0.05
    ) * storage_benefit

    # Clamp to 0-100 and round
    risk_score = min(100, max(0, round(weighted_risk)))

    # 6. PREDICT REMAINING HOURS using the existing degradation model.
    model_freshness_score = freshness_score if freshness_score is not None else 0.5
    try:
        degradation = predict_degradation(
            food_type, freshness_score, hours_since_cooked, ambient_temp_c, has_cold_storage
        )
        hours_remaining = degradation["hours_remaining"]
        spoil_by = degradation["spoil_by"]
        urgency = degradation["urgency"]

        if hours_remaining < 1:
            reasons.append("URGENT: Less than 1 hour remaining")
        elif hours_remaining < 3:
            reasons.append(f"High priority: ~{hours_remaining:.1f} hours remaining")
        elif hours_remaining < 6:
            reasons.append(f"Moderate priority: ~{hours_remaining:.1f} hours remaining")
        else:
            reasons.append(f"Good safety window: ~{hours_remaining:.1f} hours remaining")
    except Exception:
        hours_remaining = None
        spoil_by = None
        urgency = None

    # 7. DETERMINE RISK LEVEL & RECOMMENDATION
    if risk_score < 30:
        risk_level = "Low"
        recommendation = (
            "This donation has lower estimated risk based on the provided details. "
            "Proceed with standard pickup, handling, and distribution checks."
        )
    elif risk_score < 60:
        risk_level = "Medium"
        recommendation = (
            "This donation has moderate estimated risk. Prioritize matching with nearby NGOs "
            "to minimize transit time. Use cold storage if available during transport."
        )
    else:
        risk_level = "High"
        recommendation = (
            "This donation has high estimated risk of spoilage. Immediate action required: "
            "prioritize this donation for urgent pickup and delivery to the nearest NGO with "
            "cold storage capability. Consider rejection if remaining safe window is < 1 hour."
        )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "reasons": reasons,
        "recommendation": recommendation,
        "hours_remaining": hours_remaining,
        "spoil_by": spoil_by,
        "urgency": urgency,
    }
