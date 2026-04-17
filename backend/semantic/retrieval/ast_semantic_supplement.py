"""
AST–semantic supplement: score structurally matched tests against the RAG query.

Global vector search uses a similarity floor (often 0.40–0.45 when AST is strong).
That correctly reduces semantic-only false positives but hides true cosine similarity
for tests AST already found — they never enter semantic_results and show as “AST only”
with 0% semantic in the UI. This module runs a metadata-filtered Pinecone query so each
AST-matched test gets its actual cosine score vs. the same embedding used for retrieval.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest
from semantic.backends import get_backend
from semantic.config import SEMANTIC_SCORE_CAP

logger = logging.getLogger(__name__)

# Pinecone metadata filters: keep $in lists small for compatibility
_TEST_ID_IN_CHUNK = 80


async def embed_query_text(query_text: str) -> Optional[List[float]]:
    if not (query_text or "").strip():
        return None
    try:
        llm = LLMFactory.create_embedding_provider(get_settings())
        resp = await llm.get_embeddings(EmbeddingRequest(texts=[query_text.strip()]))
        return resp.embeddings[0] if resp.embeddings else None
    except Exception as e:
        logger.warning("[AST-SEM-SUP] Embedding query failed: %s", e)
        return None


def _normalize_test_id(tid: Any) -> str:
    if tid is None:
        return ""
    return str(tid).strip()


async def supplement_semantic_hits_for_ast_tests(
    conn: Any,
    ast_results: Dict[str, Any],
    primary_query_text: str,
    test_repo_id: Optional[str],
) -> Dict[str, float]:
    """
    Return test_id -> cosine similarity for AST-matched tests (no global threshold).

    Missing tests (not in index) are omitted.
    """
    ast_tests = ast_results.get("tests") or []
    raw_ids = [_normalize_test_id(t.get("test_id")) for t in ast_tests if t.get("test_id")]
    test_ids = sorted({x for x in raw_ids if x})
    if not test_ids:
        return {}

    query_embedding = await embed_query_text(primary_query_text)
    if not query_embedding:
        return {}

    backend = get_backend(conn)
    scorer = getattr(backend, "query_scores_for_test_ids", None)
    if not callable(scorer):
        logger.debug("[AST-SEM-SUP] Backend has no query_scores_for_test_ids; skip")
        return {}

    expected_dimensions = None
    llm = LLMFactory.create_embedding_provider(get_settings())
    if hasattr(llm, "get_embedding_dimensions"):
        expected_dimensions = llm.get_embedding_dimensions()

    out: Dict[str, float] = {}
    for i in range(0, len(test_ids), _TEST_ID_IN_CHUNK):
        chunk = test_ids[i : i + _TEST_ID_IN_CHUNK]
        try:
            part = await scorer(
                query_embedding,
                chunk,
                test_repo_id=test_repo_id,
                expected_dimensions=expected_dimensions,
            )
            for k, v in (part or {}).items():
                nk = _normalize_test_id(k)
                if nk:
                    out[nk] = max(out.get(nk, 0.0), float(v))
        except Exception as e:
            logger.warning("[AST-SEM-SUP] Filtered query chunk failed: %s", e)
    if out:
        logger.info(
            "[AST-SEM-SUP] Scored %s AST test(s) against primary RAG query (filtered Pinecone)",
            len(out),
        )
    return out


def merge_supplement_into_semantic_results(
    semantic_results: Dict[str, Any],
    ast_results: Dict[str, Any],
    supplement_scores: Dict[str, float],
) -> None:
    """
    Mutate semantic_results['tests']: ensure each AST test id has a row with at least
    supplement similarity (does not remove existing higher scores).
    """
    if not supplement_scores:
        return

    ast_by_id: Dict[str, Dict[str, Any]] = {}
    for t in ast_results.get("tests") or []:
        tid = _normalize_test_id(t.get("test_id"))
        if tid:
            ast_by_id[tid] = t

    rows = list(semantic_results.get("tests") or [])
    by_id: Dict[str, Dict[str, Any]] = {}
    for t in rows:
        tid = _normalize_test_id(t.get("test_id"))
        if tid:
            by_id[tid] = dict(t)

    for tid, sim in supplement_scores.items():
        if sim <= 0:
            continue
        ast_t = ast_by_id.get(tid)
        if not ast_t:
            continue
        existing = by_id.get(tid)
        if existing:
            prev = float(existing.get("similarity") or 0)
            if sim > prev:
                existing["similarity"] = sim
                existing["match_type"] = "semantic"
                existing.setdefault(
                    "confidence_score",
                    min(int(sim * 100), SEMANTIC_SCORE_CAP),
                )
        else:
            by_id[tid] = {
                "test_id": ast_t.get("test_id"),
                "method_name": ast_t.get("method_name", ""),
                "class_name": ast_t.get("class_name", ""),
                "test_file_path": ast_t.get("test_file_path")
                or ast_t.get("file_path", ""),
                "test_type": ast_t.get("test_type", "unknown"),
                "similarity": sim,
                "match_type": "semantic",
                "confidence_score": min(int(sim * 100), SEMANTIC_SCORE_CAP),
                "semantic_supplement_from_ast": True,
            }

    semantic_results["tests"] = list(by_id.values())
    semantic_results["total_tests"] = len(by_id)
