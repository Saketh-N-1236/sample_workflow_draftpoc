"""
Backend factory for vector database backends.

Only Pinecone is supported as the vector backend.
One Pinecone client/index handle is cached per process so RAG + AST supplement
(and any other step in the same request) do not reconnect and re-log initialization.
"""

import logging
import threading
from typing import Optional

from semantic.config import VECTOR_BACKEND
from semantic.backends.base import VectorBackend

logger = logging.getLogger(__name__)

_backend_lock = threading.Lock()
_cached_backend: Optional[VectorBackend] = None


def get_backend(conn=None) -> VectorBackend:
    """
    Get the Pinecone vector backend (singleton per process).

    Args:
        conn: Optional PostgreSQL connection (not used, kept for compatibility)

    Returns:
        VectorBackend instance (PineconeBackend)

    Raises:
        ValueError: If Pinecone backend is not available
    """
    global _cached_backend

    backend_name = VECTOR_BACKEND or 'pinecone'

    if backend_name != 'pinecone':
        raise ValueError(
            f"Unsupported vector backend: {backend_name}. "
            f"Only 'pinecone' is supported. Set VECTOR_BACKEND=pinecone in your .env file."
        )

    with _backend_lock:
        if _cached_backend is not None:
            try:
                if _cached_backend.is_available():
                    logger.debug("Reusing cached Pinecone vector backend")
                    return _cached_backend
            except Exception:
                _cached_backend = None

        try:
            from semantic.backends.pinecone_backend import PineconeBackend

            backend = PineconeBackend()
            if not backend.is_available():
                raise ValueError(
                    "Pinecone backend is not available. Check your PINECONE_API_KEY and "
                    "PINECONE_ENVIRONMENT configuration."
                )
            _cached_backend = backend
            logger.info(
                "Pinecone vector backend initialized (process-wide singleton; reused across calls)"
            )
            return backend
        except ImportError as e:
            raise ValueError(
                f"Pinecone backend not available: {e}. "
                f"Install with: pip install pinecone-client"
            ) from e
        except Exception as e:
            raise ValueError(f"Failed to initialize Pinecone backend: {e}") from e


def reset_backend_cache_for_tests() -> None:
    """Clear singleton (unit tests only)."""
    global _cached_backend
    with _backend_lock:
        _cached_backend = None
