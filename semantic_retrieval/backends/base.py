"""
Abstract base class for vector database backends.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class VectorBackend(ABC):
    """Abstract base class for vector database backends."""
    
    @abstractmethod
    async def store_embeddings(self, tests: List[Dict], embeddings: List[List[float]]) -> tuple:
        """
        Store embeddings for tests.
        
        Args:
            tests: List of test dictionaries with test_id, method_name, class_name, etc.
            embeddings: List of embedding vectors (each is a list of floats)
        
        Returns:
            Tuple of (stored_count, failed_count)
        """
        pass
    
    @abstractmethod
    async def search_similar(
        self, 
        query_embedding: List[float],
        similarity_threshold: float,
        max_results: int
    ) -> List[Dict]:
        """
        Search for similar tests using cosine similarity.
        
        Args:
            query_embedding: Query embedding vector (list of floats)
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            max_results: Maximum number of results to return
        
        Returns:
            List of test dictionaries with similarity scores:
            - test_id, method_name, class_name, test_file_path, test_type
            - similarity: float (0.0 to 1.0)
            - confidence_score: int (capped at SEMANTIC_SCORE_CAP)
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if backend is available/configured.
        
        Returns:
            True if backend is ready to use, False otherwise
        """
        pass
