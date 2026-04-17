"""
Configuration constants for semantic search.
"""

import os

# Vector backend selection (only 'pinecone' is supported)
VECTOR_BACKEND = os.getenv('VECTOR_BACKEND', 'pinecone').lower()

# Pinecone configuration
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY', '')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME', 'test-embeddings')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT', 'us-east-1')

# Default similarity threshold (cosine minimum for vector hits).
# Override at runtime: env SEMANTIC_VECTOR_THRESHOLD (see process_diff_programmatic).
# 0.45: scores 35-44% are vocabulary overlap (e.g. "regex" matching all regex tests
# when a diff contains a regex literal); 0.45 cuts false positives without losing
# high-signal semantic matches.  Also used by the RAG lenient-fallback path when the
# query rewriter fails — keeping this at 0.45 ensures the fallback path does not
# admit more false positives than the adaptive pipeline.
DEFAULT_SIMILARITY_THRESHOLD = 0.45

# Embedding dimensions (nomic-embed-text produces 768-dimensional vectors)
EMBEDDING_DIMENSIONS = 768

# Batch size for embedding generation
BATCH_SIZE = 10

# Semantic score cap (so semantic never outranks exact matches)
SEMANTIC_SCORE_CAP = 60

# Git diff summary as original query: use LLM summary when cosine(diff, summary) >= this
GIT_DIFF_SUMMARY_VALIDATION_THRESHOLD = 0.5

# If rewriter returns <2 queries, allow single-query search with enriched original only.
# Default on so invalid rewriter JSON does not zero out semantic retrieval; set RAG_LENIENT_FALLBACK=false to disable.
_rag_lf = os.getenv("RAG_LENIENT_FALLBACK", "true").strip().lower()
RAG_LENIENT_FALLBACK = _rag_lf not in ("0", "false", "no", "off")

# Max chars when building diff-anchor canonical text (truncation middle ellipsis)
RAG_DIFF_ANCHOR_MAX_CHARS = int(os.getenv("RAG_DIFF_ANCHOR_MAX_CHARS", "12000"))

# Pinecone metadata description max length
PINECONE_DESCRIPTION_MAX_CHARS = 1000

# LLM semantic retrieval classification controls (no numeric thresholds for pruning)
# - Top-K of semantic retrieved items to classify (or "all")
LLM_RETRIEVAL_CLASSIFY_TOP_K = os.getenv("LLM_RETRIEVAL_CLASSIFY_TOP_K", "200")
# - Hard cap on items sent to LLM (protects latency/cost)
LLM_RETRIEVAL_MAX_ITEMS = int(os.getenv("LLM_RETRIEVAL_MAX_ITEMS", "300"))
# - Batch size for classification requests
LLM_RETRIEVAL_BATCH_SIZE = int(os.getenv("LLM_RETRIEVAL_BATCH_SIZE", "50"))
