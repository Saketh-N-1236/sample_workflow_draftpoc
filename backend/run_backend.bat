@echo off
cd /d %~dp0
REM Run backend with hot-reload watching the backend/ directory
REM This ensures changes to services, analysis, semantic_retrieval, etc. trigger a reload
python -m uvicorn api.main:app --reload --reload-dir . --port 8000
