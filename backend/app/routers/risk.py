"""
Risk Estimation API endpoint.

Exposes food spoilage/risk estimation as a standalone decision support tool.
Uses the same degradation model and quality classifiers that are integrated
into the donation creation flow, but packaged for independent analysis.
"""
from fastapi import APIRouter, HTTPException
from app.schemas import RiskEstimationRequest, RiskEstimationResponse
from app.services.risk import estimate_risk

router = APIRouter()


@router.post("/estimate", response_model=RiskEstimationResponse)
def estimate_food_risk(req: RiskEstimationRequest):
    """
    Estimate food spoilage/risk level based on food characteristics and storage conditions.

    **Decision Support Only:** This is not laboratory food-safety certification.
    Use as guidance to prioritize donation handling and routing.

    **Inputs:**
    - food_type: rice | curry | bread | dairy | snacks | mixed
    - hours_since_cooked: Time elapsed since cooking (0-48 hours)
    - ambient_temp_c: Storage temperature in Celsius
    - has_cold_storage: Whether food has refrigeration/insulation
    - freshness_score: Image quality confidence (0-1), optional
    - quantity_plates: Number of plates (informational)

    **Outputs:**
    - risk_score: 0-100 (higher = more risk)
    - risk_level: Low | Medium | High
    - reasons: List of factors contributing to the risk assessment
    - recommendation: Action to take
    - hours_remaining: Predicted safe window (from degradation model)
    - spoil_by: Estimated time when food becomes unsafe
    - urgency: critical | high | moderate | low
    """
    try:
        result = estimate_risk(
            food_type=req.food_type,
            hours_since_cooked=req.hours_since_cooked,
            ambient_temp_c=req.ambient_temp_c,
            has_cold_storage=req.has_cold_storage,
            freshness_score=req.freshness_score,
            quantity_plates=req.quantity_plates,
        )
        # Convert datetime to ISO string for JSON serialization
        if result.get("spoil_by"):
            result["spoil_by"] = result["spoil_by"].isoformat()
        return RiskEstimationResponse(**result)
    except Exception as e:
        raise HTTPException(500, f"Risk estimation failed: {str(e)}")
