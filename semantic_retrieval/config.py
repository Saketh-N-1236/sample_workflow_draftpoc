"""
Configuration constants for semantic search.
"""

import os
from pathlib import Path

# Vector backend selection ('pinecone', 'chromadb', or 'pgvector')
VECTOR_BACKEND = os.getenv('VECTOR_BACKEND', 'pinecone').lower()

# Pinecone configuration
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY', '')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME', 'test-embeddings')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT', 'us-east-1')

# ChromaDB data path (default: semantic_retrieval/chromadb_data)
# Deprecated: Use Pinecone instead
_default_chromadb_path = Path(__file__).parent / "chromadb_data"
CHROMADB_DATA_PATH = os.getenv('CHROMADB_DATA_PATH', str(_default_chromadb_path))

# Default similarity threshold (0.3 = 30% similarity minimum)
# Note: ChromaDB uses L2 distance, converted to similarity, so scores are typically 0.2-0.5
# Lower threshold (0.3) allows more semantic matches while still filtering noise
DEFAULT_SIMILARITY_THRESHOLD = 0.3

# Maximum number of results to return from semantic search
# Set to a very high number to effectively remove limit (10,000 should be more than enough)
DEFAULT_MAX_RESULTS = 10000

# Embedding dimensions (nomic-embed-text produces 768-dimensional vectors)
EMBEDDING_DIMENSIONS = 768

# Batch size for embedding generation
BATCH_SIZE = 10

# Semantic score cap (so semantic never outranks exact matches)
SEMANTIC_SCORE_CAP = 60

# Adaptive similarity thresholds (tiered fallback)
SEMANTIC_THRESHOLD_STRICT = 0.5
SEMANTIC_THRESHOLD_MODERATE = 0.4
SEMANTIC_THRESHOLD_LENIENT = 0.3
MIN_RESULTS_PER_TIER = 5
