"""FastAPI application entry point."""

import sys
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Determine paths
# Path structure: project_root/backend/api/main.py
current_file = Path(__file__).resolve()
backend_path = current_file.parent.parent  # backend/
project_root = backend_path.parent         # project_root/ (sample_workflow/)

# Load environment variables: project root first, then backend/.env without
# overriding (so tokens only in backend/.env still apply when root .env exists).
_root_env = project_root / ".env"
_backend_env = backend_path / ".env"

logger = logging.getLogger(__name__)
_loaded_env_path = None
if _root_env.exists():
    load_dotenv(_root_env)
    _loaded_env_path = str(_root_env)
    logger.info("Loaded .env from: %s", _root_env)
if _backend_env.exists():
    load_dotenv(_backend_env, override=False)
    logger.info("Merged .env (override=False): %s", _backend_env)
    if not _loaded_env_path:
        _loaded_env_path = str(_backend_env)
if not _loaded_env_path:
    load_dotenv()
    _loaded_env_path = "current directory (not found in expected locations)"
    logger.warning(
        ".env not found at %s or %s; trying cwd",
        _root_env,
        _backend_env,
    )

# Add backend/ to sys.path so all packages (services, api, config, llm, etc.) are importable
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from api.routes import repositories, analysis, selection, test_repositories

app = FastAPI(
    title="Test Impact Analysis API",
    description="API for test impact analysis and test selection",
    version="1.0.0"
)


@app.on_event("shutdown")
async def shutdown_event():
    try:
        from services.http_client import close_shared_async_client
        await close_shared_async_client()
    except Exception as e:
        logger.warning(f"Could not close shared HTTP client: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    logger.info("Starting up API server...")
    
    # Ensure audit log table exists
    try:
        from services.audit_service import ensure_audit_log_table_exists
        if ensure_audit_log_table_exists():
            logger.info("Audit log table verified/created successfully")
        else:
            logger.warning("Failed to verify/create audit log table")
    except Exception as e:
        logger.warning(f"Could not verify audit log table on startup: {e}")
    
    # Ensure repositories table exists
    try:
        from services.repository_db import create_repositories_table
        create_repositories_table()
        logger.info("Repositories table verified/created successfully")
    except Exception as e:
        logger.warning(f"Could not verify repositories table on startup: {e}")
    
    # Ensure test repository tables exist
    try:
        from services.test_repo_service import create_test_repo_tables
        if create_test_repo_tables():
            logger.info("Test repository tables verified/created successfully")
        else:
            logger.warning("Failed to verify/create test repository tables")
    except Exception as e:
        logger.warning(f"Could not verify test repository tables on startup: {e}")

# CORS middleware
# In production, replace "*" with specific allowed origins
import os
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with /api prefix
app.include_router(repositories.router, prefix="/api")
app.include_router(analysis.repo_router, prefix="/api")
app.include_router(analysis.analysis_router, prefix="/api")
app.include_router(selection.router, prefix="/api")
app.include_router(test_repositories.router)

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Test Impact Analysis API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api")
async def api_root():
    """API root endpoint."""
    return {"message": "Test Impact Analysis API", "version": "1.0.0"}


@app.get("/api/debug/env")
async def debug_env():
    """
    Debug endpoint to check environment variables (without exposing values).
    Only available in development mode (ENVIRONMENT=development).
    """
    import os
    environment = os.getenv('ENVIRONMENT', 'production').lower()
    
    if environment != 'development':
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Debug endpoint not available in production")
    
    return {
        "GITHUB_API_TOKEN": "set" if os.getenv('GITHUB_API_TOKEN') else "NOT set",
        "GITHUB_API_URL": os.getenv('GITHUB_API_URL', 'not set'),
        "GITLAB_API_TOKEN": "set" if os.getenv('GITLAB_API_TOKEN') else "NOT set",
        "GITLAB_API_URL": os.getenv('GITLAB_API_URL', 'not set'),
        "PINECONE_API_KEY": "set" if os.getenv('PINECONE_API_KEY') else "NOT set",
        "PINECONE_INDEX_NAME": os.getenv('PINECONE_INDEX_NAME', 'not set'),
        "PINECONE_ENVIRONMENT": os.getenv('PINECONE_ENVIRONMENT', 'not set'),
        "VECTOR_BACKEND": os.getenv('VECTOR_BACKEND', 'not set'),
        "TEST_REPO_PATH": "set" if os.getenv('TEST_REPO_PATH') else "NOT set",
        "PROJECT_ROOT": str(project_root) if 'project_root' in globals() else "unknown",
        "BACKEND_PATH": str(backend_path) if 'backend_path' in globals() else "unknown",
        "env_file_loaded_from": _loaded_env_path if '_loaded_env_path' in globals() else "unknown"
    }
