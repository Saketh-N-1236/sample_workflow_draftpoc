"""
LLM prompts and services module for semantic retrieval.
"""

__all__ = ['QueryRewriterService']


def __getattr__(name):
    if name == 'QueryRewriterService':
        from semantic.prompts.query_rewriter import QueryRewriterService
        return QueryRewriterService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
