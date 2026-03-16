# LLM Call Analysis - Complete System Overview

## Summary

This document provides a complete breakdown of all LLM calls in the system, including:
- Number of calls per component
- Max tokens for each call
- Total token usage across the system

---

## LLM Chat Completion Calls

### 1. Query Understanding (Advanced RAG)
**Location**: `semantic_retrieval/advanced_rag/query_understanding.py`

- **Calls**: 1 time (if Advanced RAG enabled AND Query Rewriting enabled)
- **Max Tokens**: 4,000
- **Purpose**: Analyze code change intent and extract related concepts
- **When**: Step 1 of Advanced RAG pipeline

**Calculation**:
- Best case: 0 calls (Query Rewriting disabled)
- Average case: 1 call
- Worst case: 1 call

---

### 2. Query Rewriting (Advanced RAG)
**Location**: `semantic_retrieval/advanced_rag/query_rewriter.py`

- **Calls**: 1 time (if Advanced RAG enabled AND Query Rewriting enabled)
- **Max Tokens**: 1,500
- **Purpose**: Generate multiple query variations from different perspectives
- **When**: Step 2 of Advanced RAG pipeline

**Calculation**:
- Best case: 0 calls (Query Rewriting disabled)
- Average case: 1 call
- Worst case: 1 call

---

### 3. LLM Re-ranking (Advanced RAG)
**Location**: `semantic_retrieval/advanced_rag/reranker.py`

- **Calls**: Variable (batches of 50 candidates)
- **Max Tokens**: Dynamic calculation
  - Formula: `min(max(len(batch) * 120 + 2000, 4000), 32000)`
  - Minimum: 4,000 tokens
  - Maximum: 32,000 tokens (model limit)
- **Purpose**: Re-rank semantic search candidates by relevance
- **When**: Step 4 of Advanced RAG pipeline (if Re-ranking enabled)

**Dynamic Calculation**:
- Batch size: 50 candidates per batch
- Formula: `min(max(len(batch) * 120 + 2000, 4000), 32000)`
- Per batch (50 candidates): `min(max(50 * 120 + 2000, 4000), 32000) = min(8000, 32000) = 8,000 tokens`
- For 200 candidates: 4 batches × 8,000 = 32,000 tokens total
- For 100 candidates: 2 batches × 8,000 = 16,000 tokens total

**Calculation**:
- Best case: 0 calls (Re-ranking disabled)
- Average case: 1-2 batches (50-100 candidates) = 1-2 calls × 8,000 = 8,000-16,000 tokens
- Worst case: 4 batches (200 candidates) = 4 calls × 8,000 = 32,000 tokens

---

### 4. LLM Reasoning (Test Relevance Assessment)
**Location**: `web_platform/services/llm_reasoning_service.py`

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
**Location**: `semantic_retrieval/embedding_generator.py`

- **Calls**: N times (one per test file in repository)
- **Max Tokens**: N/A (embeddings don't use max_tokens)
- **Purpose**: Generate embeddings for all tests in repository
- **When**: During test repository analysis (one-time per repository)

**Calculation**:
- Best case: 0 calls (if embeddings already generated)
- Average case: 100-500 calls (one per test file)
- Worst case: 1,000+ calls (large repository)

---

### 6. Query Embedding (Basic Semantic Search)
**Location**: `semantic_retrieval/semantic_search.py`

- **Calls**: 1 time (if using basic semantic search)
- **Max Tokens**: N/A (embeddings don't use max_tokens)
- **Purpose**: Generate embedding for the change description
- **When**: Basic semantic search (non-Advanced RAG)

**Calculation**:
- Best case: 0 calls (if using Advanced RAG)
- Average case: 1 call
- Worst case: 1 call

---

### 7. Multi-Query Embeddings (Advanced RAG)
**Location**: `semantic_retrieval/advanced_rag/advanced_semantic_search.py`

- **Calls**: N times (one per query variation)
- **Max Tokens**: N/A (embeddings don't use max_tokens)
- **Purpose**: Generate embeddings for each query variation
- **When**: Step 3 of Advanced RAG pipeline

**Calculation**:
- Best case: 1 call (Query Rewriting disabled, only original query)
- Average case: 3-5 calls (1 original + 2-4 variations)
- Worst case: 6 calls (1 original + 5 variations)

---

### 8. Multi-Query Embeddings (Basic Multi-Query Search)
**Location**: `semantic_retrieval/semantic_search.py` - `find_tests_semantic_multi_query`

- **Calls**: 3 times (function query, module query, rich query)
- **Max Tokens**: N/A (embeddings don't use max_tokens)
- **Purpose**: Generate embeddings for different query perspectives
- **When**: Multi-query semantic search (non-Advanced RAG)

**Calculation**:
- Best case: 0 calls (if using Advanced RAG or single query)
- Average case: 3 calls
- Worst case: 3 calls

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
- Query Understanding: 1 call × 4,000 = **4,000 tokens**
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
- Query Understanding: 0 calls (skipped)
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
- Query Understanding: 1 call × 4,000 = **4,000 tokens**
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
| **Query Understanding** | 0-1 | 4,000 | 0-4,000 |
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
  - Query Understanding: 1 × 4,000 = 4,000
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
  - Query Understanding: 1 × 4,000 = 4,000
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
2. **Query Understanding and Rewriting are fixed**: 4,000 + 1,500 = 5,500 tokens total
3. **LLM Reasoning is consistent**: Always 8,000 tokens (if enabled)
4. **Embeddings are lightweight**: No token limits, but many API calls
5. **Total system max tokens**: 0-45,500 tokens per test selection run

---

## Recommendations

1. **Monitor token usage**: Track actual usage vs. max_tokens to optimize
2. **Batch size tuning**: Adjust reranker batch size (currently 50) based on performance
3. **Conditional calls**: Skip Query Understanding if Query Rewriting is disabled (already implemented)
4. **Caching**: Consider caching query understanding/rewriting results for similar diffs
