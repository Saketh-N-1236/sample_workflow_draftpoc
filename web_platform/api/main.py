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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Determine project root and web_platform paths
# Path structure: project_root/web_platform/api/main.py
current_file = Path(__file__).resolve()
web_platform_path = current_file.parent.parent  # web_platform/
project_root = web_platform_path.parent  # project_root/

# Load environment variables from .env file
env_path = project_root / ".env"
if not env_path.exists():
    env_path = web_platform_path / ".env"

# Store env path for debug endpoint
logger = logging.getLogger(__name__)
_loaded_env_path = None
if env_path.exists():
    load_dotenv(env_path)
    _loaded_env_path = str(env_path)
    logger.info(f"Loaded .env from: {env_path}")
else:
    # Try loading from current directory
    load_dotenv()
    _loaded_env_path = "current directory (not found in expected locations)"
    logger.warning(f".env file not found at {env_path}, trying current directory")

# Add paths to sys.path for imports (project_root first for test_analysis access)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(web_platform_path) not in sys.path:
    sys.path.insert(0, str(web_platform_path))

from api.routes import repositories, analysis, selection

app = FastAPI(
    title="Test Impact Analysis API",
    description="API for test impact analysis and test selection",
    version="1.0.0"
)


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
    """Debug endpoint to check environment variables (without exposing values)."""
    import os
    return {
        "GITHUB_API_TOKEN": "set" if os.getenv('GITHUB_API_TOKEN') else "NOT set",
        "GITHUB_API_URL": os.getenv('GITHUB_API_URL', 'not set'),
        "GITLAB_API_TOKEN": "set" if os.getenv('GITLAB_API_TOKEN') else "NOT set",
        "GITLAB_API_URL": os.getenv('GITLAB_API_URL', 'not set'),
        "PINECONE_API_KEY": "set" if os.getenv('PINECONE_API_KEY') else "NOT set",
        "PINECONE_INDEX_NAME": os.getenv('PINECONE_INDEX_NAME', 'not set'),
        "PINECONE_ENVIRONMENT": os.getenv('PINECONE_ENVIRONMENT', 'not set'),
        "VECTOR_BACKEND": os.getenv('VECTOR_BACKEND', 'not set'),
        "TEST_REPO_PATH": os.getenv('TEST_REPO_PATH', 'not set'),
        "PROJECT_ROOT": str(project_root) if 'project_root' in globals() else "unknown",
        "WEB_PLATFORM_PATH": str(web_platform_path) if 'web_platform_path' in globals() else "unknown",
        "env_file_loaded_from": _loaded_env_path if '_loaded_env_path' in globals() else "unknown"
    }
