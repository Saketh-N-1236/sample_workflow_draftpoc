## Backend Code Review (Beginner-Friendly Overview)

This document gives a friendly tour of the `backend` folder. It explains what each file or module is for and how the pieces fit together.

### High-level architecture
- **API layer (`backend/api/`)**: FastAPI app and HTTP routes you can call from the frontend or tools.
- **Services (`backend/services/`)**: Business logic; talks to VCS (GitHub/GitLab), databases, and LLMs.
- **Semantic (`backend/semantic/`)**: Embeddings, retrieval, and RAG-style search helpers.
- **LLM (`backend/llm/`)**: Pluggable clients and factories for OpenAI/Ollama/Gemini.
- **Config (`backend/config/`)**: Settings and config loading, including language-specific options.
- **Git diff processing (`backend/git_diff_processor/`)**: Logic to analyze code diffs and selection.
- **Deterministic data (`backend/deterministic/`)**: Repeatable loading/migrations for test data.
- **Parsers/registry (`backend/parsers/`)**: Plugin registry for parsing/analysis.
- **Scripts and utilities**: Batch files/PowerShell scripts and smoke tests to run pipelines.

---

### backend/
- `README.md`: Backend-specific notes and quick start.
- `requirements.txt`: Python dependencies for the backend.
- `run_backend.bat` / `run_backend_no_reload.bat`: Windows helpers to run the API (with/without reload).
- `run_dependency_extraction.ps1` / `load_all_data.ps1`: PowerShell helpers to extract dependencies/load data.
- `scripts/`:
  - `smoke_plan_imports.py`: Quick smoke test to ensure key imports/pipelines work.
  - `test_scenarios.py`: Runs example scenarios or end-to-end checks.

### backend/api/
- `__init__.py`: Package marker.
- `main.py`: FastAPI application entrypoint. Mounts routers from `routes/`, configures middleware, etc.
- `models/`:
  - `__init__.py`: Package marker.
  - `repository.py`: Pydantic models for repository metadata (owner, name, branch, etc.).
  - `semantic.py`: Pydantic models for semantic/embedding queries and results.
  - `test_repository.py`: Models specifically for test repository scenarios.
- `routes/`:
  - `__init__.py`: Package marker.
  - `analysis.py`: HTTP endpoints for code/test analysis workflows.
  - `repositories.py`: Endpoints to manage or query repositories and their data.
  - `selection.py`: Endpoints for selection logic (e.g., choosing relevant files/tests).
  - `test_repositories.py`: Endpoints supporting test repositories and verification.

### backend/config/
- `__init__.py`: Package marker.
- `settings.py`: Central runtime configuration (env vars, flags, API keys, etc.).
- `config_loader.py`: Helpers to load/merge configuration sources (files, env).
- `language_configs.yaml`: Language-specific settings (e.g., file globs, parsing rules).

### backend/services/
- `__init__.py`: Package marker.
- `analysis_service.py`: Orchestrates analysis flows across parsers, diffs, and semantic search.
- `audit_service.py`: Tracks or records operations/events for audit or traceability.
- `github_service.py` / `gitlab_service.py`: Connects to GitHub/GitLab APIs (repos, commits, diffs).
- `http_client.py`: Shared HTTP client wrapper with retries, headers, etc.
- `llm_reasoning_service.py`: Structured LLM calls for reasoning/planning steps.
- `repository_db.py`: Persistence layer for repository/test data.
- `repository_vcs.py`: Git operations (clone, fetch, checkout) abstracted from API.
- `selection_service.py`: Implements selection/triage of relevant code/tests/files.
- `test_repo_service.py`: Helpers dedicated to synthetic/test repositories used in validation.

### backend/semantic/
- `__init__.py`: Package marker.
- `README.md`: Overview of the semantic stack.
- `config.py`: High-level config for embeddings, vector backends, and retrieval.
- `clear_embeddings.py`: Utility to wipe/reset stored embeddings.
- `backends/`:
  - `base.py`: Abstract backend interface (e.g., index, query).
  - `pinecone_backend.py`: Pinecone-based vector store implementation.
- `chunking/`:
  - `content_summarizer.py`: Summarizes content or chunks for efficient retrieval.
  - `test_chunker.py`: Tests for the chunking logic.
- `embedding_generation/`:
  - `embedding_generator.py`: Generates embeddings from text/code.
  - `text_builder.py`: Prepares/normalizes text for embedding.
- `ingestion/`:
  - `data_transformer.py`: Transforms raw repo/test data into an indexable form.
  - `test_data_loader.py`: Tests for ingestion pipeline.
- `prompts/`:
  - `diff_summarizer.py`, `query_rewriter.py`: Prompt templates/utilities for LLM flows.
  - `README_PROMPTS.md`: Notes on prompts and usage.
- `retrieval/`:
  - `multi_query_search.py`: Multi-angle query expansion and search.
  - `query_builder.py`: Builds normalized search queries.
  - `rag_pipeline.py`: RAG pipeline composition (retrieve, augment, generate).
  - `semantic_search.py`: Semantic/vector search logic.
  - `validation.py`: Validates retrieval or ranking quality.

### backend/llm/
- `__init__.py`: Package marker.
- `README.md` / `LLM_CALL_ANALYSIS.md`: Notes and deep-dive on LLM interactions.
- `base.py`: Base interfaces for LLM providers.
- `factory.py`: Selects an LLM client by name/config.
- `models.py`: Data models for prompts, messages, and responses.
- `openai_client.py` / `ollama_client.py` / `gemini_client.py`: Provider-specific clients.
- `example_usage.py`: How to call the LLM layer in practice.

### backend/git_diff_processor/
- `__init__.py`: Package marker.
- `README.md`: Overview of how diffs are processed.
- `git_diff_processor.py`: Core orchestration to parse and process git diffs.
- `diff_scenario_analysis.py`: Analyzes specific diff scenarios and their impact.
- `cochange_tight_suite.py`: Identifies files that frequently change together.
- `process_diff_programmatic.py`: Programmatic entry to run processors as a script.
- `selection_engine.py`: Uses diff insights to choose relevant code/tests.
- `cli_output.py`: Pretty/structured CLI output for diff processing.
- `utils/`: Shared helpers for the diff processor.
- `tests/`: Unit tests for this package.

### backend/deterministic/
- `__init__.py`: Package marker.
- `README.md`: How to use the deterministic loaders and why.
- `requirements.txt`: Specific deps for deterministic pipelines.
- `db_connection.py`: Database connection utilities (for repeatable data loads).
- `loader.py`: Orchestrates staged/ordered loading flows.
- `00_migrate_test_structure.py`, `01_create_tables.py`, `02_create_test_repo_tables.py`: Migration/setup scripts for test data.
- `07_verify_data.py`: Verifies loaded data integrity.
- `parsing/`: Parsers used in deterministic pipelines.
- `utils/`: Common helpers for the deterministic flows.

### backend/parsers/
- `__init__.py`: Package marker.
- `registry.py`: Central plugin registry to discover/route to available parsers.

### backend/data/test_repo_data/
- Multiple folders with synthetic repositories and fixtures for testing:
  - `17f1584c/`: Sample Java repo (many `.java` files).
  - `261b672a/`: Sample JavaScript repo.
  - `5079eaac/test_repository/` and `604043aa/`: Mixed-language test repos (code, JSON, docs).

### backend/test_analysis/
- Test inputs and outputs (JSON, Python scripts, and docs) to validate analysis logic end-to-end.

---

### How the pieces work together (short flow)
1) The frontend calls `backend/api/main.py` endpoints (in `routes/`).
2) A route calls into a `services/*_service.py` function.
3) Services fetch repo data (via `repository_vcs.py`, `github_service.py`, or `gitlab_service.py`), run diff/selection (`git_diff_processor/`), and optionally semantic retrieval (`semantic/`).
4) For deeper reasoning or summarization, services call the `llm/` layer.
5) Results are returned via Pydantic models in `api/models/` to the client.

That’s it—use this as a map when navigating the backend codebase.

