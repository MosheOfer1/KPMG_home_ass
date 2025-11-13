@echo off
echo ⏹ Stopping all services...

echo Looking for processes using ports 8000, 8001, 7860...

for %%p in (8000 8001 7860) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%p ^| findstr LISTENING') do (
        echo Killing PID %%a on port %%p...
        taskkill /PID %%a /F >nul 2>&1
    )
)

echo.
echo Checking for zombie python processes (ui_gradio, uvicorn)...

for /f "tokens=2 delims=," %%a in ('tasklist /FI "IMAGENAME eq python.exe" /v ^| findstr /i "Part_2"') do (
    echo Killing python.exe PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo ✅ All services stopped.
