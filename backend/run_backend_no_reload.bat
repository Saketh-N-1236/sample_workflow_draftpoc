@echo off
cd /d %~dp0
REM Run without auto-reload to avoid issues with repos/ directory
python -m uvicorn api.main:app --port 8000
