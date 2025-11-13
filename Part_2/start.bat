@echo off
SETLOCAL

set VENV_PY=.\.venv\Scripts\python.exe

if not exist %VENV_PY% (
    echo ❌ Virtualenv not found at %VENV_PY%
    echo Run: python -m venv .venv
    exit /b 1
)

echo ▶ Starting orchestrator (8001)...
start "orchestrator" cmd /k %VENV_PY% -m uvicorn Part_2.orchestrator.app:app --port 8001 --reload

echo ▶ Starting API gateway (8000)...
start "api-gateway" cmd /k %VENV_PY% -m uvicorn Part_2.api_gateway.app:app --port 8000 --reload

echo ▶ Starting frontend (7860)...
%VENV_PY% -m Part_2.fronted.ui_gradio

echo ✅ All services started.
