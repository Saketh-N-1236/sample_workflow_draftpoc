"""
Configuration constants for semantic search.
"""

import os
from pathlib import Path

# Vector backend selection (only 'pinecone' is supported)
VECTOR_BACKEND = os.getenv('VECTOR_BACKEND', 'pinecone').lower()

# Pinecone configuration
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY', '')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME', 'test-embeddings')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT', 'us-east-1')

# Default similarity threshold (0.3 = 30% similarity minimum)
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

# Advanced RAG default configuration
DEFAULT_USE_ADVANCED_RAG = True
DEFAULT_USE_QUERY_REWRITING = True
DEFAULT_USE_LLM_RERANKING = True
DEFAULT_RERANK_TOP_K = 50
DEFAULT_NUM_QUERY_VARIATIONS = 3
# Quality threshold for Advanced RAG filtering (0.0-1.0)
# Only tests with rerank_score >= this threshold will be returned
DEFAULT_QUALITY_THRESHOLD = 0.3  # 30% minimum relevance (lowered from 0.4 to reduce false negatives)

# Test content token limits per provider (approximate chars per token: ~4)
TEST_CONTENT_MAX_TOKENS = {
    'openai': 2000,   # ~8000 chars
    'ollama': 400,    # ~1600 chars
    'gemini': 1500    # ~6000 chars
}

# Pinecone metadata description max length
PINECONE_DESCRIPTION_MAX_CHARS = 1000