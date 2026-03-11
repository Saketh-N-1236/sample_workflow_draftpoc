"""Pinecone backend implementation for vector storage and search."""

import os
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    logger.warning("Pinecone client not installed. Install with: pip install pinecone-client")

from semantic_retrieval.backends.base import VectorBackend
from semantic_retrieval.config import EMBEDDING_DIMENSIONS, SEMANTIC_SCORE_CAP


class PineconeBackend(VectorBackend):
    """
    Pinecone implementation of vector backend.
    
    Uses Pinecone cloud service for vector storage and search.
    Requires PINECONE_API_KEY environment variable.
    """
    
    def __init__(self, api_key: Optional[str] = None, index_name: Optional[str] = None, environment: Optional[str] = None):
        """
        Initialize Pinecone backend.
        
        Args:
            api_key: Pinecone API key (from env: PINECONE_API_KEY)
            index_name: Pinecone index name (from env: PINECONE_INDEX_NAME, default: 'test-embeddings')
            environment: Pinecone environment/region (from env: PINECONE_ENVIRONMENT, default: 'us-east-1')
        """
        if not PINECONE_AVAILABLE:
            raise ImportError(
                "Pinecone client not installed. Install with: pip install pinecone-client"
            )
        
        self.api_key = api_key or os.getenv('PINECONE_API_KEY')
        if not self.api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required")
        
        self.index_name = index_name or os.getenv('PINECONE_INDEX_NAME', 'test-embeddings')
        self.environment = environment or os.getenv('PINECONE_ENVIRONMENT', 'us-east-1')
        
        # Initialize Pinecone client
        try:
            self.pc = Pinecone(api_key=self.api_key)
            self._ensure_index()
            self.index = self.pc.Index(self.index_name)
            logger.info(f"Pinecone backend initialized with index: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise
    
    def _ensure_index(self):
        """Ensure Pinecone index exists, create if it doesn't."""
        try:
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                # Create index with cosine similarity metric
                logger.info(f"Creating Pinecone index: {self.index_name}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=EMBEDDING_DIMENSIONS,
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region=self.environment
                    )
                )
                logger.info(f"Pinecone index '{self.index_name}' created successfully")
            else:
                logger.info(f"Pinecone index '{self.index_name}' already exists")
        except Exception as e:
            logger.error(f"Failed to ensure Pinecone index: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if Pinecone backend is available."""
        try:
            return self.index is not None and PINECONE_AVAILABLE
        except Exception:
            return False
    
    async def store_embeddings(self, tests: List[Dict], embeddings: List[List[float]]) -> tuple:
        """
        Store embeddings in Pinecone.
        
        Args:
            tests: List of test dictionaries
            embeddings: List of embedding vectors
            
        Returns:
            Tuple of (stored_count, failed_count)
        """
        if len(tests) != len(embeddings):
            raise ValueError("Tests and embeddings lists must have same length")
        
        if not self.is_available():
            raise RuntimeError("Pinecone backend is not available")
        
        vectors_to_upsert = []
        stored = 0
        failed = 0
        
        for test, embedding in zip(tests, embeddings):
            try:
                test_id = test.get('test_id')
                if not test_id:
                    failed += 1
                    continue
                
                # Prepare comprehensive metadata (Pinecone metadata must be flat key-value pairs)
                # Convert complex types to strings for Pinecone compatibility
                markers = test.get('markers', [])
                if isinstance(markers, list):
                    markers_str = ','.join(str(m) for m in markers) if markers else ''
                else:
                    markers_str = str(markers) if markers else ''
                
                metadata = {
                    'test_id': str(test_id),  # Include test_id in metadata for easy lookup
                    'method_name': str(test.get('method_name', '')),
                    'class_name': str(test.get('class_name', '') or ''),
                    'test_file_path': str(test.get('file_path', '')),
                    'test_type': str(test.get('test_type', 'unknown')),
                    'description': str(test.get('description', ''))[:500],  # Limit description length
                    'line_number': str(test.get('line_number', '')) if test.get('line_number') else '',
                    'language': str(test.get('language', 'python')),
                    'is_async': 'true' if test.get('is_async', False) else 'false',
                    'markers': markers_str,
                    'module': str(test.get('module', '')),
                    'test_repo_id': str(test.get('test_repo_id', '')) if test.get('test_repo_id') else ''  # Store test_repo_id for filtering
                }
                
                # Pinecone requires string IDs
                vector_id = str(test_id)
                
                vectors_to_upsert.append({
                    'id': vector_id,
                    'values': embedding,
                    'metadata': metadata
                })
                
            except Exception as e:
                logger.warning(f"Failed to prepare vector for test {test.get('test_id', 'unknown')}: {e}")
                failed += 1
                continue
        
        # Batch upsert to Pinecone (max 100 vectors per batch)
        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i:i + batch_size]
            try:
                self.index.upsert(vectors=batch)
                stored += len(batch)
                logger.debug(f"Upserted batch {i//batch_size + 1}: {len(batch)} vectors")
            except Exception as e:
                logger.error(f"Failed to upsert batch {i//batch_size + 1}: {e}")
                failed += len(batch)
        
        logger.info(f"Pinecone storage complete: {stored} stored, {failed} failed")
        return stored, failed
    
    async def search_similar(
        self,
        query_embedding: List[float],
        similarity_threshold: float,
        max_results: int,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        test_repo_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for similar tests using Pinecone cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            similarity_threshold: Minimum similarity (0.0 to 1.0)
            max_results: Maximum results to return
            top_k: Optional top K parameter for vector search
            top_p: Optional top P parameter for nucleus sampling
            test_repo_id: Optional test repository ID to filter results
            
        Returns:
            List of test dictionaries with similarity scores
        """
        if not self.is_available():
            logger.error("Pinecone backend is not available")
            return []
        
        try:
            # Pinecone uses cosine similarity (0-1, where 1 is most similar)
            # Query with top_k (we'll filter by threshold after)
            # Use top_k from config if provided, otherwise use max_results
            # Pinecone max is 10,000
            query_top_k = top_k if top_k is not None and top_k > 0 else (min(max_results, 10000) if max_results > 0 else 10000)
            
            results = self.index.query(
                vector=query_embedding,
                top_k=query_top_k,
                include_metadata=True
            )
            
            # Filter by threshold and format results
            formatted_results = []
            cumulative_prob = 0.0
            
            for match in results.matches:
                score = match.score  # Pinecone returns similarity (0-1)
                
                if score >= similarity_threshold:
                    metadata = match.metadata or {}
                    
                    # Filter by test_repo_id if provided
                    if test_repo_id:
                        metadata_repo_id = metadata.get('test_repo_id', '')
                        if metadata_repo_id and metadata_repo_id != test_repo_id:
                            continue  # Skip this result if test_repo_id doesn't match
                    
                    test_result = {
                        'test_id': match.id,
                        'method_name': metadata.get('method_name', ''),
                        'class_name': metadata.get('class_name', ''),
                        'test_file_path': metadata.get('test_file_path', ''),
                        'test_type': metadata.get('test_type', 'unknown'),
                        'description': metadata.get('description', ''),
                        'line_number': metadata.get('line_number', ''),
                        'language': metadata.get('language', 'python'),
                        'is_async': metadata.get('is_async', 'false') == 'true',
                        'markers': metadata.get('markers', ''),
                        'module': metadata.get('module', ''),
                        'similarity': float(score),
                        'confidence_score': min(int(score * 100), SEMANTIC_SCORE_CAP)
                    }
                    
                    # Apply top_p (nucleus sampling) if specified
                    if top_p is not None and top_p > 0:
                        # Convert similarity to probability-like score for top_p
                        # Higher similarity = higher probability
                        prob = score  # Use similarity as probability proxy
                        cumulative_prob += prob
                        if cumulative_prob > top_p:
                            break  # Stop when cumulative probability exceeds top_p
                    
                    formatted_results.append(test_result)
            
            # Sort by similarity (descending) - caller will apply final limit
            formatted_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            return formatted_results
            
        except Exception as e:
            logger.error(f"Pinecone search failed: {e}")
            return []
