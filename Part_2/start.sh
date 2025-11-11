#!/usr/bin/env bash
# start.sh — Run all MicroChat Medical services with root .venv

# Python path from root
VENV_PY=".venv/bin/python"

# Ports
ORCH_PORT=8001
API_PORT=8000
UI_PORT=7860

echo "▶ Launching orchestrator..."
$VENV_PY -m uvicorn orchestrator.app:app --port $ORCH_PORT --reload &
orch_pid=$!

echo "▶ Launching api-gateway..."
$VENV_PY -m uvicorn api_gateway.app:app --port $API_PORT --reload &
api_pid=$!

echo "▶ Launching frontend..."
$VENV_PY -m fronted.ui_gradio &
ui_pid=$!

echo
echo "✅ All services running!"
echo "Orchestrator → http://127.0.0.1:$ORCH_PORT"
echo "API Gateway  → http://127.0.0.1:$API_PORT"
echo "Frontend UI  → http://127.0.0.1:$UI_PORT"
echo
echo "Press Ctrl+C to stop all."

trap "echo; echo '⛔ Stopping services...'; kill $orch_pid $api_pid $ui_pid 2>/dev/null; exit 0" SIGINT SIGTERM
wait
