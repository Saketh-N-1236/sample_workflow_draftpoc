"""
pgvector backend implementation for vector storage and search.
"""

from typing import List, Dict, Any
from semantic_retrieval.backends.base import VectorBackend
from semantic_retrieval.vector_utils import embedding_to_pgvector
from semantic_retrieval.config import SEMANTIC_SCORE_CAP
from deterministic.db_connection import DB_SCHEMA


class PgVectorBackend(VectorBackend):
    """
    pgvector implementation of vector backend.
    
    Uses PostgreSQL with pgvector extension for vector storage and search.
    Requires pgvector extension to be installed in PostgreSQL.
    """
    
    def __init__(self, conn):
        """
        Initialize pgvector backend.
        
        Args:
            conn: PostgreSQL database connection
        """
        self.conn = conn
    
    def is_available(self) -> bool:
        """Check if pgvector extension is available."""
        try:
            with self.conn.cursor() as cursor:
                # Check if vector extension exists
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    )
                """)
                has_extension = cursor.fetchone()[0]
                
                if not has_extension:
                    return False
                
                # Check if embedding column exists
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = 'test_metadata'
                      AND column_name = 'embedding'
                """, (DB_SCHEMA,))
                has_column = cursor.fetchone() is not None
                
                return has_column
        except Exception:
            return False
    
    async def store_embeddings(self, tests: List[Dict], embeddings: List[List[float]]) -> tuple:
        """
        Store embeddings for tests in PostgreSQL using pgvector.
        
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
        
        for test, embedding in zip(tests, embeddings):
            try:
                test_id = test['test_id']
                # Convert Python list to pgvector string format
                embedding_str = embedding_to_pgvector(embedding)
                
                with self.conn.cursor() as cursor:
                    cursor.execute(f"""
                        UPDATE {DB_SCHEMA}.test_metadata
                        SET embedding = %s::vector
                        WHERE test_id = %s
                    """, (embedding_str, test_id))
                self.conn.commit()
                stored += 1
            except Exception as e:
                self.conn.rollback()
                failed += 1
        
        return stored, failed
    
    async def search_similar(
        self, 
        query_embedding: List[float],
        similarity_threshold: float,
        max_results: int
    ) -> List[Dict]:
        """
        Search for similar tests using pgvector cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            similarity_threshold: Minimum similarity (0.0 to 1.0)
            max_results: Maximum results to return
        
        Returns:
            List of test dictionaries with similarity scores
        """
        # Convert Python list to pgvector string format
        query_embedding_str = embedding_to_pgvector(query_embedding)
        
        # pgvector cosine similarity
        # <=> = cosine DISTANCE (0=identical, 2=opposite)
        # 1 - distance = similarity (1=identical, -1=opposite)
        with self.conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    tm.test_id,
                    tr.method_name,
                    tr.class_name,
                    tr.file_path        AS test_file_path,
                    tr.test_type,
                    1 - (tm.embedding <=> %s::vector) AS similarity
                FROM {DB_SCHEMA}.test_metadata tm
                JOIN {DB_SCHEMA}.test_registry tr ON tm.test_id = tr.test_id
                WHERE tm.embedding IS NOT NULL
                  AND 1 - (tm.embedding <=> %s::vector) > %s
                ORDER BY similarity DESC
                LIMIT %s
            """, (
                query_embedding_str,
                query_embedding_str,
                similarity_threshold,
                max_results
            ))
            rows = cursor.fetchall()
        
        results = []
        for row in rows:
            test_id, method_name, class_name, test_file_path, test_type, similarity = row
            results.append({
                'test_id': test_id,
                'method_name': method_name,
                'class_name': class_name,
                'test_file_path': test_file_path,
                'test_type': test_type,
                'match_type': 'semantic',
                'similarity': round(float(similarity), 3),
                # cap at 60 — semantic never outranks exact name matches
                'confidence_score': int(float(similarity) * SEMANTIC_SCORE_CAP)
            })
        
        return results
