# Semantic retrieval & LLM prompts

These prompts are **repo-agnostic** and **scenario-agnostic**: the model infers scope from the diff and query text. No user must label “dead zone”, “blast radius”, etc.

## Design goals

1. **Precision over vague recall** — Vector search matches *descriptions*. Generic phrases (“auth validation”, “user input”) pull unrelated tests. Prompts force **verbatim file paths**, **symbol names**, and **concrete APIs** into the text that gets embedded.
2. **AST + semantic stay complementary** — Semantic should *rank* tests that plausibly exercise the **same files and symbols** the diff touches, not every test in a broad domain.
3. **LLM reasoning** — Scores must penalize “same neighborhood” / shared-constant / distant-module matches unless the diff clearly implicates them.
4. **Explicit FP/FN language** — **Summarizer + query rewriter** target retrieval: generic or anchor-dropped text → false positives / false negatives in vector search. **Reranker** (`llm_reasoning_service`) targets scoring: prefer missing a borderline test (FN) over endorsing a wrong one (FP); it ranks fixed candidates and does not repair bad upstream queries.

## Files

| File | Role |
|------|------|
| `diff_summarizer.py` | Turns raw diff into a search-oriented summary (fed to RAG + embeddings). |
| `query_rewriter.py` | Rewrites the enriched query into variations **without dropping anchors**. |
| `services/llm_reasoning_service.py` (under `backend/services/`) | Scores top merged candidates vs the diff (precision rubric). |

## Tuning

- `DIFF_SUMMARY_MAX_CHARS` / `DIFF_SUMMARY_MAX_TOKENS` — cap very large diffs.
- Lower chat `temperature` in code = more stable, more literal summaries.
