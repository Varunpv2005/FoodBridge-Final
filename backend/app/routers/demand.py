from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas import DemandForecastResponse
from app.services.demand_forecasting import forecast_demand

router = APIRouter()


@router.get("/forecast", response_model=DemandForecastResponse)
def get_demand_forecast(
    horizon: int = Query(7, ge=1, le=14),
    region: Optional[str] = Query(None),
    food_type: Optional[str] = Query(None),
):
    """Return the persisted XGBoost/LSTM demand forecast.

    The current artifact is trained on aggregate request volume. Region and
    food-type filters are rejected until enough history exists for segment
    models, avoiding unsupported or fabricated forecasts.
    """
    try:
        return forecast_demand(horizon=horizon, region=region, food_type=food_type)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, "Demand forecast model is not trained yet.") from exc