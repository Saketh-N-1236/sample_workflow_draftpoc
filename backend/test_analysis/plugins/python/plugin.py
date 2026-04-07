"""
Python language plugin.

Wraps PythonAnalyzer.analyze() → LanguageResult.
Implements load_to_db() for python_fixtures, python_decorators, python_async_tests tables.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

from psycopg2.extras import execute_values

from test_analysis.engine.models import LanguageResult
from test_analysis.plugins.base_plugin import LanguagePlugin

logger = logging.getLogger(__name__)

_EXCLUDE_DIRS = {
    "venv", ".venv", "__pycache__", ".git", ".idea", ".tox",
    "build", "dist", "node_modules", ".mypy_cache", ".pytest_cache",
}


class PythonPlugin(LanguagePlugin):
    """Plugin for Python repositories."""

    language = "python"
    file_patterns = ["test_*.py", "*_test.py"]

    # ------------------------------------------------------------------
    # scan
    # ------------------------------------------------------------------

    def scan(self, repo_path: Path) -> List[Path]:
        """Find all Python test files under repo_path."""
        found = []
        for filepath in repo_path.rglob("*.py"):
            if not filepath.is_file():
                continue
            if any(ex in filepath.parts for ex in _EXCLUDE_DIRS):
                continue
            name = filepath.name
            if name.startswith("test_") or name.endswith("_test.py"):
                found.append(filepath)
            # Also accept conftest.py
            elif name == "conftest.py":
                found.append(filepath)
        return sorted(found)

    # ------------------------------------------------------------------
    # extract
    # ------------------------------------------------------------------

    def extract(self, files: List[Path], repo_path: Path) -> LanguageResult:
        """Run PythonAnalyzer and return its LanguageResult."""
        from test_analysis.core.analyzers.python_analyzer import PythonAnalyzer

        analyzer = PythonAnalyzer()
        output_dir = repo_path / "_analysis_output"
        analyzer.analyze(repo_path, output_dir)

        result: LanguageResult = analyzer.language_result
        if result is None:
            return LanguageResult(language="python")

        self._enrich_descriptions(result)
        return result

    # ------------------------------------------------------------------
    # DB loading (language-specific tables only)
    # ------------------------------------------------------------------

    def get_table_names(self) -> List[str]:
        return ["python_fixtures", "python_decorators", "python_async_tests"]

    def load_to_db(self, conn, result: LanguageResult, schema: str) -> None:
        """Write python_fixtures, python_decorators, python_async_tests tables."""
        if result.python_fixtures:
            self._load_python_fixtures(conn, result.python_fixtures, schema)
        if result.python_decorators:
            self._load_python_decorators(conn, result.python_decorators, schema)
        if result.async_tests:
            self._load_python_async_tests(conn, result.async_tests, schema)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _enrich_descriptions(self, result: LanguageResult) -> None:
        """Add .description field to each TestRecord for embedding generation."""
        try:
            from semantic.chunking.content_summarizer import summarize_test_content
        except ImportError:
            logger.debug("[python] content_summarizer not available — skipping description enrichment")
            return

        provider = os.environ.get("EMBEDDING_PROVIDER", "openai")

        for record in result.tests:
            if record.content:
                record.description = summarize_test_content(record.content, provider=provider) or record.full_name
            else:
                record.description = record.full_name

    @staticmethod
    def _load_python_fixtures(conn, fixtures: list, schema: str) -> None:
        if not fixtures:
            return
        values = [
            (
                f.get("test_id", ""),
                f.get("fixture_name", ""),
                f.get("fixture_scope", "function"),
                f.get("fixture_params"),
            )
            for f in fixtures
        ]
        try:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {schema}.python_fixtures
                        (test_id, fixture_name, fixture_scope, fixture_params)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            logger.info(f"[python] Loaded {len(values)} python_fixtures row(s)")
        except Exception as exc:
            conn.rollback()
            logger.error(f"[python] Failed to load python_fixtures: {exc}")

    @staticmethod
    def _load_python_decorators(conn, decorators: list, schema: str) -> None:
        if not decorators:
            return
        values = [
            (
                d.get("test_id", ""),
                d.get("decorator_name", ""),
                d.get("decorator_args"),
            )
            for d in decorators
        ]
        try:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {schema}.python_decorators
                        (test_id, decorator_name, decorator_args)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            logger.info(f"[python] Loaded {len(values)} python_decorators row(s)")
        except Exception as exc:
            conn.rollback()
            logger.error(f"[python] Failed to load python_decorators: {exc}")

    @staticmethod
    def _load_python_async_tests(conn, async_tests: list, schema: str) -> None:
        if not async_tests:
            return
        values = [
            (
                t.get("test_id", ""),
                t.get("is_async", False),
                t.get("async_pattern", "async/await"),
            )
            for t in async_tests
        ]
        try:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {schema}.python_async_tests
                        (test_id, is_async, async_pattern)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            logger.info(f"[python] Loaded {len(values)} python_async_tests row(s)")
        except Exception as exc:
            conn.rollback()
            logger.error(f"[python] Failed to load python_async_tests: {exc}")
