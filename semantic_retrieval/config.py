"""
Configuration constants for semantic search.
"""

import os
from pathlib import Path

# Vector backend selection ('chromadb' or 'pgvector')
VECTOR_BACKEND = os.getenv('VECTOR_BACKEND', 'chromadb').lower()

# ChromaDB data path (default: semantic_retrieval/chromadb_data)
_default_chromadb_path = Path(__file__).parent / "chromadb_data"
CHROMADB_DATA_PATH = os.getenv('CHROMADB_DATA_PATH', str(_default_chromadb_path))

# Default similarity threshold (0.3 = 30% similarity minimum)
# Note: ChromaDB uses L2 distance, converted to similarity, so scores are typically 0.2-0.5
# Lower threshold (0.3) allows more semantic matches while still filtering noise
DEFAULT_SIMILARITY_THRESHOLD = 0.3

# Maximum number of results to return from semantic search
DEFAULT_MAX_RESULTS = 20

# Embedding dimensions (nomic-embed-text produces 768-dimensional vectors)
EMBEDDING_DIMENSIONS = 768

# Batch size for embedding generation
BATCH_SIZE = 10

# Semantic score cap (so semantic never outranks exact matches)
SEMANTIC_SCORE_CAP = 60
