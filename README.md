# FoodBridge AI Platform

A full-stack, real-time food-donation redistribution platform: four
role-based dashboards (**Donor / NGO / Volunteer / Admin**), live map
tracking, multi-stop vehicle routing, and five ML models wired into one
continuous pipeline — from a donor's photo to a delivered plate of food.

```
Donor uploads photo
   │
   ├─► CNN-style quality classifier ──► reject if spoiled
   │
   ├─► Degradation timeline regressor ──► hours-until-unsafe, urgency level
   │
   ├─► Anomaly detector (Isolation Forest + SHAP) ──► flag suspicious donors for admin review
   │
   ├─► NGO assignment engine (XGBoost + SHAP, degradation-aware) ──► best-fit NGO, explained
   │
   └─► Volunteer + multi-stop router (nearest-neighbour + 2-opt) ──► live GPS-tracked delivery
                                                                         │
                                                                         └─► Feedback loop (sentiment model) updates donor trust / NGO sentiment / volunteer rating
```

## Project layout

```
foodbridge/
├── ml/
│   ├── data/                        # your uploaded datasets + generated synthetic data
│   ├── scripts/train_*.py           # 5 training scripts, one per model
│   └── models/*.joblib              # trained artifacts
├── backend/
│   └── app/
│       ├── main.py                  # FastAPI app, all routers wired in
│       ├── models_db.py             # SQLAlchemy schema (users, donations, deliveries, feedback...)
│       ├── auth.py                  # JWT auth + role-based access control
│       ├── seed.py                  # demo accounts (donors/NGOs/volunteers/admin around Mysuru)
│       ├── services/
│       │   ├── quality.py           # image quality + degradation timeline inference
│       │   ├── assignment.py        # NGO matching: XGBoost + SHAP + degradation feasibility filter
│       │   ├── routing.py           # multi-stop consolidation + volunteer assignment
│       │   ├── geo.py                # haversine + nearest-neighbour/2-opt VRP heuristic
│       │   ├── anomaly.py           # Isolation Forest + live SHAP explainer
│       │   ├── behavior.py          # builds donor behavioural features from DB history
│       │   ├── simulate.py          # simulated real-time volunteer GPS movement
│       │   └── ws_manager.py        # WebSocket pub/sub for live tracking
│       └── routers/                 # auth, donor, ngo, volunteer, admin, feedback, ws, + standalone ML
├── frontend/
│   └── src/
│       ├── pages/donor|ngo|volunteer|admin/   # 4 role dashboards
│       ├── components/MapView.jsx   # shared Leaflet map (OpenStreetMap, no API key)
│       ├── hooks/useTrackingSocket.js
│       └── context/AuthContext.jsx
├── docker-compose.yml
└── start.sh                         # one-command local dev startup
```

## Run it

**Local (no Docker)** — requires Python 3.10+, Node 18+:
```bash
./start.sh
```
Backend: http://localhost:8000 (docs at `/docs`) · Frontend: http://localhost:5173

**Docker:**
```bash
docker compose up --build
```
Frontend: http://localhost:3000 · Backend: http://localhost:8000/docs

**Demo accounts** (password for all: `demo1234`), auto-seeded on first backend start:
| Role | Email |
|---|---|
| Admin | admin@foodbridge.demo |
| Donor | donor1@foodbridge.demo, donor2@foodbridge.demo |
| NGO | ngo1@foodbridge.demo (Sparsh), ngo2@foodbridge.demo (Green Hope), ngo3@foodbridge.demo (Akshaya Trust) |
| Volunteer | volunteer1@foodbridge.demo (bike, 40 plates), volunteer2@foodbridge.demo (van, 150 plates) |

## Walkthrough for a demo / viva

1. **Log in as donor1.** Go to "New Donation," attach a food photo, click a
   spot on the map, submit. Watch the response: quality label → predicted
   safe-hours window → matched NGO with a plain-English reason → assigned
   volunteer, all in one request (~1–2s).
2. **Log in as volunteer1** (open a second browser/incognito tab). See the
   assigned delivery with its stop order and ETAs. Click "Start delivery" —
   this launches a simulated real-time GPS feed (or wire a phone to
   `POST /api/volunteer/location` for real GPS in production).
3. **Log in as ngo1.** Watch the donation arrive in "Incoming Donations,"
   confirm receipt once delivered, leave a star rating + comment on the
   donor — this updates the donor's trust score and feeds the sentiment
   model.
4. **Log in as admin.** "Live Map" shows every donor/NGO/volunteer plus the
   volunteer's real-time position (WebSocket-pushed, no polling).
   "Anomaly Queue" shows any donations flagged by the anomaly detector,
   each with a live SHAP explanation, and lets you approve or reject.
5. **Multi-stop routing**: submit a second donation whose pickup point is
   close to an NGO already on an active volunteer's route (same city area,
   compatible capacity) — the assignment engine consolidates it into the
   existing delivery instead of dispatching a new volunteer. Check the
   updated stop list and route polyline.

## The 5 ML models

| Model | Technique | Trained on | Result |
|---|---|---|---|
| Image quality | Transfer-learning-style feature pipeline (color histogram + texture → MLP) | Synthetic proxy dataset (no real photos were supplied — see Limitations) | 99.4% accuracy |
| Degradation timeline | Random Forest regressor | Synthetic dataset generated from USDA/FDA time-temperature food-safety guidance | MAE 1.17 hours, R² 0.976 |
| NGO feedback sentiment | TF-IDF + calibrated Linear SVM | Your `NGO_Feedback_Sentiment` data | 100%* |
| Explainable NGO matching | XGBoost + live SHAP TreeExplainer | Your `Historical_Match_Training` data | 78.2% ROC-AUC |
| Donation anomaly detection | Isolation Forest + Random Forest + live SHAP | Your `donation_anomaly_dataset` | 100% ROC-AUC* |

\* These two datasets are heavily templated/near-perfectly-separable by
construction (see Limitations) — treat as pipeline sanity checks, not
real-world generalization claims.

## What's genuinely novel here (good material for your paper's Contributions section)

- **Degradation-aware NGO assignment**: the matching engine doesn't just
  rank NGOs by fit — it first *excludes* any NGO the volunteer can't
  physically reach before the food's predicted spoilage window closes
  (`services/assignment.py::assign_ngo`, `safety_margin` parameter), then
  ranks the survivors by the SHAP-explainable XGBoost model. This couples
  two otherwise-independent models (image/degradation + matching) into one
  decision.
- **Multi-stop consolidation heuristic**: new donations are checked against
  every currently-active delivery for whether they fit within capacity and
  add only a small detour (nearest-neighbour + 2-opt re-routing cost, see
  `services/routing.py::try_consolidate`) before ever dispatching a new
  volunteer — a lightweight, explainable alternative to a full VRP solver.
- **Semi-supervised anomaly ensemble**: Isolation Forest's unsupervised
  novelty score is fed as an extra feature into a supervised Random Forest
  trained on analyst-reviewed labels, and SHAP explains the supervised
  head live per-donation — the `novel_unseen_pattern` flag in
  `services/anomaly.py` specifically surfaces cases the isolation forest
  considers weird but the supervised model hasn't learned to recognize yet.
- **Closed feedback loop**: NGO ratings of donor food quality and
  donor/admin ratings of volunteer delivery update rolling trust scores
  (`routers/feedback_router.py`) that feed back into the next matching
  decision — trust isn't a static field, it evolves with the platform's use.

## Limitations (put these in your paper — reviewers respect this more than silence)

1. **Templated data**: the sentiment dataset has only ~26 unique comment
   templates repeated 1,000×, and the anomaly labels are cleanly
   separable by construction — both give inflated (100%) test accuracy.
   Retrain on organically collected data before any real deployment claim.
2. **No real food photos**: the image classifier trains on a procedurally
   generated proxy dataset (color/texture cues), not photographs — see
   `ml/scripts/train_image_quality_model.py` docstring for exactly how and
   why, and the "Swapping in a real CNN" section below.
3. **Synthetic degradation timeline**: generated from published food-safety
   *guidance* (USDA 2-hour rule, Bacillus cereus risk for rice dishes),
   not lab-measured spoilage sensors — defensible as a guideline-informed
   proxy, but real TVB-N/gas-sensor data would be stronger for production.
4. **Simulated GPS**: volunteer movement during a delivery is simulated
   (straight-line interpolation at ~25 km/h) unless a real phone posts to
   `POST /api/volunteer/location` — the rest of the system (DB writes,
   WebSocket broadcast, ETA logic) is identical either way.
5. **VRP heuristic, not an exact solver**: nearest-neighbour + 2-opt is a
   standard, citable approximation for small stop counts, not a globally
   optimal solution — fine for a handful of stops per vehicle, would need
   OR-Tools/a proper MILP solver at real fleet scale.

## Swapping in real BERT / a real CNN later

**Sentiment → BERT:**
```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
tok = AutoTokenizer.from_pretrained("bert-base-uncased")
model = AutoModelForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=3)
# fine-tune on NGO_Feedback_Sentiment, then swap load_sentiment() in
# backend/app/utils/model_loader.py for a HF pipeline — routers don't change.
```

**Image quality → MobileNetV2 transfer learning:**
```python
import torch, torchvision
backbone = torchvision.models.mobilenet_v2(weights="IMAGENET1K_V1")
backbone.classifier[1] = torch.nn.Linear(backbone.last_channel, 2)
# fine-tune on real donor photos, then swap classify_image_bytes() in
# backend/app/services/quality.py — the /predict API contract is unchanged.
```

## Environment notes

- Auth: JWT (`python-jose`), bcrypt password hashing, role-based route
  guards (`require_role` in `backend/app/auth.py`).
- Database: SQLite by default (zero-config), swap via `DATABASE_URL` env
  var to Postgres with no code changes (plain SQLAlchemy).
- Maps: Leaflet + OpenStreetMap tiles — no API key needed, works out of
  the box.
- Real-time: native WebSockets (`/ws/track/{channel}`) — one channel per
  delivery for donor/NGO viewers, plus a global `admin` channel for the
  live ops map.
