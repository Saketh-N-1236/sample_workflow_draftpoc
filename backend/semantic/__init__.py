"""
Semantic Retrieval Engine

This module provides semantic search capabilities for test selection using
vector embeddings and cosine similarity.
"""

# Main retrieval functions
from semantic.retrieval.semantic_search import find_tests_semantic
from semantic.retrieval.query_builder import build_rich_change_description
from semantic.retrieval.multi_query_search import find_tests_semantic_with_multi_queries
from semantic.retrieval.validation import validate_llm_extraction
from semantic.retrieval.rag_pipeline import run_semantic_rag

# Embedding generation
from semantic.embedding_generation.embedding_generator import store_embeddings
from semantic.embedding_generation.text_builder import build_embedding_text

# Prompts/LLM services
from semantic.prompts.query_rewriter import QueryRewriterService

# Backends
from semantic.backends import get_backend

# Config
from semantic.config import DEFAULT_SIMILARITY_THRESHOLD

__all__ = [
    'find_tests_semantic',
    'run_semantic_rag',
    'build_rich_change_description',
    'find_tests_semantic_with_multi_queries',
    'validate_llm_extraction',
    'store_embeddings',
    'build_embedding_text',
    'QueryRewriterService',
    'get_backend',
    'DEFAULT_SIMILARITY_THRESHOLD',
]
