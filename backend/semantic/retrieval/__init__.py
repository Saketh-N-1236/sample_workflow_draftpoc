"""
Retrieval module for semantic retrieval.

Unified RAG: rag_pipeline.run_semantic_rag; find_tests_semantic is the main entry.
"""

from semantic.retrieval.semantic_search import find_tests_semantic
from semantic.retrieval.query_builder import build_rich_change_description
from semantic.retrieval.multi_query_search import find_tests_semantic_with_multi_queries
from semantic.retrieval.validation import validate_llm_extraction
from semantic.retrieval.rag_pipeline import run_semantic_rag

__all__ = [
    'find_tests_semantic',
    'run_semantic_rag',
    'build_rich_change_description',
    'find_tests_semantic_with_multi_queries',
    'validate_llm_extraction',
]
