"""
LLM prompts and services module for semantic retrieval.
"""

__all__ = ['QueryRewriterService', 'build_semantic_classification_prompt']


def __getattr__(name):
    if name == 'QueryRewriterService':
        from semantic.prompts.query_rewriter import QueryRewriterService
        return QueryRewriterService
    if name == 'build_semantic_classification_prompt':
        from semantic.prompts.semantic_classify_prompt import build_semantic_classification_prompt
        return build_semantic_classification_prompt
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
