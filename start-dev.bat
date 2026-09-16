@echo off
REM Starts the full Electra dev stack: Postgres/Redis (Docker), the FastAPI
REM backend, the Celery worker + beat scheduler (background jobs - waitlist
REM promotion, overstay penalties, maintenance triggers, etc. never run
REM without these), and the Vite frontend. Each process gets its own window
REM so you can watch its logs; close a window to stop that piece.

echo Starting Postgres + Redis...
docker compose up -d

echo Starting backend (FastAPI on :8000)...
start "electra-backend" cmd /k "cd backend && venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

echo Starting Celery worker...
start "electra-celery-worker" cmd /k "cd backend && venv\Scripts\python.exe -m celery -A app.core.celery_app worker --loglevel=info --pool=solo"

echo Starting Celery beat...
start "electra-celery-beat" cmd /k "cd backend && venv\Scripts\python.exe -m celery -A app.core.celery_app beat --loglevel=info"

echo Starting frontend (Vite on :5173)...
start "electra-frontend" cmd /k "cd frontend && npm run dev -- --port 5173"

echo.
echo All set. Frontend: http://localhost:5173  Backend: http://localhost:8000
echo Close each window individually to stop that process.
