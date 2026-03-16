"""
Advanced RAG Orchestrator for Semantic Search.

Orchestrates the complete Advanced RAG pipeline:
1. Query Understanding (LLM)
2. Query Rewriting (LLM)
3. Multi-Query Semantic Search
4. LLM Re-ranking
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from semantic_retrieval.advanced_rag.query_understanding import QueryUnderstandingService
from semantic_retrieval.advanced_rag.query_rewriter import QueryRewriterService
from semantic_retrieval.advanced_rag.reranker import RerankerService
from semantic_retrieval.semantic_search import build_rich_change_description
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest
from semantic_retrieval.backends import get_backend
from semantic_retrieval.config import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_MAX_RESULTS,
    SEMANTIC_THRESHOLD_LENIENT,
    DEFAULT_QUALITY_THRESHOLD,
)

logger = logging.getLogger(__name__)


async def find_tests_advanced_rag(
    conn,
    changed_functions: List[Dict],
    file_changes: Optional[List[Dict]] = None,
    diff_content: Optional[str] = None,
    similarity_threshold: Optional[float] = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    test_repo_id: str = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    use_query_rewriting: bool = True,
    use_llm_reranking: bool = True,
    rerank_top_k: int = 50,
    num_query_variations: int = 3,
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD
) -> List[Dict]:
    """
    Advanced RAG pipeline for semantic test search.
    
    Args:
        conn: Database connection
        changed_functions: List of dicts with 'module' and 'function' keys
        file_changes: Optional list of file change dictionaries
        diff_content: Optional git diff content for context
        similarity_threshold: Optional fixed threshold (if None, uses adaptive)
        max_results: Maximum number of results to return
        test_repo_id: Optional[str] - Test repository ID for filtering
        top_k: Optional top K parameter for vector search
        top_p: Optional top P parameter for vector search
        use_query_rewriting: Whether to use query rewriting (default: True)
        use_llm_reranking: Whether to use LLM re-ranking (default: True)
        rerank_top_k: Number of candidates to re-rank (default: 50)
        num_query_variations: Number of query variations to generate (default: 3)
    
    Returns:
        List of test dicts with confidence scores and match details
    """
    # NOTE: Do NOT exit early when changed_functions is empty.
    # Constants, config, and data files (e.g. constants.ts, ApiEndPoints.js)
    # have no function definitions, so changed_functions is always [].
    # build_rich_change_description() has a file-name fallback that kicks in
    # when changed_functions is empty, but only if we let execution continue.
    # The query_understanding step can also work from file_changes + diff_content.
    # Only skip if we truly have nothing at all.
    if not changed_functions and not file_changes and not diff_content:
        return []
    
    logger.info("Advanced RAG Pipeline | Starting")
    
    # Step 1: Query Understanding
    understanding_service = QueryUnderstandingService()
    query_understanding = None
    
    if use_query_rewriting:
        try:
            logger.info("Advanced RAG Pipeline | Step 1: Query Understanding")
            query_understanding = await understanding_service.analyze_query_intent(
                changed_functions,
                file_changes,
                diff_content
            )
            intent_summary = query_understanding.get('primary_intent', 'N/A')[:80]
            logger.info(f"Advanced RAG Pipeline | Query Understanding completed | Intent: {intent_summary}...")
        except Exception as e:
            logger.warning(f"Advanced RAG Pipeline | Query Understanding failed: {e}")
            query_understanding = None
    else:
        logger.info("Advanced RAG Pipeline | Query Understanding skipped (disabled)")
    
    # Step 2: Build original query
    original_query = build_rich_change_description(changed_functions, file_changes, diff_content)
    if not original_query:
        logger.warning("Advanced RAG Pipeline | Could not build query description")
        return []
    
    # Step 3: Query Rewriting (if enabled)
    queries_to_search = [original_query]
    
    if use_query_rewriting and query_understanding:
        try:
            logger.info("Advanced RAG Pipeline | Step 2: Query Rewriting")
            rewriter_service = QueryRewriterService()
            rewritten_queries = await rewriter_service.rewrite_queries(
                original_query,
                query_understanding,
                num_query_variations
            )
            if rewritten_queries and len(rewritten_queries) > 1:
                queries_to_search = rewritten_queries
                logger.info(f"Advanced RAG Pipeline | Generated {len(queries_to_search)} query variations")
        except Exception as e:
            logger.warning(f"Advanced RAG Pipeline | Query Rewriting failed: {e}")
            queries_to_search = [original_query]
    
    # Step 4: Multi-Query Semantic Search
    logger.info(f"Advanced RAG Pipeline | Step 3: Semantic Search | Queries: {len(queries_to_search)}")
    
    settings = get_settings()
    embedding_provider = LLMFactory.create_embedding_provider(settings)
    
    # Log embedding provider info
    embedding_model = getattr(embedding_provider, 'embedding_model', None) or getattr(embedding_provider, '_embedding_model', 'default')
    embedding_dimensions = embedding_provider.get_embedding_dimensions() if hasattr(embedding_provider, 'get_embedding_dimensions') else None
    
    logger.info(
        f"Embedding Provider initialized | "
        f"Provider: {embedding_provider.provider_name.upper()} | "
        f"Model: {embedding_model} | "
        f"Dimensions: {embedding_dimensions or 'unknown'}"
    )
    
    backend = get_backend(conn)
    
    all_results = []
    seen_test_ids = set()
    
    # Use threshold from config or default
    threshold = similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD
    
    # Query limit for each query variation
    query_limit = max(max_results * 2, 100) if max_results > 0 else 10000
    
    for i, query in enumerate(queries_to_search):
        try:
            # Generate embedding for this query
            response = await embedding_provider.get_embeddings(
                EmbeddingRequest(texts=[query])
            )
            query_embedding = response.embeddings[0]
            
            # Get expected dimensions from provider for validation
            expected_dimensions = None
            if hasattr(embedding_provider, 'get_embedding_dimensions'):
                expected_dimensions = embedding_provider.get_embedding_dimensions()
            
            # Search with this query
            results = await backend.search_similar(
                query_embedding,
                threshold,
                query_limit,
                test_repo_id=test_repo_id,
                top_k=top_k,
                top_p=top_p,
                expected_dimensions=expected_dimensions
            )
            
            # Weight results based on query type
            # Original query gets weight 1.0, variations get slightly lower weight
            weight = 1.0 if i == 0 else 0.9
            
            for result in results:
                test_id = result.get('test_id')
                if test_id not in seen_test_ids:
                    result['query_weight'] = weight
                    all_results.append(result)
                    seen_test_ids.add(test_id)
                else:
                    # Boost existing result if found by multiple queries
                    for existing in all_results:
                        if existing.get('test_id') == test_id:
                            existing['query_weight'] = max(existing.get('query_weight', 1.0), weight)
                            # Boost similarity if this query found it with higher similarity
                            existing['similarity'] = max(
                                existing.get('similarity', 0),
                                result.get('similarity', 0)
                            )
                            break
            
            logger.debug(f"Query {i+1}/{len(queries_to_search)} found {len(results)} results")
            
        except Exception as e:
            logger.warning(f"Failed to process query variation {i+1}: {e}")
            continue
    
    # Calculate weighted similarity
    for result in all_results:
        weighted_sim = result.get('similarity', 0) * result.get('query_weight', 1.0)
        result['weighted_similarity'] = weighted_sim
    
    # Sort by weighted similarity
    all_results.sort(key=lambda x: x.get('weighted_similarity', 0), reverse=True)
    
    # Remove temporary fields
    for result in all_results:
        result.pop('query_weight', None)
        result.pop('weighted_similarity', None)
    
    logger.info(f"Advanced RAG Pipeline | Semantic Search completed | Results: {len(all_results)}")
    
    # Step 5: LLM Re-ranking (if enabled)
    if use_llm_reranking and len(all_results) > 0:
        logger.info("Advanced RAG Pipeline | Step 4: LLM Re-ranking")
        try:
            # Re-rank ALL candidates for quality-based filtering
            # Advanced RAG should assess all results to determine true relevance
            # Cap at 200 for performance, but prioritize quality over quantity
            effective_rerank_k = min(200, len(all_results))
            reranker_service = RerankerService()
            all_results = await reranker_service.rerank_with_llm(
                all_results[:effective_rerank_k],  # Re-rank top candidates
                diff_content,
                query_understanding,
                effective_rerank_k
            )
            
            # Sort by rerank_score (highest first) - quality-based ranking
            all_results.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
            
            logger.info(f"Advanced RAG Pipeline | Re-ranking completed | Results: {len(all_results)}")
        except Exception as e:
            logger.warning(f"Advanced RAG Pipeline | Re-ranking failed: {e}")
            # Fallback: sort by similarity
            all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
    else:
        # Sort by similarity if re-ranking is disabled
        all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
    
    # Quality-based filtering: Use Advanced RAG scores to filter, not arbitrary count
    # Advanced RAG determines quality - we trust its assessment
    if use_llm_reranking:
        # Filter by quality threshold: only return tests with rerank_score >= threshold
        # This ensures we only return truly relevant tests based on LLM assessment
        # NO arbitrary max_results limit - quality determines quantity
        filtered_results = []
        rerank_scores_present = False
        
        for result in all_results:
            rerank_score = result.get('rerank_score')
            if rerank_score is not None:
                rerank_scores_present = True
                if rerank_score >= quality_threshold:
                    filtered_results.append(result)
            else:
                # If rerank_score is not present (re-ranking failed), use similarity as fallback
                # Only include if similarity is above threshold
                similarity = result.get('similarity', 0.0)
                if similarity >= quality_threshold:
                    filtered_results.append(result)
        
        all_results = filtered_results
        
        if rerank_scores_present:
            logger.info(f"Advanced RAG Pipeline | Quality filtering | Passed: {len(all_results)} | Threshold: {quality_threshold}")
        else:
            logger.warning(f"Advanced RAG Pipeline | Quality filtering | Using similarity fallback | Passed: {len(all_results)}")
        
        # Only apply safety limit if results are excessive (e.g., > 500)
        # This prevents system overload but prioritizes quality
        safety_limit = 500
        if len(all_results) > safety_limit:
            logger.warning(f"Advanced RAG Pipeline | Results exceed safety limit | Truncating to {safety_limit}")
            all_results = all_results[:safety_limit]
    else:
        # Fallback: apply max_results limit if re-ranking is disabled
        if max_results > 0:
            all_results = all_results[:max_results]
    
    # Set confidence scores using re-ranking scores when available
    # Advanced RAG provides quality scores - use them for both confidence and similarity
    for result in all_results:
        rerank_score = result.get('rerank_score')
        original_similarity = result.get('similarity', 0)
        
        if rerank_score is not None:
            # Use rerank_score as the primary quality indicator
            # Convert rerank_score (0-1) to confidence (0-100) - full scale for quality
            result['confidence_score'] = int(rerank_score * 100)
            # Update similarity to rerank_score for UI consistency
            # This ensures similarity reflects actual relevance, not just vector similarity
            result['similarity'] = rerank_score
        else:
            # Fallback: use original similarity (shouldn't happen if re-ranking worked)
            result['confidence_score'] = int(original_similarity * 60)  # Cap at 60 for semantic-only
            result['similarity'] = original_similarity
        
        result['match_type'] = 'semantic'
    
    logger.info(f"Advanced RAG Pipeline | Completed | Final results: {len(all_results)}")
    
    return all_results
