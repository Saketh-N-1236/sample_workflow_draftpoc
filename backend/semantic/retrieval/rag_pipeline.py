"""
Unified semantic RAG pipeline for test selection.

Single path: resolve symbols, form canonical text (validated summary or diff-anchor),
enrich once with symbols, mandatory query rewriting, multi-query vector search.
Post-rewrite queries are not cosine-validated (they are grounded in the enriched
original query). Summary text is still validated vs the diff embedding. See README.
"""

from __future__ import annotations

import asyncio
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
) -> Tuple[List[Dict[str, Any]], Optional[List[float]]]:
    """
    Embed ALL query strings in ONE batched API call, then run all Pinecone searches
    in parallel via asyncio.gather.  Merge results with weights (first query 1.0, rest 0.9).

    Returns (results, primary_query_embedding).  The primary embedding (queries[0]) is
    cached so the caller can reuse it for ast_semantic_supplement without re-embedding.

    Optimisation summary
    --------------------
    Before: N serial embed calls  + N serial Pinecone searches
    After : 1 batched embed call  + N parallel Pinecone searches
    """
    embedding_provider = LLMFactory.create_embedding_provider(get_settings())
    backend = get_backend(conn)
    query_limit = max(max_results * 2, 100) if max_results > 0 else 10000
    expected_dimensions = None
    if hasattr(embedding_provider, "get_embedding_dimensions"):
        expected_dimensions = embedding_provider.get_embedding_dimensions()

    # ── Filter blanks, preserving original index so position-0 stays "primary" ──
    indexed_queries: List[tuple[int, str]] = [
        (i, q.strip()) for i, q in enumerate(queries) if q and q.strip()
    ]
    if not indexed_queries:
        return [], None

    texts = [q for _, q in indexed_queries]

    # ── Step 1: ONE batched embedding call for all query variations ──────────────
    try:
        emb_response = await embedding_provider.get_embeddings(
            EmbeddingRequest(texts=texts)
        )
        embeddings: List[List[float]] = emb_response.embeddings
    except Exception as e:
        logger.warning("[RAG] Batch embedding failed: %s", e)
        return [], None

    if len(embeddings) != len(texts):
        logger.warning(
            "[RAG] Embedding count mismatch: expected %s got %s",
            len(texts), len(embeddings),
        )
        return [], None

    primary_query_embedding: Optional[List[float]] = None
    orig_idx_0 = indexed_queries[0][0]  # original index of the first valid query
    if orig_idx_0 == 0:
        primary_query_embedding = embeddings[0]

    # ── Step 2: ALL Pinecone searches in PARALLEL ─────────────────────────────────
    async def _search(emb: List[float]) -> List[Dict[str, Any]]:
        try:
            return await backend.search_similar(
                emb,
                similarity_threshold,
                query_limit,
                test_repo_id=test_repo_id,
                top_k=top_k,
                top_p=top_p,
                expected_dimensions=expected_dimensions,
            )
        except Exception as e:
            logger.warning("[RAG] Pinecone search failed: %s", e)
            return []

    per_query_results: List[List[Dict[str, Any]]] = await asyncio.gather(
        *[_search(emb) for emb in embeddings]
    )

    # ── Step 3: Merge (identical logic to before) ─────────────────────────────────
    all_results: List[Dict[str, Any]] = []
    seen: Dict[str, Dict[str, Any]] = {}

    for slot, (orig_i, _) in enumerate(indexed_queries):
        weight = 1.0 if orig_i == 0 else 0.9
        for result in per_query_results[slot]:
            test_id = result.get("test_id")
            if test_id not in seen:
                result["query_weight"] = weight
                all_results.append(result)
                seen[test_id] = result
            else:
                existing = seen[test_id]
                existing["query_weight"] = max(existing.get("query_weight", 1.0), weight)
                existing["similarity"] = max(
                    existing.get("similarity", 0), result.get("similarity", 0)
                )

    # Sort by weighted_similarity (first-query hits rank higher) then strip helpers.
    for result in all_results:
        result["weighted_similarity"] = result.get("similarity", 0) * result.get("query_weight", 1.0)
    all_results.sort(key=lambda x: x.get("weighted_similarity", 0), reverse=True)
    for result in all_results:
        result.pop("query_weight", None)
        result.pop("weighted_similarity", None)

    for result in all_results:
        orig = result.get("similarity", 0)
        result["confidence_score"] = int(orig * 60)
        result["similarity"] = orig
        result["match_type"] = "semantic"

    if max_results > 0:
        all_results = all_results[:max_results]

    logger.info(
        "[RAG] Batch-embedded %s queries (1 API call) → parallel-searched → %s candidates",
        len(texts), len(all_results),
    )
    return all_results, primary_query_embedding


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

    diff_content is required. If empty/missing, returns [] immediately (stage: "no_inputs").
    Canonical query source: Path A (validated LLM summary) → Path B (diff-anchor text).

    Returns:
        (tests, rag_diagnostics) — diagnostics always populated; on success includes pipeline metadata.
    """
    empty_diag: Dict[str, Any] = {"ok": False, "stage": "init"}

    # Diff content is required — without it there is nothing to embed or summarise.
    dc = (diff_content or "").strip()
    if not dc:
        return [], {
            **empty_diag,
            "stage": "no_inputs",
            "reason": "diff_content is empty or missing",
            "queries_used_strings": [],
        }

    ds, ads, rns = _resolve_symbols(
        deleted_symbols, added_symbols, renamed_symbols, diff_content
    )
    rich = build_rich_change_description(
        changed_functions, file_changes, diff_content
    )
    canonical = ""
    summary_meta: Dict[str, Any] = {}

    try:
        summary, diff_embedding_cached = await summarize_git_diff(diff_content)
        if summary and summary.strip():
            metrics = await validate_llm_extraction(
                dc, [summary.strip()],
                precomputed_diff_embedding=diff_embedding_cached,
            )
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

    if not (canonical or "").strip():
        return [], {
            **empty_diag,
            "stage": "no_canonical_text",
            "reason": "empty canonical after build",
            "queries_used_strings": [],
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
            tests, prim_emb = await _vector_search_queries(
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
                "queries_used_strings": [original_query.strip()],
                "primary_query_embedding": prim_emb,
            }
        return [], {**diag, "queries_used_strings": [], "primary_query_embedding": None}

    # Rewrites are derived from original_query; no post-rewrite embedding validation.
    queries_for_search = [q.strip() for q in queries if q and q.strip()]
    if not queries_for_search:
        return [], {
            **empty_diag,
            "stage": "rewrite",
            "reason": "all rewriter outputs empty after strip",
            "query_count": len(queries),
            "queries_used_strings": [],
            "primary_query_embedding": None,
            **summary_meta,
        }

    threshold = similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD
    tests, prim_emb = await _vector_search_queries(
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
        "queries_used_strings": list(queries_for_search),
        "primary_query_embedding": prim_emb,
        **summary_meta,
    }
