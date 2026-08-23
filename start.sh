#!/usr/bin/env bash
# FoodBridge AI Platform - one-command local startup (no Docker required)
# Starts the FastAPI backend (DB auto-created + demo accounts seeded) on
# :8000 and the React dashboard on :5173.
set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing backend deps (if needed)..."
cd "$ROOT_DIR/backend"
pip install -q -r requirements.txt

if [ ! -f "$ROOT_DIR/ml/models/anomaly_model.joblib" ]; then
  echo "==> Trained models not found. Training now (one-time, ~30s)..."
  cd "$ROOT_DIR/ml/scripts"
  python3 train_anomaly_model.py
  python3 train_matching_model.py
  python3 train_sentiment_model.py
  python3 train_image_quality_model.py
  python3 train_degradation_model.py
fi

echo "==> Starting backend on http://localhost:8000 (docs at /docs) ..."
echo "    Demo accounts (password: demo1234):"
echo "      admin@foodbridge.demo | donor1@foodbridge.demo | ngo1@foodbridge.demo | volunteer1@foodbridge.demo"
cd "$ROOT_DIR/backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "==> Installing frontend deps (if needed)..."
cd "$ROOT_DIR/frontend"
[ -d node_modules ] || npm install

echo "==> Starting frontend on http://localhost:5173 ..."
npm run dev -- --host

kill $BACKEND_PID 2>/dev/null
