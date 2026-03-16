"""
Advanced RAG implementation for enhanced semantic retrieval.

This package provides LLM-powered query understanding, rewriting, and re-ranking
to improve semantic search accuracy for test selection.
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    'QueryUnderstandingService',
    'QueryRewriterService',
    'RerankerService',
    'find_tests_advanced_rag',
]

def __getattr__(name):
    """Lazy import for Advanced RAG components."""
    if name == 'QueryUnderstandingService':
        from semantic_retrieval.advanced_rag.query_understanding import QueryUnderstandingService
        return QueryUnderstandingService
    elif name == 'QueryRewriterService':
        from semantic_retrieval.advanced_rag.query_rewriter import QueryRewriterService
        return QueryRewriterService
    elif name == 'RerankerService':
        from semantic_retrieval.advanced_rag.reranker import RerankerService
        return RerankerService
    elif name == 'find_tests_advanced_rag':
        from semantic_retrieval.advanced_rag.advanced_semantic_search import find_tests_advanced_rag
        return find_tests_advanced_rag
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
