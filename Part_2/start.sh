#!/usr/bin/env bash
set -e

echo "▶ Activating virtualenv..."
source .venv/bin/activate

echo "▶ Starting orchestrator (8001)..."
python -m uvicorn Part_2.orchestrator.app:app --port 8001 --reload &

echo "▶ Starting API gateway (8000)..."
python -m uvicorn Part_2.api_gateway.app:app --port 8000 --reload &

echo "▶ Starting frontend (7860)..."
python -m Part_2.fronted.ui_gradio

echo "✅ All services started."
