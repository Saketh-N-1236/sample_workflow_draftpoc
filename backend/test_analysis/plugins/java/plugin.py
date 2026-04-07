"""
Java language plugin.

Wraps JavaAnalyzer.analyze() → LanguageResult.
Implements load_to_db() for java_reflection, java_di_fields, java_annotations tables.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List

from psycopg2.extras import execute_values

from test_analysis.engine.models import LanguageResult
from test_analysis.plugins.base_plugin import LanguagePlugin

logger = logging.getLogger(__name__)

_EXCLUDE_DIRS = {"target", "build", ".git", ".gradle", ".mvn", "node_modules", ".idea", "bin", "out"}

_JAVA_TEST_PATTERNS = [
    re.compile(r'.*Test\.java$'),
    re.compile(r'.*Tests\.java$'),
    re.compile(r'.*TestCase\.java$'),
    re.compile(r'Test.*\.java$'),
]


class JavaPlugin(LanguagePlugin):
    """Plugin for Java repositories."""

    language = "java"
    file_patterns = ["*Test.java", "*Tests.java", "Test*.java"]

    # ------------------------------------------------------------------
    # scan
    # ------------------------------------------------------------------

    def scan(self, repo_path: Path) -> List[Path]:
        """Find all Java test files under repo_path."""
        found = []
        for filepath in repo_path.rglob("*.java"):
            if not filepath.is_file():
                continue
            if any(ex in filepath.parts for ex in _EXCLUDE_DIRS):
                continue
            if any(p.match(filepath.name) for p in _JAVA_TEST_PATTERNS):
                found.append(filepath)
        return sorted(found)

    # ------------------------------------------------------------------
    # extract
    # ------------------------------------------------------------------

    def extract(self, files: List[Path], repo_path: Path) -> LanguageResult:
        """Run JavaAnalyzer and return its LanguageResult."""
        from test_analysis.core.analyzers.java_analyzer import JavaAnalyzer

        analyzer = JavaAnalyzer()
        output_dir = repo_path / "_analysis_output"
        analyzer.analyze(repo_path, output_dir)

        result: LanguageResult = analyzer.language_result
        if result is None:
            return LanguageResult(language="java")

        self._enrich_descriptions(result)
        return result

    # ------------------------------------------------------------------
    # DB loading (language-specific tables only)
    # ------------------------------------------------------------------

    def get_table_names(self) -> List[str]:
        return ["java_reflection", "java_di_fields", "java_annotations"]

    def load_to_db(self, conn, result: LanguageResult, schema: str) -> None:
        """Write java_reflection, java_di_fields, java_annotations tables."""
        if result.java_reflection:
            self._load_java_reflection(conn, result.java_reflection, schema)
        if result.java_di_fields:
            self._load_java_di_fields(conn, result.java_di_fields, schema)
        if result.java_annotations:
            self._load_java_annotations(conn, result.java_annotations, schema)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _enrich_descriptions(self, result: LanguageResult) -> None:
        """Add .description field to each TestRecord for embedding generation."""
        try:
            from semantic.chunking.content_summarizer import summarize_test_content
        except ImportError:
            logger.debug("[java] content_summarizer not available — skipping description enrichment")
            return

        provider = os.environ.get("EMBEDDING_PROVIDER", "openai")

        for record in result.tests:
            if record.content:
                record.description = summarize_test_content(record.content, provider=provider) or record.full_name
            else:
                record.description = record.full_name

    @staticmethod
    def _load_java_reflection(conn, reflection_calls: list, schema: str) -> None:
        if not reflection_calls:
            return
        values = [
            (
                r.get("test_id", ""),
                r.get("reflection_type", ""),
                r.get("target_class"),
                r.get("target_method"),
            )
            for r in reflection_calls
        ]
        try:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {schema}.java_reflection
                        (test_id, reflection_type, target_class, target_method)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            logger.info(f"[java] Loaded {len(values)} java_reflection row(s)")
        except Exception as exc:
            conn.rollback()
            logger.error(f"[java] Failed to load java_reflection: {exc}")

    @staticmethod
    def _load_java_di_fields(conn, di_fields: list, schema: str) -> None:
        if not di_fields:
            return
        values = [
            (
                d.get("test_id", ""),
                d.get("field_name", ""),
                d.get("field_type", ""),
                d.get("annotation", ""),
            )
            for d in di_fields
        ]
        try:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {schema}.java_di_fields
                        (test_id, field_name, field_type, annotation)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            logger.info(f"[java] Loaded {len(values)} java_di_fields row(s)")
        except Exception as exc:
            conn.rollback()
            logger.error(f"[java] Failed to load java_di_fields: {exc}")

    @staticmethod
    def _load_java_annotations(conn, annotations: list, schema: str) -> None:
        if not annotations:
            return
        values = [
            (
                a.get("test_id", ""),
                a.get("annotation_name", ""),
                a.get("annotation_args"),
            )
            for a in annotations
        ]
        try:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {schema}.java_annotations
                        (test_id, annotation_name, annotation_args)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            logger.info(f"[java] Loaded {len(values)} java_annotations row(s)")
        except Exception as exc:
            conn.rollback()
            logger.error(f"[java] Failed to load java_annotations: {exc}")
