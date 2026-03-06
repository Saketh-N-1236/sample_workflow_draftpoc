"""Semantic search configuration models."""

from pydantic import BaseModel
from typing import Optional


class SemanticConfig(BaseModel):
    """Configuration model for semantic search parameters."""
    similarity_threshold: Optional[float] = None  # 0.3 - 0.7
    max_results: int = 10000  # High limit to effectively remove upper bound
    use_adaptive_thresholds: bool = True
    use_multi_query: bool = False


class EmbeddingStatus(BaseModel):
    """Model for embedding status information."""
    total_embeddings: int
    last_generated: Optional[str] = None
    index_health: str  # "healthy", "unhealthy", "unknown"
    embedding_dimensions: int = 768
    backend: str  # "pinecone", "chromadb", "pgvector"
    index_name: Optional[str] = None
