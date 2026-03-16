"""
Backend factory for vector database backends.

Only Pinecone is supported as the vector backend.
"""

import logging
from semantic_retrieval.config import VECTOR_BACKEND
from semantic_retrieval.backends.base import VectorBackend

logger = logging.getLogger(__name__)


def get_backend(conn=None) -> VectorBackend:
    """
    Get the Pinecone vector backend.
    
    Args:
        conn: Optional PostgreSQL connection (not used, kept for compatibility)
    
    Returns:
        VectorBackend instance (PineconeBackend)
    
    Raises:
        ValueError: If Pinecone backend is not available
    """
    backend_name = VECTOR_BACKEND or 'pinecone'
    
    # Only Pinecone is supported
    if backend_name != 'pinecone':
        raise ValueError(
            f"Unsupported vector backend: {backend_name}. "
            f"Only 'pinecone' is supported. Set VECTOR_BACKEND=pinecone in your .env file."
        )
    
    try:
        from semantic_retrieval.backends.pinecone_backend import PineconeBackend
        backend = PineconeBackend()
        if backend.is_available():
            logger.info("Using Pinecone backend for vector storage")
            return backend
        else:
            raise ValueError("Pinecone backend is not available. Check your PINECONE_API_KEY and PINECONE_ENVIRONMENT configuration.")
    except ImportError as e:
        raise ValueError(
            f"Pinecone backend not available: {e}. "
            f"Install with: pip install pinecone-client"
        )
    except Exception as e:
        raise ValueError(f"Failed to initialize Pinecone backend: {e}")
