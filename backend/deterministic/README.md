# Deterministic — Database Layer for Test Analysis

## Overview

The **deterministic** package is the PostgreSQL persistence layer for the Test Impact Analysis app. It provides:

- **Database connections** (default schema and per–test-repo schema)
- **Table creation** for test registry, reverse index, dependencies, metadata, and language-specific tables
- **Loading** of analysis results from the test analysis pipeline into the database
- **Management tables** for multiple test repositories and repo–test-repo bindings
- **Parsing** (`parsing/`) — unified git diff parsing and search-query building (`parse_git_diff`, `build_search_queries`, symbol extraction). Consumed by **git_diff_processor**, **semantic** RAG, and diagnostics scripts.

Analysis output is loaded **in-process** from `AnalysisResult` (no JSON files); the **git_diff_processor** and **selection service** then query these tables for AST-based test selection.

---

## Role in the Application

| Consumer | What it uses |
|----------|----------------|
| **Analysis pipeline** (`services/analysis_service`) | After `RepoAnalyzer.analyze()`, calls `load_to_db(conn, analysis_result, schema)` to create tables (if needed) and fill them. |
| **Test repo management** (`services/test_repo_service`) | Uses `get_connection`, `get_connection_with_schema`, `create_schema_if_not_exists` for creating schemas and managing `test_repositories` / `repository_test_bindings`. |
| **Selection** (`selection_service`, `git_diff_processor`) | Use `get_connection_with_schema(schema_name)` to query `test_registry`, reverse index, function mappings, etc., for AST-based test selection. |
| **Audit** (`audit_service`) | Uses `get_connection` and `DB_SCHEMA` to write to `selection_audit_log`. |
| **API routes** (analysis, test_repositories, selection) | Use deterministic connections for counts, listing tests, and schema-specific queries. |

---

## Schema Model

- **Default schema** (`DB_SCHEMA`, usually `planon1`): Holds **management** data and shared tables:
  - `test_repositories` — uploaded test repos (id, name, extracted_path, hash, status, etc.)
  - `repository_test_bindings` — which source repos are bound to which test repos
  - `selection_audit_log` — audit log for test selection runs (when `repository_id` is set)

- **Per–test-repo schemas** (e.g. `test_repo_261b672a`): One schema per analyzed test repository. Each contains:
  - **Core:** `test_registry`, `test_dependencies`, `reverse_index`, `test_function_mapping`, `test_metadata`, `test_structure`
  - **Language-specific (if applicable):** `js_mocks`, `js_async_tests`; `java_reflection`, `java_di_fields`, `java_annotations`; `python_fixtures`, `python_decorators`, `python_async_tests`

Test selection runs against a **specific schema** (the bound test repo’s schema); the git_diff_processor and selection service use `get_connection_with_schema(schema_name)` so all queries are in that schema.

---

## Main APIs

### Connection

- **`get_connection()`** — Context manager that returns a connection to the default database with `search_path` set to `DB_SCHEMA` (e.g. `planon1`). Used for management tables and audit.
- **`get_connection_with_schema(schema_name)`** — Context manager that returns a connection with `search_path` set to the given schema (e.g. `test_repo_261b672a`). Used for all test-registry and reverse-index queries for one test repo.
- **`create_schema_if_not_exists(schema_name)`** — Creates the schema if it does not exist (e.g. when creating a new test repo).
- **`test_connection(schema_to_test=None)`** — Verifies connectivity (optional schema for search_path check).

### Loading

- **`load_to_db(conn, result: AnalysisResult, schema: str)`** (in `loader.py`) — Loads a full `AnalysisResult` (from `RepoAnalyzer.analyze()`) into the given schema: ensures tables exist, then fills core and language-specific tables. Called by the analysis service after analysis.

---

## Files in This Package

| File | Purpose |
|------|---------|
| **`db_connection.py`** | Connection helpers: `get_connection`, `get_connection_with_schema`, `create_schema_if_not_exists`, `test_connection`, pool and config from `.env`. |
| **`parsing/diff_parser.py`** | Parses unified git diff (standard + headerless formats); extracts changed files, methods, classes, line ranges; builds PostgreSQL search queries. Import as `deterministic.parsing` or `deterministic.parsing.diff_parser`. |
| **`parsing/__init__.py`** | Re-exports the main parsing API. |
| **`loader.py`** | Single entry point for loading: `load_to_db(conn, analysis_result, schema)`. Replaces the old multi-script load; creates tables via `01_create_tables` and inserts all core and language-specific data. |
| **`01_create_tables.py`** | Defines and creates core and language-specific tables in a given schema (`SchemaDefinition`, `create_all_tables_in_schema`). Used by the loader and by standalone table-creation. |
| **`02_create_test_repo_tables.py`** | Creates management tables in the default schema: `test_repositories`, `repository_test_bindings`, and related structures. Run once or when setting up a new environment. |
| **`00_migrate_test_structure.py`** | One-off migration: adds `test_count` to `test_structure` in all `test_repo_*` schemas. Run once on existing DBs. |
| **`07_verify_data.py`** | Verification script: counts rows, checks integrity, sample queries. Optional; run with `python deterministic/07_verify_data.py`. |
| **`utils/db_helpers.py`** | Helpers for batch insert, queries (e.g. `get_tests_for_production_class`), and other DB operations. |

Console helpers (`print_header`, `print_section`, `print_item`) for scripts live in **`test_analysis/utils/output_formatter.py`** (shared with embedding tooling).

---

## Environment and Setup

- **`.env`** (under backend or project root) should define:
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - `DB_SCHEMA` (default schema, e.g. `planon1`)

- **First-time setup (typical order):**
  1. Run `02_create_test_repo_tables.py` to create management tables in the default schema.
  2. When a test repo is uploaded and analyzed, the app will create a new schema (e.g. `test_repo_<hash>`) and call `load_to_db()` so no need to run `01_create_tables.py` by hand for that schema.
  3. Optionally run `00_migrate_test_structure.py` once if you have existing test_repo schemas without `test_count`.
  4. Optionally run `07_verify_data.py` to verify data in a schema.

---

## Dependencies

- **psycopg2** — PostgreSQL adapter
- **python-dotenv** — Load `.env`
- **test_analysis** — `AnalysisResult` and related models (for `loader.load_to_db`)

The rest of the app (api, services, git_diff_processor) depends on **deterministic** for all test-registry and management DB access.
