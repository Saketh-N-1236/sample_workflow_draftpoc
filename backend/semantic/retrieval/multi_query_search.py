"""
Multi-query search for semantic retrieval.

Performs semantic search with multiple query variations and combines
results with weighted scoring based on validation scores.
"""

import logging
from typing import List, Dict, Optional

from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest
from semantic.backends import get_backend

logger = logging.getLogger(__name__)


async def find_tests_semantic_with_multi_queries(
    conn,
    query_variations: List[str],
    validation_scores: Dict[int, float],
    similarity_threshold: Optional[float] = None,
    max_results: int = 10000,
    test_repo_id: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None
) -> List[Dict]:
    """
    Perform semantic search with multiple query variations.
    
    NEW APPROACH: Uses Pinecone only (no database queries).
    Test embeddings are generated directly from test repository files.
    
    Args:
        conn: Database connection (kept for compatibility, not used - Pinecone doesn't need DB)
        query_variations: List of query variation strings
        validation_scores: Dict mapping query_index -> validation_score
        similarity_threshold: Optional fixed threshold
        max_results: Maximum number of results to return
        test_repo_id: Optional test repository ID to filter by
        top_k: Optional top-k filtering
        top_p: Optional top-p filtering
    
    Returns:
        Combined and weighted results, sorted by weighted similarity
    """
    if not query_variations:
        return []
    
    settings = get_settings()
    llm = LLMFactory.create_embedding_provider(settings)
    backend = get_backend(conn)
    
    threshold = similarity_threshold if similarity_threshold is not None else 0.3
    
    # Get expected dimensions from provider for validation
    expected_dimensions = None
    if hasattr(llm, 'get_embedding_dimensions'):
        expected_dimensions = llm.get_embedding_dimensions()
    
    all_results = []
    seen_test_ids = set()
    
    # Search with each query variation
    for idx, query in enumerate(query_variations):
        if not query or not query.strip():
            continue
        
        try:
            # Get validation score for this query (default to 1.0 if not available)
            query_weight = validation_scores.get(idx, 1.0)
            
            # Embed query
            query_response = await llm.get_embeddings(
                EmbeddingRequest(texts=[query])
            )
            query_embedding = query_response.embeddings[0]
            
            # Search Pinecone
            results = await backend.search_similar(
                query_embedding,
                threshold,
                max_results * 2,  # Query more to ensure good coverage
                test_repo_id=test_repo_id,
                top_k=top_k,
                top_p=top_p,
                expected_dimensions=expected_dimensions
            )
            
            # Weight results by validation score
            for result in results:
                test_id = result.get('test_id')
                similarity = result.get('similarity', 0.0)
                
                # Calculate weighted similarity
                weighted_similarity = similarity * query_weight
                
                if test_id not in seen_test_ids:
                    # New result
                    result['query_weight'] = query_weight
                    result['weighted_similarity'] = weighted_similarity
                    all_results.append(result)
                    seen_test_ids.add(test_id)
                else:
                    # Update existing result if this query has higher weighted similarity
                    for existing in all_results:
                        if existing.get('test_id') == test_id:
                            existing_weighted = existing.get('weighted_similarity', 0.0)
                            if weighted_similarity > existing_weighted:
                                existing['similarity'] = similarity
                                existing['query_weight'] = query_weight
                                existing['weighted_similarity'] = weighted_similarity
                            break
            
        except Exception as e:
            logger.warning(f"Failed to search with query {idx}: {e}")
            continue
    
    # Sort by weighted similarity (descending)
    all_results.sort(key=lambda x: x.get('weighted_similarity', 0), reverse=True)
    
    # Remove internal fields before returning
    for result in all_results:
        result.pop('query_weight', None)
        result.pop('weighted_similarity', None)
    
    # Apply max_results limit
    if max_results > 0:
        all_results = all_results[:max_results]
    
    return all_results
