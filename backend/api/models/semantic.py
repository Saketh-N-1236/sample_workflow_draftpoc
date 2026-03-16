"""Semantic search configuration models."""

from pydantic import BaseModel
from typing import Optional


class SemanticConfig(BaseModel):
    """Configuration model for semantic search parameters."""
    similarity_threshold: Optional[float] = None  # 0.3 - 0.7
    max_results: int = 10000  # High limit to effectively remove upper bound
    use_adaptive_thresholds: bool = True
    use_multi_query: bool = False
    top_k: Optional[int] = None  # Top K results to retrieve from vector DB (before filtering)
    top_p: Optional[float] = None  # Nucleus sampling threshold (0.0 - 1.0)
    # Advanced RAG settings
    use_advanced_rag: bool = True  # Enable Advanced RAG pipeline
    use_query_rewriting: bool = True  # Enable query rewriting with LLM
    use_llm_reranking: bool = True  # Enable LLM re-ranking
    rerank_top_k: int = 50  # Number of candidates to re-rank
    num_query_variations: int = 3  # Number of query variations to generate
    quality_threshold: float = 0.3  # Quality threshold for filtering (0.0-1.0, only tests with rerank_score >= this are returned)


class EmbeddingStatus(BaseModel):
    """Model for embedding status information."""
    total_embeddings: int
    last_generated: Optional[str] = None
    index_health: str  # "healthy", "unhealthy", "unknown"
    embedding_dimensions: int = 768
    backend: str  # "pinecone" (only supported backend)
    index_name: Optional[str] = None
