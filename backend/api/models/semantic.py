"""Semantic search configuration models."""

from pydantic import BaseModel
from typing import Optional


class SemanticConfig(BaseModel):
    """Configuration model for semantic search parameters."""

    similarity_threshold: Optional[float] = None
    max_results: int = 10000
    use_adaptive_thresholds: bool = True  # Ignored by unified RAG; kept for DB JSON compatibility
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    num_query_variations: int = 3

    class Config:
        extra = "ignore"  # Ignore deprecated keys from stored JSON (e.g. use_advanced_rag)


class EmbeddingStatus(BaseModel):
    """Model for embedding status information."""
    total_embeddings: int
    last_generated: Optional[str] = None
    index_health: str = "healthy"  # "healthy", "unhealthy", "unknown"
    embedding_dimensions: int = 768
    backend: str = "pinecone"
    index_name: Optional[str] = None
