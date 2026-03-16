"""Test repository data models."""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class TestRepositoryCreate(BaseModel):
    """Request model for creating a test repository."""
    name: str
    zip_filename: Optional[str] = None


class TestRepositoryResponse(BaseModel):
    """Response model for test repository information."""
    id: str
    name: str
    zip_filename: Optional[str] = None
    extracted_path: str
    hash: str
    uploaded_at: Optional[datetime] = None
    last_analyzed_at: Optional[datetime] = None
    status: str = "pending"  # pending, analyzing, ready, error
    metadata: Optional[Dict] = None
    schema_name: Optional[str] = None  # Schema name for this test repo
    bound_repositories: Optional[List[str]] = None  # List of repository IDs bound to this test repo

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TestRepositoryUpdate(BaseModel):
    """Request model for updating test repository."""
    name: Optional[str] = None
    status: Optional[str] = None


class TestRepositoryBinding(BaseModel):
    """Model for repository-test repository binding."""
    repository_id: str
    test_repository_id: str
    is_primary: bool = False
    created_at: Optional[datetime] = None


class BindTestRepositoryRequest(BaseModel):
    """Request model for binding a test repository to a repository."""
    test_repository_id: str
    is_primary: Optional[bool] = False


class TestRepositoryAnalysisResponse(BaseModel):
    """Response model for test repository analysis."""
    status: str
    test_repository_id: str
    schema_name: str
    files_analyzed: int = 0
    test_files: int = 0
    total_tests: int = 0
    message: Optional[str] = None
