"""
Semantic search functions for test selection using vector embeddings.

Unified RAG: all semantic retrieval goes through rag_pipeline.run_semantic_rag.
Diagnostics are attached to semantic_config dict as '_rag_diagnostics' when provided.
"""

from typing import Any, Dict, List, Optional

from semantic.retrieval.rag_pipeline import run_semantic_rag


async def find_tests_semantic(
    conn,
    changed_functions: list,
    file_changes: Optional[List[Dict]] = None,
    similarity_threshold: Optional[float] = None,
    max_results: int = 10000,
    use_adaptive_thresholds: bool = True,  # API compat; ignored (threshold from semantic_config or default)
    test_repo_id: str = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    diff_content: Optional[str] = None,
    semantic_config: Optional[Dict] = None,
    deleted_symbols: Optional[List[str]] = None,
    added_symbols: Optional[List[str]] = None,
    renamed_symbols: Optional[List[Dict]] = None,
) -> list:
    """
    Semantic search — unified RAG pipeline (summary / diff-anchor, enrich once,
    rewrite, validate, vector search).

    When semantic_config is a mutable dict, '_rag_diagnostics' is set on it after the run.
    """
    if not changed_functions and not file_changes and not diff_content:
        return []

    num_query_variations = 3
    if semantic_config and semantic_config.get("num_query_variations") is not None:
        try:
            num_query_variations = max(1, int(semantic_config.get("num_query_variations")))
        except (TypeError, ValueError):
            num_query_variations = 3

    if semantic_config and semantic_config.get("max_results") is not None:
        try:
            max_results = int(semantic_config.get("max_results"))
        except (TypeError, ValueError):
            pass

    if semantic_config and semantic_config.get("similarity_threshold") is not None:
        try:
            similarity_threshold = float(semantic_config["similarity_threshold"])
        except (TypeError, ValueError):
            pass

    tests, diag = await run_semantic_rag(
        conn=conn,
        changed_functions=changed_functions,
        file_changes=file_changes,
        diff_content=diff_content,
        similarity_threshold=similarity_threshold,
        max_results=max_results,
        test_repo_id=test_repo_id,
        top_k=top_k,
        top_p=top_p,
        num_query_variations=num_query_variations,
        deleted_symbols=deleted_symbols,
        added_symbols=added_symbols,
        renamed_symbols=renamed_symbols,
    )

    if semantic_config is not None and isinstance(semantic_config, dict):
        semantic_config["_rag_diagnostics"] = diag

    return tests
