"""
Loads all trained model artifacts once at process startup and caches
them in memory for low-latency, real-time inference.
"""
import joblib
from pathlib import Path
from functools import lru_cache

MODELS_DIR = Path(__file__).resolve().parents[3] / "ml" / "models"


@lru_cache(maxsize=1)
def load_anomaly():
    return joblib.load(MODELS_DIR / "anomaly_model.joblib")


@lru_cache(maxsize=1)
def load_matching():
    return joblib.load(MODELS_DIR / "matching_model.joblib")


@lru_cache(maxsize=1)
def load_sentiment():
    return joblib.load(MODELS_DIR / "sentiment_model.joblib")


@lru_cache(maxsize=1)
def load_image_quality():
    return joblib.load(MODELS_DIR / "image_quality_model.joblib")


@lru_cache(maxsize=1)
def load_degradation():
    return joblib.load(MODELS_DIR / "degradation_model.joblib")


def get_all_metrics():
    return {
        "image_quality": load_image_quality()["metrics"],
        "sentiment": load_sentiment()["metrics"],
        "matching": load_matching()["metrics"],
        "anomaly": load_anomaly()["metrics"],
        "degradation": load_degradation()["metrics"],
    }
