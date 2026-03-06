"""
Backend factory for vector database backends.
"""

from typing import Optional
import logging
from semantic_retrieval.config import VECTOR_BACKEND
from semantic_retrieval.backends.base import VectorBackend

logger = logging.getLogger(__name__)


def get_backend(conn=None) -> VectorBackend:
    """
    Get the appropriate vector backend based on configuration.
    
    Args:
        conn: Optional PostgreSQL connection (required for pgvector backend, not used for Pinecone)
    
    Returns:
        VectorBackend instance (PineconeBackend, ChromaDBBackend, or PgVectorBackend)
    
    Raises:
        ValueError: If requested backend is not available
    """
    backend_name = VECTOR_BACKEND
    
    # Pinecone is the default and preferred backend
    if backend_name == 'pinecone':
        try:
            from semantic_retrieval.backends.pinecone_backend import PineconeBackend
            backend = PineconeBackend()
            if backend.is_available():
                logger.info("Using Pinecone backend for vector storage")
                return backend
            else:
                raise ValueError("Pinecone backend is not available")
        except ImportError as e:
            raise ValueError(
                f"Pinecone backend not available: {e}. "
                f"Install with: pip install pinecone-client"
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize Pinecone backend: {e}")
    
    # ChromaDB (deprecated, kept for backward compatibility)
    elif backend_name == 'chromadb':
        try:
            from semantic_retrieval.backends.chromadb_backend import ChromaDBBackend
            logger.warning("Using ChromaDB backend (deprecated). Consider migrating to Pinecone.")
            return ChromaDBBackend()
        except ImportError:
            raise ValueError(
                "ChromaDB backend not available. Install with: pip install chromadb"
            )
    
    # pgvector (deprecated, kept for backward compatibility)
    elif backend_name == 'pgvector':
        if conn is None:
            raise ValueError("PostgreSQL connection required for pgvector backend")
        
        try:
            from semantic_retrieval.backends.pgvector_backend import PgVectorBackend
            backend = PgVectorBackend(conn)
            if backend.is_available():
                logger.warning("Using pgvector backend (deprecated). Consider migrating to Pinecone.")
                return backend
            else:
                # Fallback to ChromaDB if pgvector not available
                logger.warning("pgvector not available, falling back to ChromaDB")
                from semantic_retrieval.backends.chromadb_backend import ChromaDBBackend
                return ChromaDBBackend()
        except ImportError:
            raise ValueError("pgvector backend not available")
    
    else:
        raise ValueError(
            f"Unknown vector backend: {backend_name}. "
            f"Supported backends: 'pinecone', 'chromadb', 'pgvector'"
        )
