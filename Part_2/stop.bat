@echo off
SETLOCAL

echo ⏹ Stopping all services...

REM Kill uvicorn processes running our modules
for /f "tokens=2 delims= " %%a in ('tasklist /fi "imagename eq python.exe" /v ^| findstr /i "uvicorn Part_2"') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM Kill Gradio frontend
for /f "tokens=2 delims= " %%a in ('tasklist /fi "imagename eq python.exe" /v ^| findstr /i "ui_gradio"') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo ✅ All services stopped.
