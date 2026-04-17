"""Repository data models."""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class RepositoryCreate(BaseModel):
    """Request model for creating a repository connection."""
    url: str
    provider: Optional[str] = None  # 'github' or 'gitlab', auto-detected if not provided


class RepositoryResponse(BaseModel):
    """Response model for repository information."""
    id: str
    url: str
    provider: Optional[str] = None  # 'github' or 'gitlab'
    local_path: Optional[str] = None  # Optional - not needed when using API
    selected_branch: Optional[str] = None  # Currently selected branch
    default_branch: Optional[str] = None  # Default branch from repository
    last_commit: Optional[str] = None
    createdAt: Optional[datetime] = None
    lastRefreshed: Optional[datetime] = None  # Timestamp of last refresh
    risk_threshold: Optional[int] = 20  # Risk threshold for test selection

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RepositoryUpdate(BaseModel):
    """Request model for updating repository (e.g., branch selection)."""
    selected_branch: Optional[str] = None


class RiskThresholdUpdate(BaseModel):
    """Request model for updating risk threshold."""
    threshold: Optional[int] = None  # None means no risk analysis (always run selection)


class BranchResponse(BaseModel):
    """Response model for branch information."""
    name: str
    default: bool = False
    protected: bool = False
    commit_id: str = ""
    commit_message: str = ""


class BranchesResponse(BaseModel):
    """Response model for list of branches."""
    branches: list[BranchResponse]
    default_branch: Optional[str] = None
    page: int = 1
    per_page: int = 30
    has_more: bool = False
    fetch_all: bool = False


class DiffResponse(BaseModel):
    """Response model for git diff."""
    diff: str
    changedFiles: list[str]
    stats: dict
    branch: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Response model for test analysis results."""
    status: str
    filesAnalyzed: int = 0
    testFiles: int = 0
    totalTests: int = 0
    totalTestClasses: int = 0
    totalTestMethods: int = 0
    functionsExtracted: int = 0
    modulesIdentified: int = 0
    totalDependencies: int = 0
    totalProductionClasses: int = 0
    testsWithDescriptions: int = 0
    framework: Optional[str] = None
    message: Optional[str] = None


class SemanticMatch(BaseModel):
    """Model for semantic match details."""
    test_id: str
    similarity: float
    confidence: str
    query_used: Optional[str] = None


class LLMConfig(BaseModel):
    """Model for LLM reasoning configuration."""
    enabled: bool = True
    top_n: int = 20  # Number of candidates to send to LLM
    provider: Optional[str] = None  # Override default provider


class LLMInputOutput(BaseModel):
    """Model for LLM input and output."""
    input: str
    output: str
    assessed_tests_count: Optional[int] = None


class SelectionResponse(BaseModel):
    """Response model for test selection results."""
    totalTests: int = 0  # Number of selected tests
    totalTestsInDb: int = 0  # Total tests in database (for coverage calculation)
    astMatches: int = 0  # In final table: tests with an AST/DB link
    semanticMatches: int = 0  # In final table: tests vector search contributed to
    independentCount: int = 0   # Tests that directly import/cover the changed code
    crossDependentCount: int = 0  # Tests indirectly affected (transitive/semantic)
    selectionFunnel: Optional[Dict] = None  # Pipeline explanation + vector vs final counts
    semanticSearchCandidates: Optional[int] = None  # Raw vector hits before filtering
    semanticVectorThreshold: Optional[float] = None  # Min cosine similarity used for vector search
    tests: list[dict] = []
    # Enhanced semantic fields
    semanticMatchDetails: List[SemanticMatch] = []
    astMatchDetails: List[Dict] = []
    overlapCount: int = 0
    embeddingStatus: Optional[Dict] = None
    semanticConfig: Optional[Dict] = None
    # Risk analysis fields
    riskAnalysis: Optional[Dict] = None  # {exceeded: bool, changed_files: int, threshold: int, message: str}
    selectionDisabled: bool = False
    # LLM reasoning fields
    llmScores: Optional[List[Dict]] = None  # [{test_id, llm_score, llm_explanation}]
    llmInputOutput: Optional[Dict] = None  # {input: str, output: str, assessed_tests_count: int}
    # Confidence distribution
    confidenceDistribution: Optional[Dict] = None  # {high: int, medium: int, low: int}
    # Diff impact (coverage gaps and breakage warnings)
    coverageGaps: Optional[List[Dict]] = None  # [{type, symbol?, message?, ...}]
    breakageWarnings: Optional[List[str]] = None
    ragDiagnostics: Optional[Dict] = None  # Unified RAG pipeline diagnostics (stage, scores, recovery)