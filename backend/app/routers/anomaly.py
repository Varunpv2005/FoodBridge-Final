import numpy as np
import pandas as pd
from fastapi import APIRouter
from app.schemas import AnomalyRequest, AnomalyResponse
from app.utils.model_loader import load_anomaly

router = APIRouter()

_FIELD_MAP = {
    "quantity_plates": "Quantity Plates", "session_duration_sec": "Session Duration Sec",
    "account_age_days": "Account Age Days", "donations_per_week": "Donations Per Week",
    "avg_quantity_plates": "Avg Quantity Plates", "std_quantity": "Std Quantity",
    "hour_std_dev": "Hour Std Dev", "location_variance_m": "Location Variance M",
    "expiry_fill_rate": "Expiry Fill Rate", "pickup_rate": "Pickup Rate",
    "inter_donation_gap_min": "Inter Donation Gap Min", "unique_devices_used": "Unique Devices Used",
    "unique_ip_count": "Unique Ip Count", "hour_of_day": "Hour Of Day", "day_of_week": "Day Of Week",
    "donations_last_1hr": "Donations Last 1Hr", "donations_last_3hr": "Donations Last 3Hr",
    "donations_last_24hr": "Donations Last 24Hr",
    "time_since_last_donation_min": "Time Since Last Donation Min",
    "rolling_avg_7day": "Rolling Avg 7Day", "deviation_from_avg": "Deviation From Avg",
    "distance_from_centroid_m": "Distance From Centroid M", "gps_accuracy_m": "Gps Accuracy M",
    "location_count_24hr": "Location Count 24Hr", "volunteer_views": "Volunteer Views",
    "pickup_attempts": "Pickup Attempts", "has_expiry": "has_expiry",
    "is_expired_or_flagged": "is_expired_or_flagged", "is_weekend": "Is Weekend",
    "is_night_submission": "Is Night Submission",
    "is_same_location_repeated": "Is Same Location Repeated",
    "is_residential_area": "Is Residential Area", "successful_pickup": "Successful Pickup",
    "expiry_before_pickup": "Expiry Before Pickup",
}


@router.post("/predict", response_model=AnomalyResponse)
def predict_anomaly(req: AnomalyRequest):
    bundle = load_anomaly()
    iso, rf, scaler = bundle["iso_forest"], bundle["rf"], bundle["scaler"]
    feature_cols = bundle["feature_names"]

    payload = req.dict()
    row = {}
    for py_field, xl_col in _FIELD_MAP.items():
        val = payload[py_field]
        row[xl_col] = int(val) if isinstance(val, bool) else val

    X = pd.DataFrame([row])[feature_cols]
    Xs = scaler.transform(X)

    iso_raw = -iso.score_samples(Xs)[0]
    iso_pred = iso.predict(Xs)[0]  # -1 anomaly, 1 normal
    Xs_aug = np.hstack([Xs, [[iso_raw]]])

    proba = float(rf.predict_proba(Xs_aug)[0, 1])
    is_anomaly = proba >= 0.5

    importances = rf.feature_importances_
    contrib = dict(sorted(
        zip(feature_cols + ["iso_forest_score"], importances.tolist()),
        key=lambda kv: -kv[1]
    )[:5])

    if is_anomaly:
        rec = "Hold for manual admin review before dispatch."
    elif iso_pred == -1:
        rec = "Borderline: unusual pattern detected but below the anomaly threshold. Monitor."
    else:
        rec = "Normal donation pattern. Auto-approve."

    return AnomalyResponse(
        is_anomaly=is_anomaly,
        anomaly_probability=round(proba, 4),
        isolation_forest_score=round(float(iso_raw), 4),
        top_contributing_features={k: round(v, 4) for k, v in contrib.items()},
        recommendation=rec,
    )
