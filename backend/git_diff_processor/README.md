# Git Diff Processor

## Overview

The Git Diff Processor turns a git diff into a list of tests that should be run based on code changes. It uses **AST-based matching** (database reverse index, function mappings), **semantic search** (vector embeddings via **unified RAG** in `rag_pipeline.py`), and optional **LLM reasoning** to select tests.

**Two ways to use it:**

| Entry point | Use case |
|-------------|----------|
| **CLI** – `git_diff_processor.py` | Run from the command line with a diff file; prints results to the console. |
| **API** – `process_diff_programmatic.py` | Used by the app: `process_diff_and_select_tests()` is called by the selection service when the user runs "Select tests" in the UI. |

**What it does:**

1. Parses the diff (changed files, classes, methods)
2. Builds search queries (exact, module, function-level)
3. **AST:** Queries the database (reverse index, test registry) to find tests that reference changed symbols
4. **Semantic:** Optionally runs **unified RAG** ([`semantic/retrieval/rag_pipeline.py`](../semantic/retrieval/rag_pipeline.py)): validated diff summary or diff-anchor text → **single** symbol enrich → mandatory query rewrite → Pinecone vector search (all rewriter outputs; **no** post-rewrite cosine gate)
5. Merges AST + semantic results, optionally runs LLM reasoning to score relevance
6. Returns (or displays) the selected tests with confidence scores

---

## Module structure

| File | Purpose |
|------|---------|
| **`git_diff_processor.py`** | CLI script, display helpers, and `main()`. Imports AST/semantic **selection** from `selection_engine.py` and diff I/O from `deterministic.parsing.diff_parser`. |
| **`selection_engine.py`** | AST path: DB queries (`find_affected_tests`, `find_tests_ast_only`, …). Uses `diff_parser` helpers only (no duplicate parse implementation). |
| **`process_diff_programmatic.py`** | **Programmatic API**: `process_diff_and_select_tests()` (async). Calls `parse_git_diff` / `build_search_queries` from **`deterministic/parsing/diff_parser.py`** then `selection_engine` + semantic merge. Used by `services/selection_service.py`. |
| **`deterministic/parsing/diff_parser.py`** | **Only** implementation of diff parsing and `build_search_queries`. Imported by this package and by `semantic/retrieval/rag_pipeline.py` (symbol extraction). |
| **`utils/deduplicate_tests.py`** | Deduplication helpers for test lists. |
| **`utils/indexing_utils.py`** | Index verification and reindexing utilities. |
| **`diff_scenario_analysis.py`** | **Impact intelligence**: scenario tags (mixed diff, micro-guard, blast radius), **dead zones** (symbols with zero mapped tests), **test linkage** (cross-dependent vs standalone from `test_dependencies`), **FP/FN risk** labels per test. |
| **`cochange_tight_suite.py`** | **Tight co-change**: if the diff changes **both** production code and a test file, selection is restricted to **all tests in that test file** (sibling describes), dropping cross-file semantic hits. Set `DISABLE_TIGHT_COCHANGE_SUITE=1` to disable. |

### Tuning semantic vector threshold (FP vs FN)

| Env var | Effect |
|---------|--------|
| `SEMANTIC_VECTOR_THRESHOLD=0.22` | Force minimum cosine similarity (lower → **more** vector hits: FN↓, FP↑). Restart the API after setting. |
| `SEMANTIC_VECTOR_THRESHOLD_PRESET=lenient` | Sets threshold **0.22** (same idea). Also: `moderate` (0.32), `strict` (0.50). |
| `RAG_LENIENT_FALLBACK=1` | If the rewriter returns fewer than two queries, fall back to a **single** vector search using the enriched original query (no second symbol enrich). |

The API returns `selectionFunnel.vector_similarity_threshold_used` and `tuning_false_positive_vs_false_negative` so you can compare runs. Watch `vector_search_candidates` — it should **go up** when you lower the threshold. **`ragDiagnostics`** on the selection response describes unified RAG stages (and any lenient recovery).

### API payload: `impact_intelligence`

Returned by `process_diff_and_select_tests()` alongside `tests`:

| Field | Meaning |
|-------|---------|
| `scenario_tags` | e.g. `MIXED_LANGUAGE_DIFF`, `MICRO_GUARD_HOTFIX`, `MAXIMUM_BLAST_RADIUS`, `TIGHT_FEATURE_ISOLATION` |
| `action_type_cascade` | Order of strategies (function → file → exact → module → semantic → LLM) |
| `dead_zones` | Symbols in the diff with **no** `reverse_index` test references (coverage gap) |
| `false_negative_hints` | When to widen the test set (large diff, dead zones, mixed lang) |
| `precision_notes` | Human guidance on false-positive risk for this diff shape |

Each test may include: `test_linkage_profile` (`FULLY_CROSS_DEPENDENT` / `FULLY_STANDALONE` / `MODERATE_LINKAGE`), `evidence_quality` (`CONFIRMED_FUNCTION` … `SEMANTIC_SUPPLEMENT`), `false_positive_risk` (`LOW` … `HIGH`), plus existing `semantic_only_no_overlap`.

---

## Quick start (CLI)

### 1. Generate a git diff

```bash
# Diff between two commits
git diff commit1 commit2 > git_diff_processor/sample_diffs/diff_commit1.txt

# Single commit
git show commit_hash > git_diff_processor/sample_diffs/diff_commit1.txt

# Uncommitted changes
git diff > git_diff_processor/sample_diffs/diff_uncommitted.txt
```

### 2. Run the processor (from backend directory)

```bash
# With file path
python git_diff_processor/git_diff_processor.py sample_diffs/diff_commit1.txt

# Or use default (sample_diffs/diff_commit1.txt)
python git_diff_processor/git_diff_processor.py
```

---

## Application (API) usage

The **Test Impact Analysis** app does not run the CLI. It uses the programmatic API:

1. User selects a branch and clicks **Select tests**.
2. The API fetches the diff from GitLab/GitHub.
3. **`SelectionService.run_selection_with_diff(diff_data, repository_id)`** is called.
4. That calls **`process_diff_and_select_tests()`** from `git_diff_processor.process_diff_programmatic` with:
   - `diff_content`, `file_list` (changed files), `schema_name`, `test_repo_path`, `semantic_config`
5. Result (selected tests, confidence, AST/semantic counts, etc.) is returned to the frontend.

So for the UI flow, only **`process_diff_programmatic.process_diff_and_select_tests`** is used; **`git_diff_processor.py`** is for CLI entry and printing; **selection logic** lives in **`selection_engine.py`**; **diff structure** is always built in **`deterministic/parsing/diff_parser.py`** (no duplicate parser under `git_diff_processor/`).

---

## How it works (pipeline)

1. **Parse diff** – Extract changed files, classes, methods (and support headerless diff when only a file list is provided).
2. **Build search strategy** – Exact matches, module patterns, function-level lookups from `diff_parser` and DB.
3. **AST selection** – `find_tests_ast_only()` queries the test repository schema(s): reverse index, function mappings, direct file matches, module patterns. Produces a list of tests with match types.
4. **Semantic selection** (if enabled) – **Unified RAG** (`rag_pipeline.run_semantic_rag`): summarize diff (LLM) → validate vs diff embedding; if rejected use **diff-anchor** text → **one** `enrich_semantic_query_with_diff_symbols` call → mandatory rewrite (LLM) → validate each variation vs diff embedding → embed surviving queries → Pinecone. Results merged with AST. Response may include `rag_diagnostics`.
5. **Merge** – Combine AST and semantic results, deduplicate by test ID, preserve match type (AST / semantic / both).
6. **LLM reasoning** (optional) – Score each candidate test for relevance to the diff; used to adjust confidence.
7. **Confidence** – Each test gets a confidence score and breakdown (AST, vector, LLM components). Results are filtered by threshold and returned.

---

## Example CLI output

```
==================================================
Git Diff to Test Selection
==================================================

  Step 1: Reading git diff file...
  Step 2: Parsing git diff...
  Parsed Changes:
    Changed files: 1
    Changed classes: 0
    Changed methods: 2

  Step 3: Building search strategy...
  Step 4: Querying database for affected tests...
  Step 5: Results
  Test Selection Results:
    Found N affected test(s):
    High / Medium / Low confidence...
==================================================
Processing Complete!
==================================================
```

---

## File format

Standard git unified diff format is supported. The programmatic API can also work with **headerless diffs** when the API provides only a list of changed file paths (`file_list`).

---

## Database and schema

- **AST** uses the **deterministic** DB: connection via `deterministic/db_connection.py`. Each test repository has its own schema (e.g. `test_repo_261b672a`); tables include `test_registry`, reverse index, function_mappings, etc.
- **Semantic** uses **Pinecone** (vectors) and does not query the deterministic DB for search; `test_repo_id` is used to scope vectors to the right namespace.

**Requirements:**

- Deterministic DB set up and `.env` configured for DB and (if used) Pinecone/OpenAI.
- Test repository analyzed and loaded (so test_registry and embeddings exist for that repo).

---

## Files in this package

| Path | Description |
|------|-------------|
| `git_diff_processor.py` | CLI script and core selection logic (AST, semantic callbacks, confidence). |
| `process_diff_programmatic.py` | Programmatic API: `process_diff_and_select_tests`, `build_adaptive_semantic_config`. |
| `utils/deduplicate_tests.py` | Test deduplication utilities. |
| `utils/indexing_utils.py` | Index verification and reindexing. |
| `README.md` | This file. |

---

## Dependencies

- **deterministic** – `db_connection`, `get_connection_with_schema`, schema-specific tables (test_registry, reverse index, etc.)
- **semantic** – `find_tests_semantic` / `rag_pipeline.run_semantic_rag`, config; uses vector backend and optional LLM/embedding providers
- **services** – `selection_service` calls `process_diff_and_select_tests`; `audit_service` logs selection runs when `repository_id` is set

---

## Troubleshooting

- **Diff file not found (CLI)** – Use correct path; from backend directory use paths relative to backend or absolute.
- **Cannot connect to database** – Check `.env`, run DB connection test, ensure the correct schema exists for the test repo.
- **No tests found** – Verify changed files are production code (not only tests), schema has data for that repo, and (for semantic) embeddings have been generated for the test repository.
- **Semantic returns few/no results** – Ensure embeddings exist for the bound test repo and `TEST_REPO_ID` is set when running selection (so Pinecone filters by namespace).

---

## Integration with CI/CD

CLI can be used in scripts:

```bash
git diff $BASE_COMMIT $HEAD_COMMIT > diff.txt
python git_diff_processor/git_diff_processor.py diff.txt
# Or capture output to file for downstream steps
```

For the web app, the API path is used: diff is fetched by the backend from GitLab/GitHub, then `process_diff_and_select_tests()` is invoked with that diff and the bound test repo configuration.
