from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import Base, engine
from app.seed import seed
from app.routers import (
    anomaly, matching, sentiment, image_quality, health,
    auth_router, donor, ngo_router, volunteer_router, admin_router,
    feedback_router, ws_router,
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
