"""
RepoAnalyzer — top-level engine that drives the full analysis pipeline.

Flow:
    STAGE 1  detect_languages()   — infer languages from file extensions
    STAGE 2  Plugin registry      — select plugins for detected languages only
    STAGE 3  plugin.scan()        — find test files per language
    STAGE 4  plugin.extract()     — Tree-sitter AST + domain enrichment → LanguageResult
    STAGE 5  Merger.merge()       — combine all LanguageResults → AnalysisResult

The AnalysisResult is returned to the caller (analysis_service.py) which then
calls loader.load_to_db() and the embedding generator.

No subprocesses, no disk I/O unless DEBUG_WRITE_JSON=true.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from test_analysis.engine.models import AnalysisResult, LanguageResult, TestRecord
from test_analysis.plugins.base_plugin import LanguagePlugin, get_plugin_registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_LANG_EXTENSIONS: Dict[str, List[str]] = {
    "javascript": [".js", ".ts", ".jsx", ".tsx"],
    "python":     [".py"],
    "java":       [".java"],
    "c":          [".c", ".h"],
    "cpp":        [".cpp", ".cc", ".cxx", ".hpp", ".hh"],
}

_EXCLUDE_DIRS = {
    "node_modules", ".git", "venv", ".venv", "__pycache__",
    "target", "build", "dist", ".gradle", ".mvn", "bin", "out",
}


def detect_languages(repo_path: Path) -> List[str]:
    """
    Walk repo_path and vote for languages by file-extension frequency.
    Returns a sorted list of detected language names (most common first).
    """
    votes: Dict[str, int] = defaultdict(int)
    for fp in repo_path.rglob("*"):
        if not fp.is_file():
            continue
        if any(ex in fp.parts for ex in _EXCLUDE_DIRS):
            continue
        suffix = fp.suffix.lower()
        for lang, exts in _LANG_EXTENSIONS.items():
            if suffix in exts:
                votes[lang] += 1

    detected = sorted(votes, key=lambda l: votes[l], reverse=True)
    logger.info(f"[engine] Detected languages: {detected} (votes={dict(votes)})")
    return detected


# ---------------------------------------------------------------------------
# Merger
# ---------------------------------------------------------------------------

class Merger:
    """Combines per-language LanguageResults into one AnalysisResult."""

    def merge(
        self,
        lang_results: Dict[str, LanguageResult],
        repo_path: Path,
        repo_id: str = "",
    ) -> AnalysisResult:
        all_tests: List[TestRecord] = []
        merged_reverse_index: Dict = defaultdict(list)
        merged_function_mappings: List = []
        merged_dependencies: List = []
        merged_metadata: List = []

        primary_framework = "unknown"

        for lang, lr in lang_results.items():
            all_tests.extend(lr.tests)

            # Merge reverse index — union of all language entries
            for symbol, entries in lr.reverse_index.items():
                merged_reverse_index[symbol].extend(entries)

            merged_function_mappings.extend(lr.function_mappings)
            merged_dependencies.extend(lr.dependencies)
            merged_metadata.extend(lr.metadata)

            if lr.framework not in ("unknown", ""):
                primary_framework = lr.framework

        detected_languages = list(lang_results.keys())

        result = AnalysisResult(
            repo_id=repo_id,
            repo_path=str(repo_path),
            detected_languages=detected_languages,
            framework=primary_framework,
            languages=lang_results,
            all_tests=all_tests,
            reverse_index=dict(merged_reverse_index),
            function_mappings=merged_function_mappings,
            dependencies=merged_dependencies,
            metadata=merged_metadata,
        )

        logger.info(
            f"[engine] Merge complete — {result.total_tests} test(s) "
            f"from {detected_languages}"
        )
        return result


# ---------------------------------------------------------------------------
# RepoAnalyzer — main public API
# ---------------------------------------------------------------------------

class RepoAnalyzer:
    """
    Orchestrates the full analysis pipeline for one repository.

    Usage::

        analyzer = RepoAnalyzer()
        result = analyzer.analyze(repo_path, schema_name="my_schema")
        # result is an AnalysisResult — pass it to loader.load_to_db()
    """

    def __init__(self) -> None:
        self._registry = get_plugin_registry()

    def analyze(
        self,
        repo_path: Path,
        schema_name: str = "",
        repo_id: str = "",
        progress_callback=None,
    ) -> AnalysisResult:
        """
        Run the full analysis pipeline.

        Args:
            repo_path:         Absolute path to the extracted repository.
            schema_name:       PostgreSQL schema name (informational; stored in AnalysisResult).
            repo_id:           Optional repository UUID (stored in AnalysisResult).
            progress_callback: Optional callable(message: str) for streaming progress.

        Returns:
            AnalysisResult ready for loader.load_to_db() and embedding generation.
        """
        repo_path = Path(repo_path).resolve()
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository path not found: {repo_path}")

        def _progress(msg: str) -> None:
            logger.info(f"[engine] {msg}")
            if progress_callback:
                try:
                    progress_callback(msg)
                except Exception:
                    pass

        # STAGE 1: Detect languages
        _progress("STAGE 1 — detecting languages")
        detected = detect_languages(repo_path)
        if not detected:
            logger.warning("[engine] No source files detected — returning empty result")
            return AnalysisResult(
                repo_id=repo_id,
                repo_path=str(repo_path),
            )

        # STAGE 2: Select plugins
        lang_results: Dict[str, LanguageResult] = {}
        for lang in detected:
            plugin: Optional[LanguagePlugin] = self._registry.get(lang)
            if plugin is None:
                logger.debug(f"[engine] No plugin registered for '{lang}' — skipping")
                continue

            # STAGE 3: Scan test files
            _progress(f"STAGE 3 — scanning {lang} test files")
            files = plugin.scan(repo_path)
            if not files:
                logger.info(f"[engine] No {lang} test files found — skipping plugin")
                continue

            _progress(f"STAGE 4 — extracting {lang} ({len(files)} file(s))")

            # STAGE 4: Extract
            try:
                lr = plugin.extract(files, repo_path)
                if lr and lr.tests:
                    lang_results[lang] = lr
                    _progress(f"[OK] {lang}: {len(lr.tests)} test(s) extracted")
                else:
                    logger.warning(f"[engine] Plugin '{lang}' returned no tests")
            except Exception as exc:
                logger.error(f"[engine] Plugin '{lang}' raised exception: {exc}", exc_info=True)

        if not lang_results:
            logger.warning("[engine] No tests extracted from any language")
            return AnalysisResult(
                repo_id=repo_id,
                repo_path=str(repo_path),
                detected_languages=detected,
            )

        # STAGE 5: Merge
        _progress("STAGE 5 — merging results")
        result = Merger().merge(lang_results, repo_path, repo_id=repo_id)

        return result
