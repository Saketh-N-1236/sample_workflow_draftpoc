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
    
    def _ensure_index(self, required_dimension: Optional[int] = None):
        """
        Ensure Pinecone index exists, create if it doesn't.
        If required_dimension is provided and index exists with different dimension,
        recreates the index with the correct dimension.
        
        Args:
            required_dimension: Required dimension for the index. If provided and index
                               exists with different dimension, index will be recreated.
        """
        try:
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                # Create index with cosine similarity metric
                dimension = required_dimension or EMBEDDING_DIMENSIONS
                logger.info(f"Creating Pinecone index: {self.index_name} with dimension {dimension}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=dimension,
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region=self.environment
                    )
                )
                logger.info(f"Pinecone index '{self.index_name}' created successfully")
            else:
                logger.info(f"Pinecone index '{self.index_name}' already exists")
                
                # Check dimension if required_dimension is provided
                if required_dimension is not None:
                    try:
                        temp_index = self.pc.Index(self.index_name)
                        index_stats = temp_index.describe_index_stats()
                        existing_dimension = index_stats.get('dimension')
                        
                        if existing_dimension is not None and existing_dimension != required_dimension:
                            logger.warning(
                                f"Pinecone index '{self.index_name}' has dimension {existing_dimension}, "
                                f"but {required_dimension} is required. Recreating index..."
                            )
                            self._recreate_index_with_dimension(required_dimension)
                    except Exception as e:
                        logger.warning(f"Could not check index dimension: {e}")
        except Exception as e:
            logger.error(f"Failed to ensure Pinecone index: {e}")
            raise
    
    def _recreate_index_with_dimension(self, dimension: int):
        """
        Delete and recreate the Pinecone index with the specified dimension.
        WARNING: This will delete all existing vectors in the index!
        
        Args:
            dimension: The dimension for the new index
        """
        import time
        
        try:
            # Get current vector count for warning
            temp_index = self.pc.Index(self.index_name)
            stats = temp_index.describe_index_stats()
            vector_count = stats.get('total_vector_count', 0)
            
            if vector_count > 0:
                logger.warning(
                    f"WARNING: Recreating index '{self.index_name}' will delete {vector_count} existing vectors. "
                    f"This is necessary to fix the dimension mismatch."
                )
            
            # Delete the existing index
            logger.info(f"Deleting Pinecone index '{self.index_name}'...")
            self.pc.delete_index(self.index_name)
            
            # Wait for deletion to complete (Pinecone may take a moment)
            time.sleep(3)
            
            # Recreate with correct dimension
            logger.info(f"Creating Pinecone index '{self.index_name}' with dimension {dimension}...")
            self.pc.create_index(
                name=self.index_name,
                dimension=dimension,
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='aws',
                    region=self.environment
                )
            )
            
            # Wait for index to be ready
            time.sleep(2)
            
            logger.info(f"Pinecone index '{self.index_name}' recreated successfully with dimension {dimension}")
        except Exception as e:
            logger.error(f"Failed to recreate Pinecone index: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if Pinecone backend is available."""
        try:
            return self.index is not None and PINECONE_AVAILABLE
        except Exception:
            return False
    
    async def delete_embeddings_by_repo(self, test_repo_id: str) -> int:
        """
        Delete all embeddings for a specific test repository.
        
        Args:
            test_repo_id: Test repository ID to delete embeddings for
            
        Returns:
            Number of embeddings deleted
        """
        if not self.is_available():
            logger.warning("Pinecone backend is not available, cannot delete embeddings")
            return 0
        
        if not test_repo_id:
            logger.warning("test_repo_id is required to delete embeddings")
            return 0
        
        try:
            # Get index dimension for dummy vector
            try:
                index_stats = self.index.describe_index_stats()
                index_dimension = index_stats.get('dimension', 768)
            except Exception:
                index_dimension = 768
            
            # Query all vectors with matching test_repo_id
            # Use a dummy vector (all zeros) with metadata filter
            dummy_vector = [0.0] * index_dimension
            filter_dict = {"test_repo_id": {"$eq": str(test_repo_id)}}
            
            # Query with max top_k to get all matching vectors
            query_result = self.index.query(
                vector=dummy_vector,
                top_k=10000,  # Pinecone max
                filter=filter_dict,
                include_metadata=True
            )
            
            # Collect all vector IDs to delete
            vector_ids_to_delete = []
            for match in query_result.matches:
                metadata = match.metadata or {}
                metadata_repo_id = metadata.get('test_repo_id', '')
                # Check if test_repo_id matches in metadata OR if vector ID starts with test_repo_id
                # (handles both old format with just test_id and new format with "{test_repo_id}_{test_id}")
                if metadata_repo_id == str(test_repo_id) or match.id.startswith(f"{test_repo_id}_"):
                    if match.id not in vector_ids_to_delete:
                        vector_ids_to_delete.append(match.id)
            
            # Delete vectors in batches (Pinecone supports batch delete)
            if vector_ids_to_delete:
                # Pinecone delete_all doesn't support filters, so we delete by IDs
                # Delete in batches of 1000 (Pinecone limit)
                batch_size = 1000
                deleted_count = 0
                for i in range(0, len(vector_ids_to_delete), batch_size):
                    batch_ids = vector_ids_to_delete[i:i + batch_size]
                    try:
                        self.index.delete(ids=batch_ids)
                        deleted_count += len(batch_ids)
                        logger.info(f"Deleted {len(batch_ids)} embeddings for test_repo_id '{test_repo_id}' (batch {i//batch_size + 1})")
                    except Exception as e:
                        logger.warning(f"Failed to delete batch of embeddings: {e}")
                
                logger.info(f"Deleted {deleted_count} total embeddings for test_repo_id '{test_repo_id}'")
                return deleted_count
            else:
                logger.info(f"No embeddings found for test_repo_id '{test_repo_id}' to delete")
                return 0
                
        except Exception as e:
            logger.error(f"Failed to delete embeddings for test_repo_id '{test_repo_id}': {e}")
            return 0
    
    async def store_embeddings(self, tests: List[Dict], embeddings: List[List[float]], delete_existing: bool = False) -> tuple:
        """
        Store embeddings in Pinecone.
        
        Args:
            tests: List of test dictionaries
            embeddings: List of embedding vectors
            delete_existing: If True, delete existing embeddings for the test_repo_id before storing new ones
            
        Returns:
            Tuple of (stored_count, failed_count)
        """
        if len(tests) != len(embeddings):
            raise ValueError("Tests and embeddings lists must have same length")
        
        if not self.is_available():
            raise RuntimeError("Pinecone backend is not available")
        
        # Delete existing embeddings for the repository if requested
        if delete_existing and tests:
            # Get test_repo_id from first test (all should have the same test_repo_id)
            test_repo_id = tests[0].get('test_repo_id')
            if test_repo_id:
                logger.info(f"Deleting existing embeddings for test_repo_id '{test_repo_id}' before storing new ones...")
                deleted_count = await self.delete_embeddings_by_repo(test_repo_id)
                logger.info(f"Deleted {deleted_count} existing embeddings for test_repo_id '{test_repo_id}'")
        
        # Get index dimension for validation
        index_dimension = None
        try:
            index_stats = self.index.describe_index_stats()
            index_dimension = index_stats.get('dimension')
        except Exception as e:
            logger.warning(f"Could not get index dimension: {e}")
        
        vectors_to_upsert = []
        stored = 0
        failed = 0
        dimension_mismatches = 0
        
        for test, embedding in zip(tests, embeddings):
            try:
                test_id = test.get('test_id')
                if not test_id:
                    failed += 1
                    continue
                
                # Validate embedding dimension matches index dimension
                embedding_dim = len(embedding)
                if index_dimension is not None and embedding_dim != index_dimension:
                    logger.error(
                        f"Dimension mismatch for test {test_id}: "
                        f"embedding has {embedding_dim} dimensions, "
                        f"but index expects {index_dimension} dimensions. "
                        f"Please recreate the Pinecone index with dimension {embedding_dim} "
                        f"or use an embedding provider that produces {index_dimension}-dimensional vectors."
                    )
                    failed += 1
                    dimension_mismatches += 1
                    continue
                
                # Prepare comprehensive metadata (Pinecone metadata must be flat key-value pairs)
                # Convert complex types to strings for Pinecone compatibility
                markers = test.get('markers', [])
                if isinstance(markers, list):
                    markers_str = ','.join(str(m) for m in markers) if markers else ''
                else:
                    markers_str = str(markers) if markers else ''
                
                # Get test_repo_id for unique vector ID generation
                test_repo_id = test.get('test_repo_id', '')
                
                # Use test_content_summary if available (from build_embedding_text), otherwise use description
                # Truncate to PINECONE_DESCRIPTION_MAX_CHARS (1000) for Pinecone metadata
                from semantic_retrieval.config import PINECONE_DESCRIPTION_MAX_CHARS
                description_for_metadata = test.get('test_content_summary') or test.get('description', '')
                description_for_metadata = str(description_for_metadata)[:PINECONE_DESCRIPTION_MAX_CHARS]
                
                metadata = {
                    'test_id': str(test_id),  # Include test_id in metadata for easy lookup
                    'method_name': str(test.get('method_name', '')),
                    'class_name': str(test.get('class_name', '') or ''),
                    'test_file_path': str(test.get('file_path', '')),
                    'test_type': str(test.get('test_type', 'unknown')),
                    'description': description_for_metadata,  # Test content summary or description (first 1000 chars)
                    'line_number': str(test.get('line_number', '')) if test.get('line_number') else '',
                    'language': str(test.get('language', 'python')),
                    'is_async': 'true' if test.get('is_async', False) else 'false',
                    'markers': markers_str,
                    'module': str(test.get('module', '')),
                    'test_repo_id': str(test_repo_id) if test_repo_id else ''  # Store test_repo_id for filtering
                }
                
                # Pinecone requires string IDs
                # IMPORTANT: Include test_repo_id in vector ID to ensure uniqueness across repositories
                # This prevents embeddings from different repositories from overwriting each other
                if test_repo_id:
                    vector_id = f"{test_repo_id}_{test_id}"
                else:
                    # Fallback for old embeddings without test_repo_id (backward compatibility)
                    vector_id = str(test_id)
                    logger.warning(
                        f"Test {test_id} has no test_repo_id. Using test_id as vector_id. "
                        f"This may cause conflicts if the same test_id exists in multiple repositories."
                    )
                
                vectors_to_upsert.append({
                    'id': vector_id,
                    'values': embedding,
                    'metadata': metadata
                })
                
            except Exception as e:
                logger.warning(f"Failed to prepare vector for test {test.get('test_id', 'unknown')}: {e}")
                failed += 1
                continue
        
        if dimension_mismatches > 0:
            logger.error(
                f"Stopped storing embeddings: {dimension_mismatches} dimension mismatch(es) detected. "
                f"Index dimension: {index_dimension}, Embedding dimension: {len(embeddings[0]) if embeddings else 'unknown'}. "
                f"Please recreate the Pinecone index with the correct dimension or use a matching embedding provider."
            )
            return 0, failed
        
        # Batch upsert to Pinecone (max 100 vectors per batch)
        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i:i + batch_size]
            try:
                self.index.upsert(vectors=batch)
                stored += len(batch)
                logger.debug(f"Upserted batch {i//batch_size + 1}: {len(batch)} vectors")
            except Exception as e:
                error_msg = str(e)
                # Check if error is due to dimension mismatch
                if "dimension" in error_msg.lower() or "400" in error_msg:
                    logger.error(
                        f"Failed to upsert batch {i//batch_size + 1} due to dimension mismatch: {e}. "
                        f"Index dimension: {index_dimension}, Embedding dimension: {len(batch[0]['values']) if batch else 'unknown'}. "
                        f"Please recreate the Pinecone index with dimension {len(batch[0]['values']) if batch else 'unknown'} "
                        f"or use an embedding provider that produces {index_dimension}-dimensional vectors."
                    )
                else:
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
        test_repo_id: Optional[str] = None,
        expected_dimensions: Optional[int] = None
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
            expected_dimensions: Expected embedding dimensions (for validation)
            
        Returns:
            List of test dictionaries with similarity scores
        """
        if not self.is_available():
            logger.error("Pinecone backend is not available")
            return []
        
        # Validate embedding dimensions
        query_dim = len(query_embedding)
        if expected_dimensions and query_dim != expected_dimensions:
            logger.error(
                f"Embedding dimension mismatch: Query has {query_dim} dimensions, "
                f"but expected {expected_dimensions}. This usually means the embedding "
                f"provider/model has changed. You may need to recreate the Pinecone index "
                f"or regenerate embeddings with the correct provider."
            )
            return []
        
        # Check index dimensions
        try:
            index_stats = self.index.describe_index_stats()
            index_dimension = index_stats.get('dimension', None)
            
            if index_dimension and query_dim != index_dimension:
                logger.error(
                    f"Pinecone dimension mismatch: Query embedding has {query_dim} dimensions, "
                    f"but Pinecone index '{self.index_name}' was created with {index_dimension} dimensions. "
                    f"This usually happens when switching embedding providers (e.g., from Ollama 768-dim "
                    f"to OpenAI 1536-dim). Solutions:\n"
                    f"  1. Use the same embedding provider that was used to create the index\n"
                    f"  2. Delete and recreate the Pinecone index with the new dimensions\n"
                    f"  3. Regenerate all embeddings with the new provider"
                )
                return []
        except Exception as e:
            logger.warning(f"Could not verify index dimensions: {e}")
        
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
