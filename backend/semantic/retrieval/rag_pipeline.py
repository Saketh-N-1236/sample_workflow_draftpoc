"""
Unified semantic RAG pipeline for test selection.

Single path: resolve symbols, form canonical text (validated summary or diff-anchor),
enrich once with symbols, mandatory query rewriting, multi-query vector search.
Post-rewrite queries are not cosine-validated (they are grounded in the enriched
original query). Summary text is still validated vs the diff embedding. See README.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest
from semantic.backends import get_backend
from semantic.config import (
    DEFAULT_SIMILARITY_THRESHOLD,
    GIT_DIFF_SUMMARY_VALIDATION_THRESHOLD,
    RAG_DIFF_ANCHOR_MAX_CHARS,
    RAG_LENIENT_FALLBACK,
)
from semantic.prompts.diff_summarizer import summarize_git_diff
from semantic.prompts.query_rewriter import QueryRewriterService
from semantic.retrieval.query_builder import (
    build_diff_anchor_text,
    build_rich_change_description,
    enrich_semantic_query_with_diff_symbols,
)
from semantic.retrieval.validation import validate_llm_extraction

logger = logging.getLogger(__name__)


def _resolve_symbols(
    deleted_symbols: Optional[List[str]],
    added_symbols: Optional[List[str]],
    renamed_symbols: Optional[List[Dict[str, Any]]],
    diff_content: Optional[str],
) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    ds = list(deleted_symbols or [])
    ads = list(added_symbols or [])
    rns = list(renamed_symbols or [])
    if not ds and not ads and not rns and diff_content and diff_content.strip():
        try:
            from deterministic.parsing.diff_parser import (
                extract_deleted_added_renamed_symbols,
            )

            delta = extract_deleted_added_renamed_symbols(diff_content)
            ds = list(delta.get("deleted_symbols") or [])
            ads = list(delta.get("added_symbols") or [])
            rns = list(delta.get("renamed_symbols") or [])
        except Exception:
            pass
    return ds, ads, rns


async def _vector_search_queries(
    conn,
    queries: List[str],
    similarity_threshold: float,
    max_results: int,
    test_repo_id: Optional[str],
    top_k: Optional[int],
    top_p: Optional[int],
) -> List[Dict[str, Any]]:
    """Embed each query string, search backend, merge with weights (first query 1.0, rest 0.9)."""
    embedding_provider = LLMFactory.create_embedding_provider(get_settings())
    backend = get_backend(conn)
    query_limit = max(max_results * 2, 100) if max_results > 0 else 10000
    expected_dimensions = None
    if hasattr(embedding_provider, "get_embedding_dimensions"):
        expected_dimensions = embedding_provider.get_embedding_dimensions()

    all_results: List[Dict[str, Any]] = []
    seen_test_ids = set()

    for i, query in enumerate(queries):
        if not query or not query.strip():
            continue
        try:
            response = await embedding_provider.get_embeddings(
                EmbeddingRequest(texts=[query])
            )
            query_embedding = response.embeddings[0]
            results = await backend.search_similar(
                query_embedding,
                similarity_threshold,
                query_limit,
                test_repo_id=test_repo_id,
                top_k=top_k,
                top_p=top_p,
                expected_dimensions=expected_dimensions,
            )
            weight = 1.0 if i == 0 else 0.9
            for result in results:
                test_id = result.get("test_id")
                if test_id not in seen_test_ids:
                    result["query_weight"] = weight
                    all_results.append(result)
                    seen_test_ids.add(test_id)
                else:
                    for existing in all_results:
                        if existing.get("test_id") == test_id:
                            existing["query_weight"] = max(
                                existing.get("query_weight", 1.0), weight
                            )
                            existing["similarity"] = max(
                                existing.get("similarity", 0),
                                result.get("similarity", 0),
                            )
                            break
        except Exception as e:
            logger.warning("[RAG] Failed query variation %s: %s", i + 1, e)
            continue

    for result in all_results:
        w = result.get("query_weight", 1.0)
        result["weighted_similarity"] = result.get("similarity", 0) * w
    all_results.sort(key=lambda x: x.get("weighted_similarity", 0), reverse=True)
    for result in all_results:
        result.pop("query_weight", None)
        result.pop("weighted_similarity", None)
    all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
    for result in all_results:
        orig = result.get("similarity", 0)
        result["confidence_score"] = int(orig * 60)
        result["similarity"] = orig
        result["match_type"] = "semantic"
    if max_results > 0:
        all_results = all_results[:max_results]
    return all_results


async def run_semantic_rag(
    conn,
    changed_functions: List[Dict[str, Any]],
    file_changes: Optional[List[Dict]] = None,
    diff_content: Optional[str] = None,
    similarity_threshold: Optional[float] = None,
    max_results: int = 10000,
    test_repo_id: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[int] = None,
    num_query_variations: int = 3,
    deleted_symbols: Optional[List[str]] = None,
    added_symbols: Optional[List[str]] = None,
    renamed_symbols: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Run the unified RAG pipeline.

    Returns:
        (tests, rag_diagnostics) — diagnostics always populated; on success includes pipeline metadata.
    """
    empty_diag: Dict[str, Any] = {"ok": False, "stage": "init"}

    if not changed_functions and not file_changes and not diff_content:
        return [], {**empty_diag, "stage": "no_inputs", "reason": "no functions, files, or diff"}

    ds, ads, rns = _resolve_symbols(
        deleted_symbols, added_symbols, renamed_symbols, diff_content
    )
    rich = build_rich_change_description(
        changed_functions, file_changes, diff_content
    )
    canonical = ""
    summary_meta: Dict[str, Any] = {}

    dc = (diff_content or "").strip()
    if dc:
        try:
            summary = await summarize_git_diff(diff_content)
            if summary and summary.strip():
                metrics = await validate_llm_extraction(dc, [summary.strip()])
                avg_sim = float(metrics.get("avg_similarity", 0.0))
                summary_meta = {
                    "summary_validation_avg_similarity": avg_sim,
                    "threshold": GIT_DIFF_SUMMARY_VALIDATION_THRESHOLD,
                }
                if avg_sim >= GIT_DIFF_SUMMARY_VALIDATION_THRESHOLD:
                    canonical = summary.strip()
                    logger.info(
                        "[RAG] Using LLM diff summary (cosine=%.3f >= %.3f)",
                        avg_sim,
                        GIT_DIFF_SUMMARY_VALIDATION_THRESHOLD,
                    )
                else:
                    hint = rich[:800] if rich else None
                    canonical = build_diff_anchor_text(
                        dc, hint, RAG_DIFF_ANCHOR_MAX_CHARS
                    )
                    summary_meta["canonical_source"] = "diff_anchor"
                    logger.info(
                        "[RAG] Summary rejected (cosine=%.3f); using diff-anchor text",
                        avg_sim,
                    )
            else:
                canonical = build_diff_anchor_text(
                    dc, rich[:800] if rich else None, RAG_DIFF_ANCHOR_MAX_CHARS
                )
                summary_meta["canonical_source"] = "diff_anchor"
        except Exception as e:
            logger.warning("[RAG] Summary step failed: %s", e)
            canonical = build_diff_anchor_text(
                dc, rich[:800] if rich else None, RAG_DIFF_ANCHOR_MAX_CHARS
            )
            summary_meta["canonical_source"] = "diff_anchor"
            summary_meta["summary_error"] = str(e)
    else:
        canonical = rich or ""
        summary_meta["canonical_source"] = "rich_description_only"

    if not (canonical or "").strip():
        return [], {
            **empty_diag,
            "stage": "no_canonical_text",
            "reason": "empty canonical after build",
            **summary_meta,
        }

    # Single symbol enrichment (once)
    original_query = enrich_semantic_query_with_diff_symbols(
        canonical.strip(), ds, ads, rns
    )

    # Mandatory query rewriting
    queries: List[str] = []
    try:
        rewriter = QueryRewriterService()
        queries = await rewriter.rewrite_queries(
            original_query,
            None,
            num_query_variations,
        )
    except Exception as e:
        logger.error("[RAG] Query rewriting failed: %s", e, exc_info=True)
        queries = []

    if not queries:
        queries = [original_query]

    # Mandatory multi-query rewrite: need original plus at least one variation
    rewrite_ok = len(queries) >= 2

    if not rewrite_ok:
        diag = {
            "ok": False,
            "stage": "rewrite",
            "reason": "rewriter returned fewer than 2 queries",
            "query_count": len(queries),
            **summary_meta,
        }
        if RAG_LENIENT_FALLBACK:
            tests = await _vector_search_queries(
                conn,
                [original_query],
                similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD,
                max_results,
                test_repo_id,
                top_k,
                top_p,
            )
            return tests, {
                **diag,
                "ok": True,
                "recovered_via": "RAG_LENIENT_FALLBACK",
                "after_rewrite_failure": True,
            }
        return [], diag

    # Rewrites are derived from original_query; no post-rewrite embedding validation.
    queries_for_search = [q.strip() for q in queries if q and q.strip()]
    if not queries_for_search:
        return [], {
            **empty_diag,
            "stage": "rewrite",
            "reason": "all rewriter outputs empty after strip",
            "query_count": len(queries),
            **summary_meta,
        }

    threshold = similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD
    tests = await _vector_search_queries(
        conn,
        queries_for_search,
        threshold,
        max_results,
        test_repo_id,
        top_k,
        top_p,
    )
    return tests, {
        "ok": True,
        "stage": "complete",
        "post_rewrite_validation": "skipped",
        "queries_used": len(queries_for_search),
        **summary_meta,
    }
