#!/usr/bin/env bash
# FoodBridge AI Platform - one-command local startup (no Docker required)
# Starts the FastAPI backend (DB auto-created + demo accounts seeded) on
# :8000 and the React dashboard on :5173.
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON_BIN="${ROOT_DIR}/.venv/Scripts/python.exe"

if [ ! -f "$PYTHON_BIN" ]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi
if [ ! -f "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi

if [ -z "${PYTHON_BIN:-}" ] || { [ ! -f "$PYTHON_BIN" ] && [ ! -x "$PYTHON_BIN" ]; }; then
  echo "Python interpreter not found. Activate a virtual environment or install Python 3 first."
  exit 1
fi

echo "==> Installing backend deps (if needed)..."
cd "$BACKEND_DIR"
"$PYTHON_BIN" -m pip install -q -r requirements.txt

if [ ! -f "$ROOT_DIR/ml/models/anomaly_model.joblib" ]; then
  echo "==> Trained models not found. Training now (one-time, ~30s)..."
  cd "$ROOT_DIR/ml/scripts"
  "$PYTHON_BIN" train_anomaly_model.py
  "$PYTHON_BIN" train_matching_model.py
  "$PYTHON_BIN" train_sentiment_model.py
  "$PYTHON_BIN" train_image_quality_model.py
  "$PYTHON_BIN" train_degradation_model.py
fi

echo "==> Starting backend on http://localhost:8000 (docs at /docs) ..."
echo "    Demo accounts (password: demo1234):"
echo "      admin@foodbridge.demo | donor1@foodbridge.demo | ngo1@foodbridge.demo | volunteer1@foodbridge.demo"
cd "$BACKEND_DIR"
"$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "==> Installing frontend deps (if needed)..."
cd "$FRONTEND_DIR"
[ -d node_modules ] || npm install

echo "==> Starting frontend on http://localhost:5173 ..."
npm run dev -- --host --strictPort

wait "$BACKEND_PID"
