# LLM Call Analysis - Complete System Overview

## Summary

This document provides a complete breakdown of all LLM calls in the system, including:
- Number of calls per component
- Max tokens for each call
- Total token usage across the system

---

## LLM Chat Completion Calls

### 1. Git diff summary (Advanced RAG, optional)
**Location**: `semantic/prompts/diff_summarizer.py` (used from `semantic/retrieval/rag_pipeline.py`)

- **Calls**: 0–1 time (LLM summarizes the diff; kept only if cosine similarity vs raw diff ≥ validation threshold)
- **Max Tokens**: (model-dependent; summarization call)
- **Purpose**: Richer “original query” for semantic search than static change description alone
- **When**: Before query rewriting, when `diff_content` is present

**Calculation**:
- Best case: 0 calls (no diff text or summarization skipped / fails)
- Average case: 0–1 call

---

### 2. Query Rewriting (unified RAG)
**Location**: `semantic/prompts/query_rewriter.py` (called from `semantic/retrieval/rag_pipeline.py`)

- **Calls**: 1 time per selection (mandatory in unified RAG; no disable flag)
- **Max Tokens**: 1,500
- **Purpose**: Generate multiple query variations from different perspectives
- **When**: Step 2 of Advanced RAG pipeline

**Calculation**:
- Best case: 0 calls (Query Rewriting disabled)
- Average case: 1 call
- Worst case: 1 call

---

### 3. LLM Reasoning (Test Relevance Assessment)
**Location**: `services/llm_reasoning_service.py`

- **Calls**: 1 time (always, if LLM reasoning enabled)
- **Max Tokens**: 8,000
- **Purpose**: Assess relevance of top 20 test candidates
- **When**: After merging AST + Semantic results

**Calculation**:
- Best case: 0 calls (LLM reasoning disabled)
- Average case: 1 call
- Worst case: 1 call

---

## Embedding Generation Calls

### 5. Embedding Generation (Test Analysis Phase)
**Location**: `semantic/embedding_generation/embedding_generator.py`

- **Calls**: N times (one per test file in repository)
- **Max Tokens**: N/A (embeddings don't use max_tokens)
- **Purpose**: Generate embeddings for all tests in repository
- **When**: During test repository analysis (one-time per repository)

**Calculation**:
- Best case: 0 calls (if embeddings already generated)
- Average case: 100-500 calls (one per test file)
- Worst case: 1,000+ calls (large repository)

---

### 6. Validation embeddings (unified RAG — summary only)
**Location**: `semantic/retrieval/validation.py` (used from `rag_pipeline.py`)

- **Calls**: Embed `diff_content` plus one embedding for the LLM summary text (when summarizing the diff)
- **Purpose**: Cosine gate: accept or reject the diff summary vs raw diff (`GIT_DIFF_SUMMARY_VALIDATION_THRESHOLD`)
- **When**: Only when `diff_content` is present and a non-empty summary is returned — **not** applied to rewritten queries

---

### 7. Multi-Query Embeddings (unified RAG retrieval)
**Location**: `semantic/retrieval/rag_pipeline.py` (`_vector_search_queries`)

- **Calls**: One embedding per rewriter output (typically 2–4; all non-empty strings)
- **Max Tokens**: N/A (embeddings don't use max_tokens)
- **Purpose**: Pinecone search per variation; results merged
- **When**: After mandatory query rewriting (no post-rewrite cosine filter)

**Calculation**:
- Typical: 2–4 calls (one per query variation from `QueryRewriterService`)
- Lenient fallback: 1 call (`RAG_LENIENT_FALLBACK=1`) if the rewriter returns fewer than 2 queries

---

### 8. Legacy `find_tests_semantic_with_multi_queries` (unused by default path)
**Location**: `semantic/retrieval/multi_query_search.py`

- **Status**: Not used by `find_tests_semantic` after unified RAG; kept for optional tooling.
- **Calls**: N/A for normal API selection flow (use section 7 instead).

---

## Complete System Token Usage

### Scenario 1: Basic Semantic Search (No Advanced RAG)

**LLM Chat Completions**:
- LLM Reasoning: 1 call × 8,000 = **8,000 tokens**

**Embedding Calls**:
- Query Embedding: 1 call
- **Total**: 1 embedding call

**Total LLM Chat Calls**: 1
**Total Max Tokens**: 8,000

---

### Scenario 2: Advanced RAG (All Features Enabled)

**LLM Chat Completions**:
- Diff summary (optional LLM): 1 call × 4,000 = **4,000 tokens**
- Query Rewriting: 1 call × 1,500 = **1,500 tokens**
- LLM Re-ranking: 2-4 calls × 8,000 = **16,000-32,000 tokens** (average: 2 batches)
- LLM Reasoning: 1 call × 8,000 = **8,000 tokens**

**Embedding Calls**:
- Multi-Query Embeddings: 3-5 calls (query variations)

**Total LLM Chat Calls**: 5-7 calls
**Total Max Tokens**: 29,500-45,500 tokens (average: ~33,500 tokens)

---

### Scenario 3: Advanced RAG (Query Rewriting Disabled)

**LLM Chat Completions**:
- Diff summary (optional LLM): 0 calls (skipped)
- Query Rewriting: 0 calls (disabled)
- LLM Re-ranking: 2-4 calls × 8,000 = **16,000-32,000 tokens**
- LLM Reasoning: 1 call × 8,000 = **8,000 tokens**

**Embedding Calls**:
- Multi-Query Embeddings: 1 call (only original query)

**Total LLM Chat Calls**: 3-5 calls
**Total Max Tokens**: 24,000-40,000 tokens (average: ~28,000 tokens)

---

### Scenario 4: Advanced RAG (Re-ranking Disabled)

**LLM Chat Completions**:
- Diff summary (optional LLM): 1 call × 4,000 = **4,000 tokens**
- Query Rewriting: 1 call × 1,500 = **1,500 tokens**
- LLM Re-ranking: 0 calls (disabled)
- LLM Reasoning: 1 call × 8,000 = **8,000 tokens**

**Embedding Calls**:
- Multi-Query Embeddings: 3-5 calls

**Total LLM Chat Calls**: 3 calls
**Total Max Tokens**: 13,500 tokens

---

## Token Usage Summary Table

| Component | Calls | Max Tokens/Call | Total Max Tokens |
|-----------|-------|-----------------|------------------|
| **Diff summary (LLM)** | 0-1 | (varies) | (varies) |
| **Query Rewriting** | 0-1 | 1,500 | 0-1,500 |
| **LLM Re-ranking** | 0-4 | 8,000 | 0-32,000 |
| **LLM Reasoning** | 0-1 | 8,000 | 0-8,000 |
| **TOTAL (Chat)** | 0-7 | - | **0-45,500** |

---

## Best, Average, and Worst Case Scenarios

### Best Case (Minimal LLM Usage)
- Advanced RAG: Disabled
- LLM Reasoning: Disabled
- **Total Calls**: 0 chat completions
- **Total Max Tokens**: 0
- **Embedding Calls**: 1 (basic query embedding)

---

### Average Case (Typical Usage)
- Advanced RAG: Enabled (all features)
- LLM Reasoning: Enabled
- Re-ranking: 2 batches (100 candidates)
- Query Variations: 3-4 queries
- **Total Calls**: 5 chat completions
  - Diff summary (optional LLM): 1 × 4,000 = 4,000
  - Query Rewriting: 1 × 1,500 = 1,500
  - LLM Re-ranking: 2 × 8,000 = 16,000
  - LLM Reasoning: 1 × 8,000 = 8,000
- **Total Max Tokens**: **29,500 tokens**
- **Embedding Calls**: 3-4 (query variations)

---

### Worst Case (Maximum LLM Usage)
- Advanced RAG: Enabled (all features)
- LLM Reasoning: Enabled
- Re-ranking: 4 batches (200 candidates)
- Query Variations: 5 queries
- **Total Calls**: 7 chat completions
  - Diff summary (optional LLM): 1 × 4,000 = 4,000
  - Query Rewriting: 1 × 1,500 = 1,500
  - LLM Re-ranking: 4 × 8,000 = 32,000
  - LLM Reasoning: 1 × 8,000 = 8,000
- **Total Max Tokens**: **45,500 tokens**
- **Embedding Calls**: 5 (query variations)

---

## Embedding Calls Summary

Embeddings don't use `max_tokens` (they're not chat completions), but here's the call count:

| Phase | Calls | Notes |
|-------|-------|-------|
| **Test Analysis** | N (one per test) | One-time per repository |
| **Query Embedding (Basic)** | 1 | Per test selection |
| **Multi-Query Embeddings** | 1-5 | Per test selection (Advanced RAG) |
| **Multi-Query Embeddings (Basic)** | 3 | Per test selection (if multi-query enabled) |

---

## Key Insights

1. **LLM Re-ranking is the largest token consumer**: Up to 32,000 tokens (4 batches × 8,000)
2. **Diff summary (optional LLM) and Rewriting are fixed**: 4,000 + 1,500 = 5,500 tokens total
3. **LLM Reasoning is consistent**: Always 8,000 tokens (if enabled)
4. **Embeddings are lightweight**: No token limits, but many API calls
5. **Total system max tokens**: 0-45,500 tokens per test selection run

---

## Recommendations

1. **Monitor token usage**: Track actual usage vs. max_tokens to optimize
2. **Query variations**: Tune num_query_variations based on diff complexity
3. **Conditional calls**: Disable query rewriting via `semantic_config` / env when you want fewer LLM calls
4. **Caching**: Consider caching diff summaries / rewritten queries for similar diffs
