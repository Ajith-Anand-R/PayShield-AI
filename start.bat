@echo off
title PayShield Orchestrator
color 0b

echo =================================================================
echo                 PAYSHIELD LAUNCH ORCHESTRATOR
echo =================================================================
echo.
echo PayShield is starting both engines:
echo  1. FastAPI Risk scoring engine (port 8001)
echo  2. Vite React Frontend Dashboard (port 5173)
echo.
echo [PayShield] Initializing Backend in a new window...
start "PayShield Backend" cmd /c "cd backend && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8001"

echo [PayShield] Initializing Frontend in a new window...
start "PayShield Frontend" cmd /c "cd frontend && npm run dev"

echo.
echo =================================================================
echo  Platform is loading!
echo   - Interactive Web Dashboard:  http://localhost:5173
echo   - FastAPI Swagger Documents:  http://localhost:8001/docs
echo =================================================================
echo.
echo Press any key to shutdown this controller window (servers will continue in their respective shells)...
pause > nul
