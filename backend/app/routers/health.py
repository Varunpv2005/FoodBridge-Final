from fastapi import APIRouter
from app.utils.model_loader import get_all_metrics

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/api/metrics")
def metrics():
    """Return training metrics for all 4 models -- handy for the frontend
    dashboard and for the conference-paper results table."""
    return get_all_metrics()
