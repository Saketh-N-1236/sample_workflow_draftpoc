"""
Validation module for semantic retrieval.

Validates LLM-generated summaries by comparing embeddings with the diff embedding.
"""

import logging
from typing import List, Dict
import numpy as np

from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest
from semantic.embedding_limits import truncate_for_embedding_api

logger = logging.getLogger(__name__)


async def validate_llm_extraction(
    diff_content: str,
    query_variations: List[str]
) -> Dict[str, float]:
    """
    Compare query/summary embeddings to the diff embedding (cosine similarity).

    Returns:
        avg_similarity, max_similarity, min_similarity, query_scores
    """
    if not diff_content or not query_variations:
        logger.warning("[VALIDATION] Missing diff_content or query_variations, skipping")
        return {
            'avg_similarity': 0.0,
            'max_similarity': 0.0,
            'min_similarity': 0.0,
            'query_scores': {}
        }

    logger.info(
        "[VALIDATION] Cosine validation for %d variation(s)",
        len(query_variations),
    )

    try:
        settings = get_settings()
        llm = LLMFactory.create_embedding_provider(settings)

        diff_for_embed, diff_was_trunc = truncate_for_embedding_api(diff_content)
        if diff_was_trunc:
            logger.info(
                "[VALIDATION] Diff truncated to %s chars for embedding (8192-token API limit)",
                len(diff_for_embed),
            )

        diff_response = await llm.get_embeddings(
            EmbeddingRequest(texts=[diff_for_embed])
        )
        diff_embedding = np.array(diff_response.embeddings[0])

        query_scores: Dict[int, float] = {}
        similarities: List[float] = []

        for idx, query in enumerate(query_variations):
            if not query or not query.strip():
                logger.warning("[VALIDATION] Query %d is empty, skipping", idx + 1)
                query_scores[idx] = 0.0
                continue

            try:
                q_for_embed, _ = truncate_for_embedding_api(query)
                query_response = await llm.get_embeddings(
                    EmbeddingRequest(texts=[q_for_embed])
                )
                query_embedding = np.array(query_response.embeddings[0])
                similarity = _cosine_similarity(diff_embedding, query_embedding)
                query_scores[idx] = float(similarity)
                similarities.append(similarity)
                logger.debug(
                    "[VALIDATION] Query %d cosine=%.3f preview=%r",
                    idx + 1,
                    similarity,
                    query[:80],
                )
            except Exception as e:
                logger.warning("[VALIDATION] Failed to embed query %d: %s", idx + 1, e)
                query_scores[idx] = 0.0

        if not similarities:
            logger.error("[VALIDATION] No valid similarities calculated")
            return {
                'avg_similarity': 0.0,
                'max_similarity': 0.0,
                'min_similarity': 0.0,
                'query_scores': query_scores
            }

        avg_sim = float(np.mean(similarities))
        max_sim = float(np.max(similarities))
        min_sim = float(np.min(similarities))

        logger.info(
            "[VALIDATION] avg=%.3f max=%.3f min=%.3f scores=%s",
            avg_sim,
            max_sim,
            min_sim,
            {k: f"{v:.3f}" for k, v in query_scores.items()},
        )

        return {
            'avg_similarity': avg_sim,
            'max_similarity': max_sim,
            'min_similarity': min_sim,
            'query_scores': query_scores
        }

    except Exception as e:
        logger.error("[VALIDATION] Validation failed: %s", e, exc_info=True)
        return {
            'avg_similarity': 0.0,
            'max_similarity': 0.0,
            'min_similarity': 0.0,
            'query_scores': {}
        }


def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)
