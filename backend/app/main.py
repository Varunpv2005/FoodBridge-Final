from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.db import Base, engine
from app.seed import seed
from app.routers import (
    anomaly, matching, sentiment, image_quality, health, risk, demand, assistant,
    auth_router, donor, ngo_router, volunteer_router, admin_router,
    feedback_router, ws_router, tts,
)

app = FastAPI(
    title="FoodBridge AI Platform",
    description="Full-stack, real-time food-donation redistribution platform: "
                 "role-based dashboards (donor/NGO/volunteer/admin), live map "
                 "tracking, multi-stop routing, and 5 ML models (image quality, "
                 "degradation timeline, explainable NGO matching, sentiment, anomaly).",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    delivery_columns = {column["name"] for column in inspector.get_columns("deliveries")}
    experiment_columns = {column["name"] for column in inspector.get_columns("experiment_records")}
    with engine.begin() as connection:
        if "current_session_id" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN current_session_id VARCHAR(128)"))
        for name, definition in {
            "estimated_travel_minutes": "FLOAT",
            "urgent_stop_count": "INTEGER DEFAULT 0",
            "expected_late_stop_count": "INTEGER DEFAULT 0",
            "route_error": "TEXT",
            "route_deviated": "BOOLEAN DEFAULT 0",
            "route_deviation_at": "DATETIME",
            "route_recalculated_at": "DATETIME",
        }.items():
            if name not in delivery_columns:
                connection.execute(text(f"ALTER TABLE deliveries ADD COLUMN {name} {definition}"))
        for name, definition in {
            "is_controlled_trial": "BOOLEAN DEFAULT 0",
            "trial_id": "VARCHAR(64)",
        }.items():
            if name not in experiment_columns:
                connection.execute(text(f"ALTER TABLE experiment_records ADD COLUMN {name} {definition}"))
    seed()


import os
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --- Platform routers (DB-backed, role-based) ---
app.include_router(auth_router.router, prefix="/api/auth", tags=["Auth"])
app.include_router(donor.router, prefix="/api/donor", tags=["Donor"])
app.include_router(ngo_router.router, prefix="/api/ngo", tags=["NGO"])
app.include_router(volunteer_router.router, prefix="/api/volunteer", tags=["Volunteer"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["Admin"])
app.include_router(feedback_router.router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(ws_router.router, tags=["Realtime"])

# --- Standalone ML inference routers (stateless, usable independent of the DB flow) ---
app.include_router(health.router, tags=["Health"])
app.include_router(image_quality.router, prefix="/api/ml/image-quality", tags=["ML: Image Quality"])
app.include_router(sentiment.router, prefix="/api/ml/sentiment", tags=["ML: Sentiment"])
app.include_router(matching.router, prefix="/api/ml/matching", tags=["ML: Matching (SHAP)"])
app.include_router(anomaly.router, prefix="/api/ml/anomaly", tags=["ML: Anomaly"])
app.include_router(risk.router, prefix="/api/ml/risk", tags=["ML: Spoilage Risk"])
app.include_router(demand.router, prefix="/api/ml/demand", tags=["ML: Demand Forecast"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["Assistant"])
app.include_router(tts.router, prefix="/api/tts", tags=["Text to speech"])


@app.get("/")
def root():
    return {
        "service": "FoodBridge AI Platform",
        "docs": "/docs",
        "demo_login": {"password": "demo1234", "emails": [
            "admin@foodbridge.demo", "donor1@foodbridge.demo",
            "ngo1@foodbridge.demo", "volunteer1@foodbridge.demo",
        ]},
    }
