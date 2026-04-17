# Test Impact Analysis — Complete Architecture & Flow Reference

> Auto-generated from full source traversal — covers every file, trigger point,
> language plugin, user flow, sequence diagram, and system architecture.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Supported Languages](#2-supported-languages)
3. [Repository & Folder Map](#3-repository--folder-map)
4. [Component Architecture Diagram](#4-component-architecture-diagram)
5. [User Flow (End-to-End)](#5-user-flow-end-to-end)
6. [Sequence Diagrams](#6-sequence-diagrams)
   - 6.1 [Connect Repository](#61-connect-repository)
   - 6.2 [Select Tests (Main Path)](#62-select-tests-main-path)
   - 6.3 [Upload & Analyse Test Repository](#63-upload--analyse-test-repository)
   - 6.4 [Generate Embeddings](#64-generate-embeddings)
7. [Backend Pipeline — File-by-File Trigger Chain](#7-backend-pipeline--file-by-file-trigger-chain)
   - 7.1 [API Entry Point](#71-api-entry-point)
   - 7.2 [Route Layer](#72-route-layer)
   - 7.3 [Service Layer](#73-service-layer)
   - 7.4 [Diff Processing & Test Selection](#74-diff-processing--test-selection)
   - 7.5 [Deterministic / AST Layer](#75-deterministic--ast-layer)
   - 7.6 [Semantic / RAG Layer](#76-semantic--rag-layer)
   - 7.7 [LLM Clients](#77-llm-clients)
   - 7.8 [Test Analysis Engine](#78-test-analysis-engine)
   - 7.9 [VCS Services (GitHub / GitLab)](#79-vcs-services-github--gitlab)
   - 7.10 [Configuration Layer](#710-configuration-layer)
8. [Frontend — File-by-File Trigger Chain](#8-frontend--file-by-file-trigger-chain)
9. [Database Schema](#9-database-schema)
10. [Vector Store (Pinecone)](#10-vector-store-pinecone)
11. [Scoring & Selection Logic](#11-scoring--selection-logic)
12. [Risk Analysis Flow](#12-risk-analysis-flow)
13. [Environment Variables Reference](#13-environment-variables-reference)
14. [Startup & Initialization Sequence](#14-startup--initialization-sequence)

---

## 1. System Overview

Test Impact Analysis automatically selects the **minimum set of tests** that need
to run for a given code change (git diff). It combines three complementary
strategies:

| Strategy | Engine | Description |
|---|---|---|
| **Structural (AST)** | Deterministic | SQL queries against a pre-built test registry using exact class/function names from the diff |
| **Semantic (Vector)** | Pinecone + Embeddings | Cosine-similarity search over test embeddings, using LLM-summarized diff queries |
| **LLM Reasoning** | Gemini / OpenAI / Anthropic / Ollama | Second-pass classification to promote or demote borderline candidates |

Results are **merged** (not added) into a single ranked list, scored, and
returned to the UI.

---

## 2. Supported Languages

Languages are configured in `backend/config/language_configs.yaml` and
detected automatically by the `RepoAnalyzer` engine.

| Language | File Extensions | Test Frameworks | Test Naming Pattern | Parser |
|---|---|---|---|---|
| **Python** | `.py` | pytest, unittest, nose | `test_*.py`, `*_test.py` | Tree-sitter |
| **Java** | `.java` | JUnit, TestNG, Spock | `*Test.java`, `Test*.java` | Tree-sitter |
| **JavaScript** | `.js`, `.jsx` | Jest, Mocha | `*.test.js`, `*.spec.js` | Tree-sitter |
| **TypeScript** | `.ts`, `.tsx` | Jest, Mocha, Vitest | `*.test.ts`, `*.spec.ts` | Tree-sitter |
| **C** | `.c`, `.h` | Google Test | `test_*.c`, `*_test.c` | Tree-sitter |
| **C++** | `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh` | Google Test | `*_test.cpp`, `test_*.cpp` | Tree-sitter |

Language plugins live under `backend/test_analysis/plugins/<language>/plugin.py`.
A fallback regex parser (`core/parsers/plugins/regex_fallback.py`) is used when
Tree-sitter grammars are unavailable.

---

## 3. Repository & Folder Map

```
sample_workflow/
├── .env                          ← Root env file (all secrets & config)
├── README.md
│
├── backend/
│   ├── api/
│   │   ├── main.py               ← FastAPI app, CORS, router registration, startup hooks
│   │   ├── models/
│   │   │   ├── repository.py     ← Pydantic request/response models (SelectionResponse etc.)
│   │   │   └── test_repository.py
│   │   └── routes/
│   │       ├── analysis.py       ← /api/analysis/* endpoints
│   │       ├── repositories.py   ← /api/repositories/* CRUD + diff + branches
│   │       ├── selection.py      ← /api/repositories/{id}/select-tests
│   │       └── test_repositories.py ← /test-repositories/* upload/bind/analyze
│   │
│   ├── config/
│   │   ├── config_loader.py      ← Loads language_configs.yaml
│   │   ├── language_configs.yaml ← Per-language parser rules (extensions, patterns, frameworks)
│   │   └── settings.py           ← Pydantic Settings (LLM_PROVIDER, EMBEDDING_PROVIDER, keys…)
│   │
│   ├── deterministic/
│   │   ├── parsing/
│   │   │   └── diff_parser.py    ← parse_git_diff(), build_search_queries(), symbol extraction
│   │   ├── utils/
│   │   │   └── db_helpers.py     ← get_tests_for_production_class()
│   │   ├── db_connection.py      ← PostgreSQL connection pool (get_connection, DB_SCHEMA)
│   │   ├── loader.py             ← Loads AnalysisResult into DB (test_registry, function_mapping…)
│   │   ├── 01_create_tables.py   ← DB migration: creates test_registry, static_deps tables
│   │   ├── 02_create_test_repo_tables.py ← Test-repo-specific schema tables
│   │   └── 07_verify_data.py     ← Data integrity checks
│   │
│   ├── git_diff_processor/
│   │   ├── process_diff_programmatic.py  ← CORE: process_diff_and_select_tests() — full pipeline
│   │   ├── selection_engine.py           ← find_affected_tests(), find_tests_ast_only(), find_tests_semantic_only()
│   │   ├── git_diff_processor.py         ← CLI entry point (wraps programmatic)
│   │   ├── cli_output.py                 ← Pretty-print helpers
│   │   ├── cochange_tight_suite.py       ← Co-change / co-location analysis
│   │   └── utils/
│   │       ├── deduplicate_tests.py
│   │       └── indexing_utils.py
│   │
│   ├── llm/
│   │   ├── factory.py            ← LLMFactory.create_provider() + create_embedding_provider()
│   │   ├── base.py               ← Abstract LLMProvider interface
│   │   ├── gemini_client.py      ← Google Gemini (chat + embeddings)
│   │   ├── openai_client.py      ← OpenAI (chat + embeddings)
│   │   ├── ollama_client.py      ← Ollama local (chat + embeddings, nomic-embed-text default)
│   │   └── models.py             ← LLMRequest, LLMResponse, EmbeddingRequest, EmbeddingResponse
│   │
│   ├── parsers/
│   │   └── registry.py           ← Maps language names → parser classes
│   │
│   ├── semantic/
│   │   ├── config.py             ← Thresholds, batch sizes, caps, RAG knobs (env-backed)
│   │   ├── backends/
│   │   │   ├── __init__.py       ← get_backend() singleton (thread-safe, process-wide cache)
│   │   │   ├── base.py           ← Abstract VectorBackend interface
│   │   │   └── pinecone_backend.py ← PineconeBackend: upsert, search, query_scores_for_test_ids
│   │   ├── chunking/
│   │   │   ├── test_chunker.py   ← chunk_file_by_tests(), chunk_test_intelligently()
│   │   │   └── content_summarizer.py
│   │   ├── embedding_generation/
│   │   │   ├── embedding_generator.py  ← Batch-embed test files → Pinecone upsert (run once)
│   │   │   └── text_builder.py         ← Builds embedding text from test metadata
│   │   ├── ingestion/
│   │   │   ├── data_transformer.py
│   │   │   └── test_data_loader.py     ← load_test_files_from_repo(), load_tests_from_analysis()
│   │   ├── prompts/
│   │   │   ├── diff_summarizer.py          ← summarize_git_diff() — LLM → canonical query text
│   │   │   ├── query_rewriter.py           ← QueryRewriterService — expands query to multi-angle variants
│   │   │   └── semantic_classify_prompt.py ← build_semantic_classification_prompt() — Critical/High/NonRelevant labels
│   │   └── retrieval/
│   │       ├── rag_pipeline.py         ← run_rag_pipeline(): summarise → rewrite → vector search
│   │       ├── ast_semantic_supplement.py ← supplement_semantic_hits_for_ast_tests()
│   │       ├── multi_query_search.py   ← Merge results from multiple query vectors
│   │       ├── query_builder.py        ← Build rich change-description, enrich with diff symbols
│   │       ├── semantic_search.py      ← find_tests_semantic() (single-query path)
│   │       └── validation.py          ← validate_llm_extraction() — cosine-check LLM summary
│   │
│   ├── services/
│   │   ├── analysis_service.py   ← run_pipeline(): RepoAnalyzer → loader → embedding_generator
│   │   ├── audit_service.py      ← log_selection_run() → audit_log table
│   │   ├── github_service.py     ← GitHub API: validate_access, get_latest_diff, list_branches
│   │   ├── gitlab_service.py     ← GitLab API: same interface
│   │   ├── http_client.py        ← Shared async HTTPX client (closed on shutdown)
│   │   ├── llm_reasoning_service.py  ← assess_test_relevance() via LLM classification
│   │   ├── prompts/   (empty — classify prompt moved to semantic/prompts/)
│   │   ├── repository_db.py      ← create/get/update repository rows (PostgreSQL)
│   │   ├── repository_vcs.py     ← resolve_provider(), effective_branch(), normalize_diff_payload()
│   │   ├── selection_service.py  ← SelectionService.run_selection_with_diff() — orchestrator
│   │   └── test_repo_service.py  ← Upload zip, run analysis, bind to code repo
│   │
│   └── test_analysis/
│       ├── engine/
│       │   ├── repo_analyzer.py  ← RepoAnalyzer: detect_languages() → plugins → Merger
│       │   └── models.py         ← AnalysisResult, LanguageResult, TestRecord dataclasses
│       ├── core/
│       │   ├── analyzers/        ← java_analyzer, python_analyzer, javascript_analyzer, treesitter_fallback
│       │   ├── detection/        ← framework_detector.py, language_detector.py
│       │   ├── merger/           ← result_merger.py — merges per-language LanguageResults
│       │   ├── parsers/          ← treesitter_core.py, registry.py, plugins/regex_fallback.py
│       │   └── schema/           ← schema_builder.py
│       ├── plugins/
│       │   ├── base_plugin.py    ← LanguagePlugin ABC + get_plugin_registry()
│       │   ├── java/plugin.py
│       │   ├── javascript/plugin.py
│       │   ├── python/plugin.py
│       │   └── native/plugin.py  ← C/C++
│       └── utils/
│           ├── ast_parser.py
│           ├── config.py         ← get_test_repo_path()
│           ├── dependency_plugins/  ← java_plugin, javascript_plugin, python_plugin
│           ├── file_scanner.py
│           ├── language_parser.py
│           ├── output_formatter.py
│           └── universal_parser.py
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── main.jsx              ← ReactDOM.render(<App/>)
        ├── App.jsx               ← Router → routes map
        ├── services/
        │   └── api.js            ← Axios wrapper for all backend endpoints
        ├── pages/
        │   ├── AddRepository.jsx         ← URL input → connectRepository()
        │   ├── RepositoryList.jsx        ← Lists saved repos
        │   ├── RepositoryDetail.jsx      ← MAIN PAGE: diff, branch picker, test selection
        │   ├── ManageTestRepositories.jsx← Upload & bind test repos
        │   └── TestRepositoryAnalysis.jsx← Analysis outputs for a test repo
        ├── components/
        │   ├── Header.jsx
        │   ├── Sidebar.jsx
        │   ├── BranchSelector.jsx        ← Dropdown + refresh inside card
        │   ├── DiffViewer.jsx
        │   ├── DiffStats.jsx
        │   ├── DiffModal.jsx
        │   ├── ActionButtons.jsx         ← "Run Selection" button
        │   ├── ResultsDisplay.jsx        ← Tabbed table: All / AST / Semantic / Both
        │   ├── TestSummaryModal.jsx      ← Score breakdown (Combined, LLM wt., Relevance)
        │   ├── AnalysisStats.jsx
        │   ├── EmbeddingStatus.jsx       ← Pinecone index health indicator
        │   ├── RiskAnalysisPanel.jsx
        │   ├── RepositoryConnector.jsx
        │   ├── TestRepositoryBinding.jsx
        │   ├── TestRepositoryCard.jsx
        │   ├── TestRepositoryList.jsx
        │   └── TestRepositoryUpload.jsx
        └── styles/
            └── App.css
```

---

## 4. Component Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                      │
│                                                                     │
│  App.jsx → BrowserRouter                                           │
│   ├── AddRepository.jsx  (POST /api/repositories/connect)          │
│   ├── RepositoryList.jsx (GET  /api/repositories)                  │
│   ├── RepositoryDetail.jsx  ◄──── MAIN PAGE                        │
│   │    ├── BranchSelector ──────────────────────────────────┐      │
│   │    ├── DiffViewer                                        │      │
│   │    ├── ActionButtons → selectTests()                     │      │
│   │    ├── ResultsDisplay                                    │      │
│   │    └── TestSummaryModal                                  │      │
│   ├── ManageTestRepositories                                 │      │
│   └── TestRepositoryAnalysis                                 │      │
│                                                              │      │
│  api.js (axios) → http://localhost:8000/api                  │      │
└─────────────────────────────────────────┬────────────────────┘      │
                                          │ HTTP / JSON               │
┌─────────────────────────────────────────▼────────────────────────────┐
│                    BACKEND (FastAPI + Uvicorn)                        │
│                                                                      │
│  main.py ── CORS ── Router registration                             │
│   │                                                                  │
│   ├── /api/repositories/*   repositories.py                         │
│   │    ├── GET  /             list_repositories()                   │
│   │    ├── POST /connect      connect_repository()                  │
│   │    ├── GET  /{id}/branches  list_branches()                     │
│   │    ├── GET  /{id}/diff    get_diff()                            │
│   │    └── POST /{id}/refresh refresh_repository()                  │
│   │                                                                  │
│   ├── /api/repositories/{id}/select-tests  selection.py             │
│   │    └── POST → SelectionService.run_selection_with_diff()        │
│   │                                                                  │
│   ├── /api/analysis/*   analysis.py                                 │
│   │    ├── GET  /results        get_analysis_results()              │
│   │    ├── POST /refresh        refresh_analysis()                  │
│   │    ├── GET  /embedding-status  get_embedding_status()           │
│   │    └── GET  /total-tests    get_total_tests_count()             │
│   │                                                                  │
│   └── /test-repositories/*   test_repositories.py                   │
│        ├── POST /upload                                              │
│        ├── POST /{id}/analyze                                        │
│        ├── POST /{id}/regenerate-embeddings                          │
│        └── POST /repositories/{repoId}/bind-test-repo               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │               SELECTION PIPELINE                            │    │
│  │                                                              │    │
│  │  selection_service.py                                        │    │
│  │       │                                                      │    │
│  │       ▼                                                      │    │
│  │  process_diff_and_select_tests()  [process_diff_programmatic]│    │
│  │       │                                                      │    │
│  │       ├── parse_git_diff()  [diff_parser]                   │    │
│  │       │                                                      │    │
│  │       ├── AST PATH ─────────────────────────────────────┐   │    │
│  │       │   find_tests_ast_only()  [selection_engine]      │   │    │
│  │       │   → SQL: test_registry + static_deps + fn_mapping│   │    │
│  │       │                                              ▼   │   │    │
│  │       ├── SEMANTIC PATH ─────────────────────────────┐  │   │    │
│  │       │   run_rag_pipeline()  [rag_pipeline]          │  │   │    │
│  │       │   → summarize_git_diff() [LLM]               │  │   │    │
│  │       │   → QueryRewriterService → multi_query_search │  │   │    │
│  │       │   → Pinecone cosine search                    │  │   │    │
│  │       │                                               │  │   │    │
│  │       ├── AST-SEM SUPPLEMENT ──────────────────────── │  │   │    │
│  │       │   supplement_semantic_hits_for_ast_tests()    │  │   │    │
│  │       │   → metadata-filtered Pinecone (no threshold) │  │   │    │
│  │       │                                               │  │   │    │
│  │       └── MERGE ◄──────────────────────────────────── ┘  │   │    │
│  │           + LLM reasoning (assess_test_relevance)         │   │    │
│  │           + Confidence scoring                            │   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │  PostgreSQL  │  │   Pinecone   │  │  LLM Provider            │   │
│  │  (test_reg.  │  │  (vector     │  │  Gemini / OpenAI /       │   │
│  │   fn_mapping │  │   index)     │  │  Anthropic / Ollama      │   │
│  │   audit_log) │  │              │  │                          │   │
│  └──────────────┘  └──────────────┘  └─────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────┐                        │
│  │   GitHub API / GitLab API               │                        │
│  │   github_service.py / gitlab_service.py │                        │
│  │   (diff, branches, access validation)   │                        │
│  └─────────────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. User Flow (End-to-End)

### Flow A — First-Time Setup

```
User opens app (localhost:3000)
  │
  ▼
[AddRepository page]
  User pastes GitHub/GitLab URL  →  POST /api/repositories/connect
    Backend: validate access token → fetch default branch → save to DB
  │
  ▼
[ManageTestRepositories page]
  User uploads test repo ZIP      →  POST /test-repositories/upload
    Backend: extract ZIP → run RepoAnalyzer pipeline
                         → load results into DB schema (test_registry etc.)
                         → generate embeddings → upsert into Pinecone
  User binds test repo to code repo  →  POST /test-repositories/repositories/{id}/bind-test-repo
```

### Flow B — Everyday Selection Run

```
[RepositoryDetail page]  ← user navigates here
  │
  ├── BranchSelector loads   →  GET /api/repositories/{id}/branches
  ├── Diff loads             →  GET /api/repositories/{id}/diff
  │
  ▼
User clicks "Run Test Selection"
  │
  POST /api/repositories/{id}/select-tests
  │
  ├── Risk threshold check: if #changed_files > threshold → return ALL tests
  │
  └── SelectionService.run_selection_with_diff()
        │
        ▼
      process_diff_and_select_tests()
        1. parse_git_diff()        → changed files, classes, methods, symbols
        2. build_search_queries()  → DB key lists
        3. find_tests_ast_only()   → SQL: exact class/function matches
        4. run_rag_pipeline()      → semantic vector search
        5. supplement_ast_tests()  → score AST tests against same embedding
        6. MERGE                   → single combined result set
        7. LLM reasoning           → assess_test_relevance()
        8. Confidence scoring      → blended score per test
        9. Audit log               → log_selection_run()
        │
        ▼
      SelectionResponse JSON  →  frontend
        │
        ▼
      ResultsDisplay renders tabs (All / AST / Semantic / Both)
      TestSummaryModal shows Score Breakdown (Combined, LLM wt., Relevance)
```

---

## 6. Sequence Diagrams

### 6.1 Connect Repository

```
Browser          Frontend          Backend API         GitHub/GitLab API   PostgreSQL
  │                │                   │                      │                │
  │─ enter URL ──► │                   │                      │                │
  │                │─ POST /connect ──►│                      │                │
  │                │                   │─ validate_access() ─►│                │
  │                │                   │◄── 200 OK ───────────│                │
  │                │                   │─ get_project_info() ►│                │
  │                │                   │◄── default_branch ───│                │
  │                │                   │─ create_repository() ──────────────── ►│
  │                │                   │◄──────────────────────────────────────│
  │                │◄── RepositoryResponse ──│               │                │
  │◄── redirect ───│                   │                      │                │
```

### 6.2 Select Tests (Main Path)

```
Browser    Frontend     SelectionRoute  SelectionService  DiffParser  SelectionEngine  RAGPipeline  Pinecone    LLMProvider  PostgreSQL
  │          │               │               │               │              │               │            │           │             │
  │─ click ─►│               │               │               │              │               │            │           │             │
  │          │─ POST ────────►│               │               │              │               │            │           │             │
  │          │               │─ GET diff ─────────────────────────────────────────────────────────────────────────────────────────►│
  │          │               │◄── diff_content ───────────────────────────────────────────────────────────────────────────────────│
  │          │               │─ risk_check ──│               │               │               │            │           │             │
  │          │               │               │─ process() ──►│               │               │            │           │             │
  │          │               │               │               │─ parse_diff ─►│               │            │           │             │
  │          │               │               │               │◄── queries ───│               │            │           │             │
  │          │               │               │               │               │─ AST SQL ──────────────────────────────────────────►│
  │          │               │               │               │               │◄── AST tests ──────────────────────────────────────│
  │          │               │               │               │               │               │─ summarize ►│           │           │
  │          │               │               │               │               │               │            │─ embed ───►│           │
  │          │               │               │               │               │               │◄── vector results ──────│           │
  │          │               │               │               │               │─ supplement ──►│            │           │           │
  │          │               │               │               │               │               │─ filter ──►│           │           │
  │          │               │               │               │               │◄── scores ─────────────────│           │           │
  │          │               │               │               │◄─ merged ─────│               │            │           │           │
  │          │               │               │               │               │               │            │─ LLM assess ──────────►│
  │          │               │               │               │               │               │            │◄── ranked ─────────────│
  │          │               │               │─ SelectionResponse ────────────────────────────────────────────────────────────────│
  │          │◄── JSON ───────│               │               │               │               │            │           │           │
  │◄── UI ───│               │               │               │               │               │            │           │           │
```

### 6.3 Upload & Analyse Test Repository

```
Browser    ManageTestRepo   TestRepoRoute   TestRepoService   RepoAnalyzer   Loader   EmbeddingGen   Pinecone
  │             │                │               │                │              │          │             │
  │─ upload ───►│                │               │                │              │          │             │
  │             │─ POST /upload ─►│               │                │              │          │             │
  │             │                │─ extract ZIP ─►│                │              │          │             │
  │             │                │               │─ run_pipeline ─►│              │          │             │
  │             │                │               │                │─ scan() ─────►│          │             │
  │             │                │               │                │◄── files ─────│          │             │
  │             │                │               │                │─ extract() ──►│          │             │
  │             │                │               │                │◄── LanguageResult        │             │
  │             │                │               │                │─ merge() ────►│          │             │
  │             │                │               │◄── AnalysisResult              │          │             │
  │             │                │               │─ load_to_db() ──────────────── ►│         │             │
  │             │                │               │─ generate_embeddings() ──────────────────►│             │
  │             │                │               │                │              │          │─ upsert ────►│
  │             │                │               │                │              │          │◄── OK ───────│
  │             │◄── 200 OK ─────│               │                │              │          │             │
```

### 6.4 Generate Embeddings

```
EmbeddingGenerator     TestDataLoader     TextBuilder     LLMProvider(embed)   Pinecone
      │                      │                │                  │                  │
      │─ load_test_files ───►│                │                  │                  │
      │◄── test_chunks ───────│                │                  │                  │
      │                                        │                  │                  │
      │ for each chunk:                        │                  │                  │
      │─ build_embedding_text ────────────────►│                  │                  │
      │◄── text string ────────────────────────│                  │                  │
      │─ EmbeddingRequest ─────────────────────────────────────►│                  │
      │◄── vector[768/1536] ───────────────────────────────────────────────────────│
      │─ upsert(id, vector, metadata) ──────────────────────────────────────────── ►│
      │◄── OK ───────────────────────────────────────────────────────────────────── │
```

---

## 7. Backend Pipeline — File-by-File Trigger Chain

### 7.1 API Entry Point

**`backend/api/main.py`**

- **Triggered by**: `uvicorn main:App --reload` (or `run_backend.bat`)
- Loads `.env` from project root (or backend root as fallback)
- Adds `backend/` to `sys.path`
- Registers four routers under `/api`
- On **startup**: creates `audit_log`, `repositories`, and test-repo DB tables
- On **shutdown**: closes shared async HTTP client

### 7.2 Route Layer

| File | Prefix | Triggers |
|---|---|---|
| `routes/repositories.py` | `/api/repositories` | List, connect, refresh, branches, diff, threshold update |
| `routes/analysis.py` | `/api/repositories/{id}` + `/api/analysis` | Analysis pipeline, embedding status, all-tests count |
| `routes/selection.py` | `/api/repositories/{id}/select-tests` | Full selection pipeline |
| `routes/test_repositories.py` | `/test-repositories` | Upload ZIP, analyse, bind/unbind, regenerate embeddings |

### 7.3 Service Layer

**`services/selection_service.py`** — `SelectionService.run_selection_with_diff()`

1. Extracts `diff_content` and `changed_files` from the diff payload.
2. Looks up bound test repositories via `repository_db.get_test_repository_bindings()`.
3. Calls `process_diff_and_select_tests()` with schema list and test repo IDs.
4. Runs audit logging via `audit_service.log_selection_run()`.

**`services/analysis_service.py`** — `run_pipeline()`

1. Instantiates `RepoAnalyzer` on the local test repo path.
2. Calls `RepoAnalyzer.analyze()` → `AnalysisResult`.
3. Calls `loader.load_to_db(analysis_result)`.
4. Calls `embedding_generator` (async).

**`services/llm_reasoning_service.py`** — `assess_test_relevance()`

- Takes merged candidates + diff content.
- Batches candidates (default 5 per prompt, up to top-20).
- Calls `LLMFactory.create_provider()` → LLM chat.
- Returns enriched candidates with `llm_score` and `llm_reasoning`.

**`services/github_service.py` / `services/gitlab_service.py`**

- `validate_access()` — token check.
- `get_latest_diff()` — fetches HEAD commit diff via REST API.
- `list_branches()` — paginated; supports `fetch_all` for full listing.

### 7.4 Diff Processing & Test Selection

**`git_diff_processor/process_diff_programmatic.py`** — `process_diff_and_select_tests()`

This is the **core orchestrator** for a selection run:

```
parse_git_diff()                → structured diff: files, classes, methods, symbols
build_search_queries()          → DB key lists for SQL lookups
find_tests_ast_only()           → per-schema SQL queries  [selection_engine]
run_rag_pipeline()              → semantic retrieval        [rag_pipeline]
supplement_semantic_hits_for_ast_tests()  → AST tests scored by same query vector
MERGE  ────────────────────────  single non-additive set (overlap + semantic-only)
assess_test_relevance()         → LLM second-pass classification
build_confidence_scores()       → blended scoring (AST weight + semantic weight + LLM)
log_selection_run()             → audit DB record
```

**`git_diff_processor/selection_engine.py`** — `find_tests_ast_only()`

SQL queries against:
- `test_registry` (class names, method names, file paths)
- `static_dependencies` (referenced classes)
- `test_function_mapping` (exact function-call level matching)
- Co-location tokens (camelCase + anchor variants)

**`deterministic/parsing/diff_parser.py`** — `parse_git_diff()`

- Parses unified diff format.
- Extracts changed file paths, class/function names, deleted/added/renamed symbols.
- `build_search_queries()` → DB key structures for AST matching.
- `extract_deleted_added_renamed_symbols()` → used by RAG pipeline for query enrichment.

### 7.5 Deterministic / AST Layer

**`deterministic/db_connection.py`**

- `get_connection()` — returns a PostgreSQL connection (env: `DATABASE_URL` or individual `DB_*` vars).
- `get_connection_with_schema(schema)` — sets search_path for multi-schema support.
- `DB_SCHEMA` — default schema name.

**`deterministic/loader.py`**

- `load_to_db(analysis_result)` — inserts into:
  - `test_registry` — one row per test (id, class, method, file, type)
  - `test_static_dependencies` — referenced class names per test
  - `test_function_mapping` — function-call level associations
  - `test_metadata` — descriptions, tags

### 7.6 Semantic / RAG Layer

**`semantic/retrieval/rag_pipeline.py`** — `run_rag_pipeline()`

```
1. _resolve_symbols()                 → extract deleted/added/renamed symbols from diff
2. build_rich_change_description()    → canonical change description text
3. enrich_semantic_query_with_diff_symbols()
4. summarize_git_diff()  [LLM]        → concise query text (validated vs diff embedding)
5. validate_llm_extraction()          → cosine check: summary vs diff embedding
6. QueryRewriterService.rewrite()     → multi-angle query variants
7. _vector_search_queries()           → embed each query → Pinecone cosine search
8. merge results by test_id           → highest score wins per test
9. return results + diagnostics (queries_used_strings)
```

**`semantic/retrieval/ast_semantic_supplement.py`** — `supplement_semantic_hits_for_ast_tests()`

- Embeds the primary RAG query text.
- Calls `PineconeBackend.query_scores_for_test_ids()` — metadata-filtered search for specific test IDs only (no global threshold).
- Returns `test_id → cosine_score` map; merged back into AST results so they show real semantic scores in the UI.

**`semantic/backends/__init__.py`** — `get_backend()`

- **Process-wide singleton** (threading lock).
- First call: creates `PineconeBackend`, logs INFO.
- Subsequent calls: returns cached instance, logs DEBUG.
- `reset_backend_cache_for_tests()` — clears cache for unit tests.

**`semantic/backends/pinecone_backend.py`** — `PineconeBackend`

- `search(embedding, top_k, filter, threshold)` → Pinecone `index.query()`
- `query_scores_for_test_ids(embedding, test_ids, test_repo_id)` → filtered query returning only specified test IDs
- `upsert(vectors)` → stores test embeddings with metadata (`test_id`, `test_repo_id`, `class_name`, `method_name`)

**`semantic/prompts/diff_summarizer.py`** — `summarize_git_diff()`

- Sends diff content to the configured LLM.
- Returns a concise natural-language description of what changed.
- Result is used as the primary vector query.

**`semantic/prompts/query_rewriter.py`** — `QueryRewriterService`

- Rewrites the primary query into multiple perspectives (e.g., "failure path", "data flow", "boundary conditions").
- Each rewritten query is embedded and searched independently.
- All results are merged; first-query results weighted 1.0, subsequent 0.9.

**`semantic/prompts/semantic_classify_prompt.py`** — `build_semantic_classification_prompt()`

- Builds the prompt used to classify retrieved tests as `Critical`, `High`, or `NonRelevant` before the AST–semantic merge.
- Uses diff summary and test metadata (class name, file path, match hints) as classification signals.

**`semantic/embedding_generation/embedding_generator.py`**

- Triggered once per test repository (on upload or manual regenerate).
- Loads test files via `load_test_files_from_repo()`.
- Chunks by tests: `chunk_file_by_tests()` → one chunk per `it()`/`test`/`@Test`/`def test_`.
- Builds embedding text via `text_builder.build_embedding_text()`.
- Batch-embeds via `LLMFactory.create_embedding_provider()`.
- Upserts into Pinecone as `{test_repo_id}_{test_id}` vectors.

### 7.7 LLM Clients

**`llm/factory.py`** — `LLMFactory`

| Method | Returns |
|---|---|
| `create_provider(settings)` | Chat LLM (Gemini / OpenAI / Anthropic / Ollama) |
| `create_embedding_provider(settings)` | Embedding LLM (Gemini / OpenAI / Ollama) |

| Provider | Chat Model (default) | Embedding Model (default) | Config Env Vars |
|---|---|---|---|
| Gemini | `gemini-2.5-flash` | Gemini embedding API | `GEMINI_API_KEY` |
| OpenAI | `gpt-4` | `text-embedding-3-small` | `OPENAI_API_KEY` |
| Anthropic | `claude-3-5-sonnet` | N/A (use OpenAI/Gemini for embeddings) | `ANTHROPIC_API_KEY` |
| Ollama | `llama3` | `nomic-embed-text` | `OLLAMA_BASE_URL` |

### 7.8 Test Analysis Engine

**Trigger**: `analysis_service.run_pipeline(repo_path)` or `POST /test-repositories/{id}/analyze`

**Stage-by-stage** (driven by `test_analysis/engine/repo_analyzer.py`):

```
STAGE 1  detect_languages(repo_path)
           Walk all files, vote by extension frequency.
           Detected: python, java, javascript, c, cpp

STAGE 2  get_plugin_registry() [base_plugin.py]
           Select plugins for detected languages only.

STAGE 3  plugin.scan(repo_path)
           Find all test files matching language patterns.
           e.g. Java: *Test.java in src/test/java/

STAGE 4  plugin.extract(test_files)
           Tree-sitter AST parse each file.
           Extract: test class names, test method names, annotations,
                    referenced imports, described functions (co-location).
           Returns LanguageResult.

STAGE 5  Merger.merge(language_results)
           Combine into single AnalysisResult.
           Deduplicates test_ids across languages.
```

**Language plugins** (`test_analysis/plugins/<lang>/plugin.py`):

| Plugin | Scan pattern | Extractor |
|---|---|---|
| `python/plugin.py` | `test_*.py`, `*_test.py` | `python_analyzer.py` |
| `java/plugin.py` | `*Test.java`, `Test*.java` | `java_analyzer.py` |
| `javascript/plugin.py` | `*.test.js`, `*.spec.js`, `*.test.ts` | `javascript_analyzer.py` |
| `native/plugin.py` | `test_*.c`, `*_test.cpp` | `treesitter_fallback.py` |

### 7.9 VCS Services (GitHub / GitLab)

**`services/github_service.py`**

- `validate_access(url)` — `GET /repos/{owner}/{repo}` with `Authorization: token`
- `get_latest_diff(url, branch)` — `GET /repos/{owner}/{repo}/commits/{branch}` → parent SHA → `GET /compare/{base}...{head}` → unified diff
- `list_branches(url, page, per_page, fetch_all)` — paginated `GET /repos/{owner}/{repo}/branches`
- `get_repository_info(url)` — default branch, visibility

**`services/gitlab_service.py`** — same interface for GitLab REST API v4.

**`services/repository_vcs.py`**

- `resolve_provider(url, stored)` — detects `github` or `gitlab` from URL.
- `effective_branch(requested, selected, default)` — priority resolution.
- `normalize_diff_payload(raw)` — unifies GitHub/GitLab diff shapes into `{diff, changedFiles, stats}`.
- `ensure_branches_present(…)` — injects default/selected branch when missing from page.

### 7.10 Configuration Layer

**`config/settings.py`** — Pydantic `Settings` (reads `.env` at project root):

```
LLM_PROVIDER          = gemini | openai | anthropic | ollama
MODEL_NAME            = override model (optional)
EMBEDDING_PROVIDER    = gemini | openai | ollama
EMBEDDING_MODEL_NAME  = override embedding model (optional)
GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
OLLAMA_BASE_URL       = http://localhost:11434
```

**`semantic/config.py`** — Semantic RAG knobs (env-backed):

```
DEFAULT_SIMILARITY_THRESHOLD       = 0.40 (min cosine for semantic results)
GIT_DIFF_SUMMARY_VALIDATION_THRESHOLD = used to accept/reject LLM summary
RAG_DIFF_ANCHOR_MAX_CHARS          = max chars for diff-anchor text
SEMANTIC_SCORE_CAP                 = max semantic score (capped at 1.0)
BATCH_SIZE                         = Pinecone upsert batch size
LLM_RETRIEVAL_BATCH_SIZE           = LLM classify batch size
LLM_RETRIEVAL_CLASSIFY_TOP_K       = top-K for LLM pass
LLM_RETRIEVAL_MAX_ITEMS            = max LLM inputs
```

---

## 8. Frontend — File-by-File Trigger Chain

### Entry

```
main.jsx → ReactDOM.createRoot → <App/>
App.jsx  → <Router> → <Routes>
  /                          → <AddRepository>
  /repositories              → <RepositoryList>
  /repositories/:repoId      → <RepositoryDetail>    ← MAIN PAGE
  /test-repositories         → <ManageTestRepositories>
  /test-repositories/:id/analysis → <TestRepositoryAnalysis>
```

### Component Trigger Map

| Component | Triggered When | API Calls |
|---|---|---|
| `Header.jsx` | Always visible | — |
| `Sidebar.jsx` | Always visible | — |
| `AddRepository.jsx` | Route `/` | `connectRepository()` |
| `RepositoryList.jsx` | Route `/repositories` | `listRepositories()` |
| `RepositoryDetail.jsx` | Route `/repositories/:id` | `getRepository()`, `getDiff()`, `getBoundTestRepositories()`, `getTotalTestsCount()` |
| `BranchSelector.jsx` | Inside `RepositoryDetail` on mount | `listBranches()`, `updateRepository()` |
| `DiffViewer.jsx` | Inside `RepositoryDetail` | — (renders `diffContent`) |
| `DiffStats.jsx` | Inside `RepositoryDetail` | — (renders `diffStats`) |
| `DiffModal.jsx` | On "View Full Diff" click | — |
| `ActionButtons.jsx` | "Run Test Selection" click | `selectTests()` |
| `ResultsDisplay.jsx` | When `selectionResults` is set | — (renders table) |
| `TestSummaryModal.jsx` | On "View Summary" click | — (renders score breakdown) |
| `RiskAnalysisPanel.jsx` | When risk threshold exceeded | `updateRiskThreshold()` |
| `TestRepositoryBinding.jsx` | Inside `RepositoryDetail` | `getBoundTestRepositories()`, `bindTestRepository()`, `unbindTestRepository()` |
| `EmbeddingStatus.jsx` | Inside `ManageTestRepositories` | `getEmbeddingStatus()` |
| `ManageTestRepositories.jsx` | Route `/test-repositories` | `listTestRepositories()`, `regenerateEmbeddings()` |
| `TestRepositoryUpload.jsx` | Inside `ManageTestRepositories` | `uploadTestRepository()` |
| `TestRepositoryAnalysis.jsx` | Route `/test-repositories/:id/analysis` | `getTestRepositoryAnalysis()` |

### `ResultsDisplay.jsx` — Tab Logic

```
All       → all tests (sorted by confidence_score)
AST       → tests where is_ast_any = true
Semantic  → tests where is_semantic_only = true
Both      → tests where is_ast_any = true AND has semantic score
```

### `TestSummaryModal.jsx` — Score Breakdown

```
Combined    = (ast_score × ast_weight) + (semantic_score × sem_weight) + (llm_score × llm_weight)
LLM wt.    = llm_score contribution  (tooltip: "Model's own relevance score, weighted in blend")
Relevance  = raw LLM score (0–1, unweighted)
```

---

## 9. Database Schema

All tables are created in a named PostgreSQL schema (default `public`, overridable
via `DB_SCHEMA` env var). For each bound test repository, a separate schema is
created (`test_repo_{uuid_short}`).

### Core Tables

```sql
-- Code repository registry
CREATE TABLE repositories (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url          TEXT NOT NULL UNIQUE,
    provider     TEXT,           -- 'github' | 'gitlab'
    local_path   TEXT,
    selected_branch TEXT,
    default_branch  TEXT,
    risk_threshold  INTEGER,
    last_refreshed  TIMESTAMP,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Test case registry (one row per test method)
CREATE TABLE {schema}.test_registry (
    test_id      TEXT PRIMARY KEY,
    class_name   TEXT,
    method_name  TEXT NOT NULL,
    test_type    TEXT,           -- 'unit' | 'integration' | 'e2e' etc.
    file_path    TEXT,
    language     TEXT,
    framework    TEXT
);

-- Static import dependencies per test
CREATE TABLE {schema}.test_static_dependencies (
    test_id      TEXT REFERENCES test_registry(test_id),
    referenced_class TEXT NOT NULL
);

-- Function-level call mapping
CREATE TABLE {schema}.test_function_mapping (
    test_id      TEXT REFERENCES test_registry(test_id),
    module_name  TEXT NOT NULL,
    function_name TEXT NOT NULL
);

-- Test metadata (descriptions, tags)
CREATE TABLE {schema}.test_metadata (
    test_id      TEXT PRIMARY KEY REFERENCES test_registry(test_id),
    description  TEXT,
    tags         JSONB
);

-- Audit log for every selection run
CREATE TABLE audit_log (
    id                  SERIAL PRIMARY KEY,
    repository_id       TEXT,
    run_timestamp       TIMESTAMP DEFAULT NOW(),
    changed_files_count INTEGER,
    selected_tests_count INTEGER,
    confidence_scores   JSONB,
    llm_used            BOOLEAN,
    execution_time_ms   INTEGER,
    threshold_exceeded  BOOLEAN DEFAULT FALSE
);
```

---

## 10. Vector Store (Pinecone)

### Index Configuration

- **Index name**: `PINECONE_INDEX_NAME` (default: `test-embeddings`)
- **Metric**: cosine similarity
- **Dimension**: matches embedding provider (Gemini: 768, OpenAI `text-embedding-3-small`: 1536, Ollama `nomic-embed-text`: 768)
- **Environment/Region**: `PINECONE_ENVIRONMENT` (default: `us-east-1`)

### Vector ID Format

```
{test_repo_id}_{test_id}
```

### Metadata stored per vector

```json
{
  "test_repo_id": "17f1584c",
  "test_id":      "PaymentGatewayTest.testChargeCard",
  "class_name":   "PaymentGatewayTest",
  "method_name":  "testChargeCard",
  "file_path":    "payment/PaymentGatewayTest.java",
  "language":     "java",
  "content":      "<embedding text snippet>"
}
```

### Singleton Pattern

`semantic/backends/__init__.py` caches a single `PineconeBackend` per process:

```python
_backend_lock = threading.Lock()
_cached_backend: Optional[VectorBackend] = None

def get_backend(conn=None) -> VectorBackend:
    # First call: INFO log, creates PineconeBackend, stores in _cached_backend
    # Subsequent calls: DEBUG log, returns _cached_backend
    # If is_available() fails: clears cache, creates new instance
```

---

## 11. Scoring & Selection Logic

### Confidence Score Formula

```
confidence_score = (
    ast_score   × AST_WEIGHT   +
    sem_score   × SEM_WEIGHT   +
    llm_score   × LLM_WEIGHT
) / (AST_WEIGHT + SEM_WEIGHT + LLM_WEIGHT)
```

Where:
- `ast_score` — 1.0 if direct function match, 0.8 class match, 0.6 file co-location
- `sem_score` — cosine similarity (capped at `SEMANTIC_SCORE_CAP`)
- `llm_score` — 0.0–1.0 from LLM reasoning pass (or 0.5 if LLM skipped)

### Match Source Flags

Each test result carries:
```
is_ast_any              → true if found by any AST strategy
is_semantic_only        → true if ONLY found by semantic (no AST match)
semantic_colocated_file → true if found by semantic file co-location
match_type              → 'both' | 'ast_only' | 'semantic_only'
```

### Merge Logic (`process_diff_programmatic.py`)

The `[MERGE]` step is **non-additive**:

```
AST base: N test_ids
Semantic rows: M rows (some overlap with AST, some new)
──────────────────────────────────────────────
Overlap (enriched): overlap_count  ← same test_id, gets both AST + semantic scores
Semantic-only:      sem_only_count ← new test_ids from vector search only
──────────────────────────────────────────────
Final set: N + sem_only_count  (NOT N + M)
```

---

## 12. Risk Analysis Flow

```
selection.py: POST /{id}/select-tests
  │
  ├── changed_files_count = len(diff_data['changedFiles'])
  ├── risk_threshold = repo['risk_threshold']
  │
  ├── if risk_threshold is None  → skip risk analysis (normal selection)
  │
  └── if changed_files_count > risk_threshold:
        ├── Count total tests from all bound test-repo schemas
        ├── log_selection_run(threshold_exceeded=True)
        └── Return SelectionResponse(
              selectionDisabled=True,
              tests=[],       ← empty = run ALL tests
              riskAnalysis={exceeded:True, changed_files, threshold}
            )
```

The frontend `RiskAnalysisPanel` renders the "All tests" warning when `riskAnalysis.exceeded = true`.

---

## 13. Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_API_TOKEN` | For GitHub repos | — | GitHub personal access token |
| `GITHUB_API_URL` | No | `https://api.github.com` | GitHub API base |
| `GITLAB_API_TOKEN` | For GitLab repos | — | GitLab personal access token |
| `GITLAB_API_URL` | No | `https://gitlab.com` | GitLab API base |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `DB_SCHEMA` | No | `public` | Default PostgreSQL schema |
| `PINECONE_API_KEY` | Yes | — | Pinecone API key |
| `PINECONE_INDEX_NAME` | No | `test-embeddings` | Pinecone index name |
| `PINECONE_ENVIRONMENT` | No | `us-east-1` | Pinecone region |
| `VECTOR_BACKEND` | No | `pinecone` | Only `pinecone` is supported |
| `LLM_PROVIDER` | No | `gemini` | `gemini` \| `openai` \| `anthropic` \| `ollama` |
| `EMBEDDING_PROVIDER` | No | `ollama` | `gemini` \| `openai` \| `ollama` |
| `GEMINI_API_KEY` | If using Gemini | — | Google Gemini API key |
| `OPENAI_API_KEY` | If using OpenAI | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | — | Anthropic API key |
| `OLLAMA_BASE_URL` | If using Ollama | `http://localhost:11434` | Ollama server URL |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Allowed CORS origins |
| `ENVIRONMENT` | No | `production` | Set to `development` to enable debug endpoints |
| `TEST_REPO_PATH` | No | auto-detected | Override path for local test repo |

---

## 14. Startup & Initialization Sequence

```
1. uvicorn starts main.py
2. .env loaded from project root
3. backend/ added to sys.path
4. FastAPI app created
5. CORS middleware registered
6. Routers registered (/api/repositories, /api/analysis, /api/…/select-tests, /test-repositories)
7. startup_event() fires:
   a. ensure_audit_log_table_exists()     → PostgreSQL
   b. create_repositories_table()         → PostgreSQL
   c. create_test_repo_tables()           → PostgreSQL
8. First GET /api/repositories/{id}/select-tests:
   a. VCS API called (GitHub/GitLab) for diff
   b. process_diff_and_select_tests() starts
   c. get_backend() called → PineconeBackend initialized (singleton, logged at INFO)
   d. LLMFactory.create_embedding_provider() → embedding client created
   e. Subsequent calls within same request → get_backend() returns cached (logged at DEBUG)
9. shutdown_event(): close_shared_async_client()
```

---

*Document generated by traversing every source file in `backend/` and `frontend/`.
Update whenever a new language plugin, route, or pipeline stage is added.*
