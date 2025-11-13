#!/usr/bin/env bash
echo "⏹ Stopping all services..."
pkill -f "uvicorn Part_2" || true
pkill -f "ui_gradio" || true
echo "✅ All services stopped."
