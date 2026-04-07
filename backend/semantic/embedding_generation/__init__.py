"""
Embedding generation module for semantic retrieval.

Generates vector embeddings for test data and stores them in vector databases.
"""

from semantic.embedding_generation.embedding_generator import store_embeddings
from semantic.embedding_generation.text_builder import build_embedding_text

__all__ = [
    'store_embeddings',
    'build_embedding_text',
]
