@echo off
REM Closes the windows opened by start-dev.bat (backend, celery worker,
REM celery beat, frontend). Docker containers keep running - stop them
REM separately with "docker compose down" if you want to free those ports too.

taskkill /FI "WINDOWTITLE eq electra-backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq electra-celery-worker*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq electra-celery-beat*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq electra-frontend*" /T /F >nul 2>&1

echo Dev processes stopped. Postgres/Redis containers are still running (docker compose down to stop them).
