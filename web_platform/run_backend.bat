@echo off
cd /d %~dp0
REM Note: --reload watches all files. To avoid reloading on repo changes,
REM consider running without --reload in production or moving repos/ outside web_platform/
python -m uvicorn api.main:app --reload --port 8000
