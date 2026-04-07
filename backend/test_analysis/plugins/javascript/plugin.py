"""
JavaScript / TypeScript language plugin.

Wraps JavaScriptAnalyzer.analyze() → LanguageResult.
Implements load_to_db() for js_mocks and js_async_tests tables.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

from psycopg2.extras import execute_values

from test_analysis.engine.models import LanguageResult, TestRecord
from test_analysis.plugins.base_plugin import LanguagePlugin

logger = logging.getLogger(__name__)

# Re-use patterns already in the analyzer
import re
_JS_TEST_PATTERNS = [
    re.compile(r'.*\.test\.(js|ts|jsx|tsx)$'),
    re.compile(r'.*\.spec\.(js|ts|jsx|tsx)$'),
    re.compile(r'.*test.*\.(js|ts|jsx|tsx)$'),
]
_EXCLUDE_DIRS = {'node_modules', '.git', '.idea', '.vscode', 'dist', 'build', '.next', '.nuxt'}


class JavaScriptPlugin(LanguagePlugin):
    """Plugin for JavaScript / TypeScript repositories."""

    language = "javascript"
    file_patterns = ["*.test.js", "*.test.ts", "*.test.jsx", "*.test.tsx",
                     "*.spec.js", "*.spec.ts", "*.spec.jsx", "*.spec.tsx"]

    def scan(self, repo_path: Path) -> List[Path]:
        """Find all JS/TS test files under repo_path."""
        found = []
        for filepath in repo_path.rglob("*"):
            if not filepath.is_file():
                continue
            if any(ex in filepath.parts for ex in _EXCLUDE_DIRS):
                continue
            if filepath.suffix.lower() in (".js", ".ts", ".jsx", ".tsx"):
                if any(p.match(filepath.name) for p in _JS_TEST_PATTERNS):
                    found.append(filepath)
        return sorted(found)

    def extract(self, files: List[Path], repo_path: Path) -> LanguageResult:
        """
        Run JavaScriptAnalyzer and return its LanguageResult.

        Also enriches each TestRecord.description via the smart content
        summariser so the embedding generator has ready-made text to embed.
        """
        from test_analysis.core.analyzers.javascript_analyzer import JavaScriptAnalyzer

        analyzer = JavaScriptAnalyzer()
        # We need an output_dir for the legacy AnalyzerResult, but we won't
        # write files there unless DEBUG_WRITE_JSON is set.
        output_dir = repo_path / "_analysis_output"

        # Pass the pre-scanned file list so the analyzer skips its own
        # internal scan.  This avoids path-encoding / permission issues that
        # can make _scan_test_files() return an empty list on some platforms
        # even when the files are accessible (the scan in JavaScriptPlugin.scan
        # already succeeded, so we know the list is valid).
        analyzer.analyze(repo_path, output_dir, test_files=files)

        result: LanguageResult = analyzer.language_result
        if result is None:
            # No tests found — return empty result
            return LanguageResult(language="javascript")

        # ── Enrich descriptions for embeddings ────────────────────────────
        self._enrich_descriptions(result, repo_path)
        # ──────────────────────────────────────────────────────────────────

        return result

    # ------------------------------------------------------------------
    # DB loading (language-specific tables only)
    # ------------------------------------------------------------------

    def get_table_names(self) -> List[str]:
        return ["js_mocks", "js_async_tests"]

    def load_to_db(self, conn, result: LanguageResult, schema: str) -> None:
        """Write js_mocks and js_async_tests tables."""
        if result.mocks:
            self._load_js_mocks(conn, result.mocks, schema)
        if result.async_tests:
            self._load_js_async_tests(conn, result.async_tests, schema)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _enrich_descriptions(self, result: LanguageResult, repo_path: Path) -> None:
        """
        Build the .description field on each TestRecord by reading the test body
        and running it through the smart content summariser.
        """
        try:
            from semantic.chunking.content_summarizer import summarize_test_content
        except ImportError:
            logger.debug("[javascript] content_summarizer not available — skipping description enrichment")
            return

        provider = os.environ.get("EMBEDDING_PROVIDER", "openai")

        # Build a lookup: file_path → content (avoid re-reading the same file)
        _file_cache: dict = {}

        for record in result.tests:
            if record.content:
                # Already populated by the analyzer
                description = summarize_test_content(record.content, provider=provider)
                record.description = description or record.full_name
                continue

            # Try to read the test body from source
            try:
                fp = Path(record.file)
                if fp not in _file_cache:
                    _file_cache[fp] = fp.read_text(encoding="utf-8", errors="replace") if fp.is_file() else ""
                # Use method name as a minimal description for now
                record.description = f"{record.describe} > {record.name}" if record.describe else record.name
            except Exception:
                record.description = record.full_name

    @staticmethod
    def _load_js_mocks(conn, mocks: list, schema: str) -> None:
        if not mocks:
            return
        values = [
            (
                m.get("test_id", ""),
                m.get("mock_type", ""),
                m.get("mock_target"),
                m.get("mock_implementation"),
            )
            for m in mocks
        ]
        try:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {schema}.js_mocks
                        (test_id, mock_type, mock_target, mock_implementation)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            logger.info(f"[javascript] Loaded {len(values)} js_mocks row(s)")
        except Exception as exc:
            conn.rollback()
            logger.error(f"[javascript] Failed to load js_mocks: {exc}")

    @staticmethod
    def _load_js_async_tests(conn, async_tests: list, schema: str) -> None:
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
                    INSERT INTO {schema}.js_async_tests
                        (test_id, is_async, async_pattern)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            logger.info(f"[javascript] Loaded {len(values)} js_async_tests row(s)")
        except Exception as exc:
            conn.rollback()
            logger.error(f"[javascript] Failed to load js_async_tests: {exc}")
