"""
Backend factory for vector database backends.
"""

from typing import Optional
from semantic_retrieval.config import VECTOR_BACKEND
from semantic_retrieval.backends.base import VectorBackend
from semantic_retrieval.backends.chromadb_backend import ChromaDBBackend
from semantic_retrieval.backends.pgvector_backend import PgVectorBackend


def get_backend(conn=None) -> VectorBackend:
    """
    Get the appropriate vector backend based on configuration.
    
    Args:
        conn: Optional PostgreSQL connection (required for pgvector backend)
    
    Returns:
        VectorBackend instance (ChromaDBBackend or PgVectorBackend)
    
    Raises:
        ValueError: If requested backend is not available
    """
    backend_name = VECTOR_BACKEND
    
    if backend_name == 'pgvector':
        if conn is None:
            raise ValueError("PostgreSQL connection required for pgvector backend")
        
        backend = PgVectorBackend(conn)
        if backend.is_available():
            return backend
        else:
            # Fallback to ChromaDB if pgvector not available
            print("Warning: pgvector not available, falling back to ChromaDB")
            return ChromaDBBackend()
    
    elif backend_name == 'chromadb':
        return ChromaDBBackend()
    
    else:
        raise ValueError(
            f"Unknown vector backend: {backend_name}. "
            f"Supported backends: 'chromadb', 'pgvector'"
        )
