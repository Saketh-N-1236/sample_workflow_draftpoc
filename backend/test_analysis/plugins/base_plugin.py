"""
LanguagePlugin — abstract interface that every language plugin must implement.

Each plugin is responsible for the full lifecycle of one language:
  1. scan()       — find test files in the repo
  2. extract()    — Tree-sitter AST parse + domain enrichment → LanguageResult
  3. load_to_db() — write the language-specific DB tables

Adding a new language = creating one folder with one plugin.py that
implements this interface.  No central if/else lists needed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
import logging

from test_analysis.engine.models import LanguageResult

logger = logging.getLogger(__name__)


class LanguagePlugin(ABC):
    """
    Abstract base for all language plugins.

    Concrete implementations live in:
      plugins/javascript, python, java, native (C/C++).
    """

    # ── subclasses must set these class-level attributes ──────────────────
    language: str = ""              # "javascript" | "python" | "java"
    file_patterns: List[str] = []   # ["*.test.js", "*.spec.ts"]
    # ──────────────────────────────────────────────────────────────────────

    @abstractmethod
    def scan(self, repo_path: Path) -> List[Path]:
        """
        Return the list of test files found in repo_path for this language.
        Return an empty list if no files are found (the engine will skip this plugin).
        """

    @abstractmethod
    def extract(self, files: List[Path], repo_path: Path) -> LanguageResult:
        """
        Parse the given test files with Tree-sitter + language-specific enrichment
        and return a fully-populated LanguageResult.

        This method must NOT write any files to disk.
        """

    @abstractmethod
    def get_table_names(self) -> List[str]:
        """
        Return the list of DB table names that this language needs.
        Used by the schema builder to decide which tables to create.
        Example: ["js_mocks", "js_async_tests"]
        """

    @abstractmethod
    def load_to_db(self, conn, result: LanguageResult, schema: str) -> None:
        """
        Write the language-specific sections of result to PostgreSQL.
        Core tables (test_registry, reverse_index, …) are written by loader.py
        before this method is called — write ONLY the language-specific tables here.
        """

    # ── helpers available to all subclasses ───────────────────────────────

    def _log(self, msg: str) -> None:
        logger.info(f"[{self.language}] {msg}")

    def _log_warn(self, msg: str) -> None:
        logger.warning(f"[{self.language}] {msg}")


# ---------------------------------------------------------------------------
# Plugin registry
# ---------------------------------------------------------------------------

class PluginRegistry:
    """
    Holds one plugin per language.  Plugins are registered at import time.
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, LanguagePlugin] = {}

    def register(self, plugin: LanguagePlugin) -> None:
        self._plugins[plugin.language] = plugin
        logger.debug(f"[PluginRegistry] registered plugin for '{plugin.language}'")

    def get(self, language: str) -> Optional[LanguagePlugin]:
        return self._plugins.get(language)

    def all_plugins(self) -> List[LanguagePlugin]:
        return list(self._plugins.values())

    def registered_languages(self) -> List[str]:
        return list(self._plugins.keys())


# ---------------------------------------------------------------------------
# Singleton registry — populated in get_plugin_registry()
# ---------------------------------------------------------------------------

_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """
    Return the global PluginRegistry, building it on first call.
    Plugins are imported lazily so missing optional dependencies (e.g. javalang)
    do not break the JS or Python paths.
    """
    global _registry
    if _registry is not None:
        return _registry

    _registry = PluginRegistry()

    # --- JavaScript / TypeScript ---
    try:
        from test_analysis.plugins.javascript.plugin import JavaScriptPlugin
        _registry.register(JavaScriptPlugin())
    except Exception as exc:
        logger.warning(f"[PluginRegistry] Could not load JavaScriptPlugin: {exc}")

    # --- Python ---
    try:
        from test_analysis.plugins.python.plugin import PythonPlugin
        _registry.register(PythonPlugin())
    except Exception as exc:
        logger.warning(f"[PluginRegistry] Could not load PythonPlugin: {exc}")

    # --- Java ---
    try:
        from test_analysis.plugins.java.plugin import JavaPlugin
        _registry.register(JavaPlugin())
    except Exception as exc:
        logger.warning(f"[PluginRegistry] Could not load JavaPlugin: {exc}")

    try:
        from test_analysis.plugins.native.plugin import CPlugin, CppPlugin
        _registry.register(CPlugin())
        _registry.register(CppPlugin())
    except Exception as exc:
        logger.warning(f"[PluginRegistry] Could not load C/C++ plugins: {exc}")

    return _registry
