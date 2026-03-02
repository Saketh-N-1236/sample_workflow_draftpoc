"""
Semantic search functions for test selection using vector embeddings.
"""

from typing import List, Dict, Any
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest
from semantic_retrieval.backends import get_backend
from semantic_retrieval.config import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_MAX_RESULTS
)


async def find_tests_semantic(
    conn,
    changed_functions: list,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_results: int = DEFAULT_MAX_RESULTS
) -> list:
    """
    Semantic search layer — finds tests by meaning, not name.

    Runs as Strategy 4 inside find_affected_tests().
    Only adds tests NOT already found by strategies 0-3.

    Uses the configured vector backend (ChromaDB or pgvector) for search.

    changed_functions — list of dicts from search_queries['changed_functions']:
      [{'module': 'agent.langgraph_agent', 'function': 'initialize'}, ...]

    Returns list of test dicts with confidence_score already set (max 60).
    match_type will be 'semantic' for deduplication.

    Uses Ollama nomic-embed-text (768 dims).
    similarity_threshold=0.75 = 75% cosine similarity minimum.
    Semantic scores capped at 60 so they NEVER outrank exact matches.
    """
    if not changed_functions:
        return []

    # Build description of what changed
    functions_str = ', '.join(
        f"{cf['function']}() in {cf['module']}"
        for cf in changed_functions
    )
    change_description = (
        f"Changed functions: {functions_str}. "
        f"Module: {changed_functions[0]['module']}."
    )

    # Get query embedding via Ollama
    settings        = get_settings()
    llm             = LLMFactory.create_embedding_provider(settings)
    response        = await llm.get_embeddings(
        EmbeddingRequest(texts=[change_description])
    )
    query_embedding = response.embeddings[0]

    # Get the appropriate backend and search
    backend = get_backend(conn)
    results = await backend.search_similar(
        query_embedding,
        similarity_threshold,
        max_results
    )

    return results
