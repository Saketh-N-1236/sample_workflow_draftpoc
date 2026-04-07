# Semantic — vector search and RAG

This package (import name: `semantic`) holds everything for **semantic test retrieval**:

| Subfolder | Role |
|-----------|------|
| `retrieval/` | RAG pipeline, Pinecone queries, multi-query search, validation |
| `embedding_generation/` | Build embeddings from test chunks, batch upsert |
| `chunking/` | Test-boundary chunking, content summarizer |
| `ingestion/` | Load test files / analysis output for embedding |
| `prompts/` | Diff summarizer, query rewriter |
| `backends/` | Vector store abstraction (Pinecone) |
| `config.py` | Thresholds, batch size, Pinecone settings |

**Run from `backend/` with `PYTHONPATH=.`:**

```bash
python -m semantic.embedding_generation.embedding_generator
python -m semantic.clear_embeddings
```

**Imports:** `from semantic.retrieval.semantic_search import find_tests_semantic`

Git diff **parsing** lives under `deterministic/parsing/` — not here.
