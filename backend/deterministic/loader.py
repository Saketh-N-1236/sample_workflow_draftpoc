"""
Unified database loader — replaces deterministic scripts 02 through 14.

Public API::

    from deterministic.loader import load_to_db

    load_to_db(conn, analysis_result, schema_name="my_schema")

The function:
  1. Creates all necessary tables (calls create_tables from 01_create_tables.py)
  2. Loads core tables: test_registry, test_dependencies, reverse_index,
     test_function_mapping, test_metadata, test_structure
  3. Conditionally loads language tables:
       - javascript → js_mocks, js_async_tests
       - java       → java_reflection, java_di_fields, java_annotations
       - python     → python_fixtures, python_decorators, python_async_tests

This runs in-process — no subprocess.run(), no JSON file reads.
"""

from __future__ import annotations

import json
import logging
import re as _re
from typing import Any, Dict, List, Optional

from psycopg2.extras import execute_values

from test_analysis.engine.models import AnalysisResult

logger = logging.getLogger(__name__)

# Regex for extracting primary symbol from Jest describe labels:
# "capitalizeFirstLetter with checkWhiteSpace" → "capitalizeFirstLetter"
_DESCRIBE_SPLIT_RE = _re.compile(
    r'\s+(?:with|uses|from|for|in|that|>|→|:)\s+', _re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_to_db(conn, result: AnalysisResult, schema: str) -> Dict[str, int]:
    """
    Load a fully-populated AnalysisResult into PostgreSQL.

    Args:
        conn:    An active psycopg2 connection (from get_connection_with_schema).
        result:  AnalysisResult produced by RepoAnalyzer.analyze().
        schema:  Target PostgreSQL schema name.

    Returns:
        A dict with row counts per table for logging/debugging.
    """
    stats: Dict[str, int] = {}

    logger.info(f"[loader] Loading {result.total_tests} test(s) into schema '{schema}'")

    # Step 1: Ensure tables exist
    _ensure_tables(conn, schema, result.detected_languages)

    # Step 2: Core tables (always)
    stats["test_registry"] = _load_test_registry(conn, result, schema)
    stats["test_dependencies"] = _load_dependencies(conn, result, schema)
    stats["reverse_index"] = _load_reverse_index(conn, result, schema)
    stats["test_function_mapping"] = _load_function_mappings(conn, result, schema)
    stats["test_metadata"] = _load_metadata(conn, result, schema)
    stats["test_structure"] = _load_structure(conn, result, schema)

    # Step 3: Language-specific tables (conditional)
    if "javascript" in result.detected_languages:
        js_lr = result.get_language("javascript")
        if js_lr:
            stats["js_mocks"] = _load_js_mocks(conn, js_lr.mocks, schema)
            stats["js_async_tests"] = _load_js_async_tests(conn, js_lr.async_tests, schema)

    if "java" in result.detected_languages:
        java_lr = result.get_language("java")
        if java_lr:
            stats["java_reflection"] = _load_java_reflection(conn, java_lr.java_reflection, schema)
            stats["java_di_fields"] = _load_java_di_fields(conn, java_lr.java_di_fields, schema)
            stats["java_annotations"] = _load_java_annotations(conn, java_lr.java_annotations, schema)

    if "python" in result.detected_languages:
        py_lr = result.get_language("python")
        if py_lr:
            stats["python_fixtures"] = _load_python_fixtures(conn, py_lr.python_fixtures, schema)
            stats["python_decorators"] = _load_python_decorators(conn, py_lr.python_decorators, schema)
            stats["python_async_tests"] = _load_python_async(conn, py_lr.async_tests, schema)

    # Step 4: Post-processing — enrich reverse_index from describe labels
    enriched = _enrich_reverse_index_from_class_names(conn, schema)
    stats["reverse_index_enriched"] = enriched

    total_rows = sum(v for v in stats.values())
    logger.info(f"[loader] Done — {total_rows} total row(s) written. Stats: {stats}")
    return stats


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

def _ensure_tables(conn, schema: str, detected_languages: List[str]) -> None:
    """Call create_all_tables_in_schema from 01_create_tables.py in-process."""
    try:
        import importlib.util
        from pathlib import Path as _Path
        _det_dir = _Path(__file__).parent
        spec = importlib.util.spec_from_file_location(
            "create_tables_module",
            _det_dir / "01_create_tables.py",
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            if hasattr(mod, "create_all_tables_in_schema") and hasattr(mod, "SchemaDefinition"):
                # Build SchemaDefinition from detected languages
                java_tables = (
                    ["java_reflection", "java_di_fields", "java_annotations"]
                    if "java" in detected_languages else []
                )
                python_tables = (
                    ["python_fixtures", "python_decorators", "python_async_tests"]
                    if "python" in detected_languages else []
                )
                js_tables = (
                    ["js_mocks", "js_async_tests"]
                    if any(l in detected_languages for l in ("javascript", "typescript"))
                    else []
                )
                schema_def = mod.SchemaDefinition(
                    java_tables=java_tables,
                    python_tables=python_tables,
                    js_tables=js_tables,
                )
                mod.create_all_tables_in_schema(conn, schema, schema_def)
                logger.info(f"[loader] Tables ensured in schema '{schema}' (languages={detected_languages})")
                return
    except Exception as exc:
        logger.warning(f"[loader] Could not call create_all_tables_in_schema: {exc} — assuming tables exist")


# ---------------------------------------------------------------------------
# Core loaders
# ---------------------------------------------------------------------------

def _load_test_registry(conn, result: AnalysisResult, schema: str) -> int:
    if not result.all_tests:
        return 0
    values = [
        (
            t.id,
            t.file,
            t.describe or None,
            t.full_name,
            t.test_type,
            t.line_number,
            t.language,
            t.repository_path or result.repo_path,
        )
        for t in result.all_tests
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.test_registry
                    (test_id, file_path, class_name, method_name, test_type,
                     line_number, language, repository_path)
                VALUES %s
                ON CONFLICT (test_id) DO UPDATE SET
                    file_path        = EXCLUDED.file_path,
                    class_name       = EXCLUDED.class_name,
                    method_name      = EXCLUDED.method_name,
                    test_type        = EXCLUDED.test_type,
                    line_number      = EXCLUDED.line_number,
                    language         = EXCLUDED.language,
                    repository_path  = EXCLUDED.repository_path
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] test_registry: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] test_registry failed: {exc}")
        return 0


def _load_dependencies(conn, result: AnalysisResult, schema: str) -> int:
    """Flatten dependency records into (test_id, referenced_class, import_type) rows."""
    if not result.dependencies:
        return 0

    rows: List[tuple] = []
    for dep in result.dependencies:
        test_id = dep.get("test_id", "")
        refs = dep.get("referenced_classes", [])
        ref_types = dep.get("reference_types", {})
        if isinstance(refs, list):
            for cls in refs:
                rows.append((test_id, cls, ref_types.get(cls, "direct_import")))
        elif isinstance(refs, str) and refs:
            rows.append((test_id, refs, dep.get("import_type", "direct_import")))

    if not rows:
        return 0

    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.test_dependencies
                    (test_id, referenced_class, import_type)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                rows,
            )
        conn.commit()
        logger.info(f"[loader] test_dependencies: {len(rows)} row(s)")
        return len(rows)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] test_dependencies failed: {exc}")
        return 0


def _load_reverse_index(conn, result: AnalysisResult, schema: str) -> int:
    if not result.reverse_index:
        return 0

    rows: List[tuple] = []
    for symbol, entries in result.reverse_index.items():
        for e in entries:
            rows.append((
                symbol,
                e.get("test_id", ""),
                e.get("file_path") or e.get("test_file_path"),
                e.get("reference_type", "direct_import"),
            ))

    if not rows:
        return 0

    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.reverse_index
                    (production_class, test_id, test_file_path, reference_type)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                rows,
            )
        conn.commit()
        logger.info(f"[loader] reverse_index: {len(rows)} row(s)")
        return len(rows)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] reverse_index failed: {exc}")
        return 0


def _load_function_mappings(conn, result: AnalysisResult, schema: str) -> int:
    if not result.function_mappings:
        return 0

    values = [
        (
            m.get("test_id", ""),
            m.get("module_name", ""),
            m.get("function_name", ""),
            m.get("call_type"),
            m.get("source"),
        )
        for m in result.function_mappings
    ]

    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.test_function_mapping
                    (test_id, module_name, function_name, call_type, source)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] test_function_mapping: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] test_function_mapping failed: {exc}")
        return 0


def _load_metadata(conn, result: AnalysisResult, schema: str) -> int:
    if not result.metadata:
        return 0

    values = [
        (
            m.get("test_id", ""),
            m.get("description"),
            json.dumps(m.get("markers", [])) if m.get("markers") else None,
            m.get("is_async", False),
            m.get("is_parameterized", False),
            m.get("pattern"),
            m.get("line_number"),
        )
        for m in result.metadata
    ]

    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.test_metadata
                    (test_id, description, markers, is_async, is_parameterized, pattern, line_number)
                VALUES %s
                ON CONFLICT (test_id) DO UPDATE SET
                    description     = EXCLUDED.description,
                    markers         = EXCLUDED.markers,
                    is_async        = EXCLUDED.is_async,
                    is_parameterized = EXCLUDED.is_parameterized,
                    pattern         = EXCLUDED.pattern,
                    line_number     = EXCLUDED.line_number
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] test_metadata: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] test_metadata failed: {exc}")
        return 0


def _load_structure(conn, result: AnalysisResult, schema: str) -> int:
    """Load test structure summary (one row per category)."""
    from collections import defaultdict

    by_cat: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"file_count": 0, "test_count": 0, "total_lines": 0})
    files_seen: Dict[str, set] = defaultdict(set)

    for t in result.all_tests:
        cat = t.test_type or "unit"
        by_cat[cat]["test_count"] += 1
        files_seen[cat].add(t.file)

    for cat in by_cat:
        by_cat[cat]["file_count"] = len(files_seen[cat])

    if not by_cat:
        return 0

    rows = [
        (cat, cat, stats["file_count"], stats["test_count"], stats["total_lines"])
        for cat, stats in by_cat.items()
    ]

    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.test_structure
                    (directory_path, category, file_count, test_count, total_lines)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                rows,
            )
        conn.commit()
        logger.info(f"[loader] test_structure: {len(rows)} row(s)")
        return len(rows)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] test_structure failed: {exc}")
        return 0


# ---------------------------------------------------------------------------
# JavaScript-specific
# ---------------------------------------------------------------------------

def _load_js_mocks(conn, mocks: list, schema: str) -> int:
    if not mocks:
        return 0
    values = [
        (m.get("test_id", ""), m.get("mock_type", ""), m.get("mock_target"), m.get("mock_implementation"))
        for m in mocks
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.js_mocks (test_id, mock_type, mock_target, mock_implementation)
                VALUES %s ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] js_mocks: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] js_mocks failed: {exc}")
        return 0


def _load_js_async_tests(conn, async_tests: list, schema: str) -> int:
    if not async_tests:
        return 0
    values = [
        (t.get("test_id", ""), t.get("is_async", False), t.get("async_pattern", "async/await"))
        for t in async_tests
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.js_async_tests (test_id, is_async, async_pattern)
                VALUES %s ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] js_async_tests: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] js_async_tests failed: {exc}")
        return 0


# ---------------------------------------------------------------------------
# Java-specific
# ---------------------------------------------------------------------------

def _load_java_reflection(conn, reflection_calls: list, schema: str) -> int:
    if not reflection_calls:
        return 0
    values = [
        (r.get("test_id", ""), r.get("reflection_type", ""), r.get("target_class"), r.get("target_method"))
        for r in reflection_calls
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.java_reflection (test_id, reflection_type, target_class, target_method)
                VALUES %s ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] java_reflection: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] java_reflection failed: {exc}")
        return 0


def _load_java_di_fields(conn, di_fields: list, schema: str) -> int:
    if not di_fields:
        return 0
    values = [
        (d.get("test_id", ""), d.get("field_name", ""), d.get("field_type", ""), d.get("annotation", ""))
        for d in di_fields
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.java_di_fields (test_id, field_name, field_type, annotation)
                VALUES %s ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] java_di_fields: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] java_di_fields failed: {exc}")
        return 0


def _load_java_annotations(conn, annotations: list, schema: str) -> int:
    if not annotations:
        return 0
    values = [
        (a.get("test_id", ""), a.get("annotation_name", ""), a.get("annotation_args"))
        for a in annotations
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.java_annotations (test_id, annotation_name, annotation_args)
                VALUES %s ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] java_annotations: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] java_annotations failed: {exc}")
        return 0


# ---------------------------------------------------------------------------
# Python-specific
# ---------------------------------------------------------------------------

def _load_python_fixtures(conn, fixtures: list, schema: str) -> int:
    if not fixtures:
        return 0
    values = [
        (f.get("test_id", ""), f.get("fixture_name", ""), f.get("fixture_scope", "function"), f.get("fixture_params"))
        for f in fixtures
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.python_fixtures (test_id, fixture_name, fixture_scope, fixture_params)
                VALUES %s ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] python_fixtures: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] python_fixtures failed: {exc}")
        return 0


def _load_python_decorators(conn, decorators: list, schema: str) -> int:
    if not decorators:
        return 0
    values = [
        (d.get("test_id", ""), d.get("decorator_name", ""), d.get("decorator_args"))
        for d in decorators
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.python_decorators (test_id, decorator_name, decorator_args)
                VALUES %s ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] python_decorators: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] python_decorators failed: {exc}")
        return 0


def _load_python_async(conn, async_tests: list, schema: str) -> int:
    if not async_tests:
        return 0
    values = [
        (t.get("test_id", ""), t.get("is_async", False), t.get("async_pattern", "async/await"))
        for t in async_tests
    ]
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.python_async_tests (test_id, is_async, async_pattern)
                VALUES %s ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info(f"[loader] python_async_tests: {len(values)} row(s)")
        return len(values)
    except Exception as exc:
        conn.rollback()
        logger.error(f"[loader] python_async_tests failed: {exc}")
        return 0


# ---------------------------------------------------------------------------
# Post-processing: enrich reverse_index from describe labels
# ---------------------------------------------------------------------------

def _enrich_reverse_index_from_class_names(conn, schema: str) -> int:
    """
    Read test_registry.class_name and insert reverse_index entries for
    the primary symbol extracted from the Jest describe label.

    Mirrors the logic in 04_load_reverse_index.py:enrich_reverse_index_from_class_names().
    """
    inserted = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT test_id, file_path, class_name, method_name
                FROM {schema}.test_registry
                WHERE class_name IS NOT NULL AND class_name != ''
                """
            )
            rows = cur.fetchall()

        if not rows:
            return 0

        new_entries: List[tuple] = []
        for test_id, file_path, class_name, method_name in rows:
            # Extract primary symbol from the describe label
            primary = _DESCRIBE_SPLIT_RE.split(class_name, maxsplit=1)[0].strip()
            primary = primary.split(" > ")[0].strip()
            if not primary:
                continue

            # (primary, test_id) entry
            new_entries.append((primary, test_id, file_path, "describe_label"))

            # Also add full class_name if different
            if primary != class_name:
                new_entries.append((class_name, test_id, file_path, "describe_label"))

        if not new_entries:
            return 0

        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.reverse_index
                    (production_class, test_id, test_file_path, reference_type)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                new_entries,
            )
        conn.commit()
        inserted = len(new_entries)
        logger.info(f"[loader] reverse_index enriched: {inserted} row(s) from describe labels")
    except Exception as exc:
        conn.rollback()
        logger.warning(f"[loader] reverse_index enrichment failed: {exc}")

    return inserted
