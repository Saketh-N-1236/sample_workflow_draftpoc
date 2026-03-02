"""
ChromaDB backend implementation for vector storage and search.
"""

import os
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings

from semantic_retrieval.backends.base import VectorBackend
from semantic_retrieval.config import CHROMADB_DATA_PATH, SEMANTIC_SCORE_CAP


class ChromaDBBackend(VectorBackend):
    """
    ChromaDB implementation of vector backend.
    
    Uses persistent ChromaDB client to store and search embeddings.
    Collection name: 'test_embeddings'
    """
    
    def __init__(self, data_path: str = None):
        """
        Initialize ChromaDB backend.
        
        Args:
            data_path: Path to ChromaDB data directory (defaults to CHROMADB_DATA_PATH)
        """
        self.data_path = Path(data_path or CHROMADB_DATA_PATH)
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB persistent client
        self.client = chromadb.PersistentClient(
            path=str(self.data_path),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Get or create collection with cosine distance metric
        # ChromaDB supports: "l2", "ip" (inner product), "cosine"
        # For cosine similarity, we use "cosine" distance metric
        try:
            self.collection = self.client.get_collection(
                name="test_embeddings"
            )
            # Check if collection exists but has wrong metric - we'd need to recreate it
            # For now, we'll handle the distance conversion in search_similar
        except Exception:
            # Collection doesn't exist, create it with cosine metric
            self.collection = self.client.create_collection(
                name="test_embeddings",
                metadata={"description": "Test embeddings for semantic search"},
                # Note: ChromaDB doesn't directly support cosine in create_collection
                # We'll use L2 and convert, or use inner product
            )
    
    def is_available(self) -> bool:
        """Check if ChromaDB backend is available."""
        try:
            # Try to access the collection
            _ = self.collection.count()
            return True
        except Exception:
            return False
    
    async def store_embeddings(self, tests: List[Dict], embeddings: List[List[float]]) -> tuple:
        """
        Store embeddings for tests in ChromaDB.
        
        Args:
            tests: List of test dictionaries
            embeddings: List of embedding vectors
        
        Returns:
            Tuple of (stored_count, failed_count)
        """
        if len(tests) != len(embeddings):
            raise ValueError(f"Mismatch: {len(tests)} tests but {len(embeddings)} embeddings")
        
        stored = 0
        failed = 0
        
        # Prepare data for batch insert
        ids = []
        embeddings_list = []
        metadatas = []
        
        for test, embedding in zip(tests, embeddings):
            try:
                test_id = test['test_id']
                ids.append(test_id)
                embeddings_list.append(embedding)
                metadatas.append({
                    'test_id': test_id,
                    'method_name': test.get('method_name', ''),
                    'class_name': test.get('class_name', ''),
                    'test_file_path': test.get('file_path', ''),
                    'test_type': test.get('test_type', 'unit')
                })
            except Exception as e:
                failed += 1
                continue
        
        # Batch upsert to ChromaDB
        if ids:
            try:
                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings_list,
                    metadatas=metadatas
                )
                stored = len(ids)
            except Exception as e:
                # If batch fails, try individual inserts
                for i, test_id in enumerate(ids):
                    try:
                        self.collection.upsert(
                            ids=[test_id],
                            embeddings=[embeddings_list[i]],
                            metadatas=[metadatas[i]]
                        )
                        stored += 1
                    except Exception:
                        failed += 1
        
        return stored, failed
    
    async def search_similar(
        self, 
        query_embedding: List[float],
        similarity_threshold: float,
        max_results: int
    ) -> List[Dict]:
        """
        Search for similar tests using cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            similarity_threshold: Minimum similarity (0.0 to 1.0)
            max_results: Maximum results to return
        
        Returns:
            List of test dictionaries with similarity scores
        """
        # ChromaDB uses distance (lower is better), we need similarity (higher is better)
        # ChromaDB's query returns results sorted by distance ascending
        # We'll filter by converting distance to similarity
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=max_results * 2,  # Get more to filter by threshold
            include=['metadatas', 'distances']
        )
        
        # Process results
        output = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i, test_id in enumerate(results['ids'][0]):
                # ChromaDB by default uses L2 (Euclidean) distance, not cosine
                # L2 distances are typically much larger (e.g., 100-200 for 768-dim vectors)
                # Convert L2 distance to similarity using: similarity = 1 / (1 + distance/scale)
                distance = results['distances'][0][i]
                
                # If distance > 10, it's L2, not cosine
                # Normalize L2 to similarity: use exponential decay
                # For 768-dim normalized vectors, typical L2 range is 0-200
                if distance > 10:
                    # L2 distance - convert to similarity (0-1)
                    # Scale factor: divide by ~100 to normalize typical distances
                    # Then use 1/(1+x) to map to 0-1 range
                    similarity = 1.0 / (1.0 + distance / 100.0)
                else:
                    # Assume cosine distance (0-2 range)
                    similarity = 1.0 - (distance / 2.0)
                
                # Filter by threshold
                if similarity >= similarity_threshold:
                    metadata = results['metadatas'][0][i]
                    output.append({
                        'test_id': test_id,
                        'method_name': metadata.get('method_name', ''),
                        'class_name': metadata.get('class_name', ''),
                        'test_file_path': metadata.get('test_file_path', ''),
                        'test_type': metadata.get('test_type', 'unit'),
                        'match_type': 'semantic',
                        'similarity': round(similarity, 3),
                        'confidence_score': int(similarity * SEMANTIC_SCORE_CAP)
                    })
                    
                    # Stop if we have enough results
                    if len(output) >= max_results:
                        break
        
        return output
