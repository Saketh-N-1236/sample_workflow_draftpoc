"""
Data models for the unified analysis pipeline.

These replace the 8 individual JSON files.  A single AnalysisResult object is
built in-memory by the engine, passed to the loader, and optionally serialised
to one consolidated analysis.json for debugging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Flat test record — one per it()/test()/def test_*/etc.
# ---------------------------------------------------------------------------

@dataclass
class TestRecord:
    """One test case extracted from the repository."""

    id: str                         # "test_0061"
    file: str                       # absolute or repo-relative path to test file
    describe: str                   # enclosing describe/class block label
    name: str                       # human-readable test name (the it()/def test_… label)
    full_name: str                  # "describe > name" composite — used as method_name in DB
    test_type: str                  # "unit" | "integration" | "e2e"
    language: str                   # "javascript" | "python" | "java"
    framework: str                  # "jest" | "pytest" | "junit" …
    sources: List[str] = field(default_factory=list)   # production source files this test covers
    symbols: List[str] = field(default_factory=list)   # production symbols (constants, functions)
    imports: List[str] = field(default_factory=list)   # raw import strings from the test file
    content: str = ""               # test body code (for smart summariser / embedding)
    description: str = ""           # smart summariser output sent to the embedding model
    line_number: Optional[int] = None
    repository_path: str = ""

    # Extra fields carried through from the analyzers (kept for compatibility)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_db_dict(self) -> Dict[str, Any]:
        """Return a dict shaped for batch_insert_test_registry."""
        return {
            "test_id": self.id,
            "file_path": self.file,
            "class_name": self.describe or None,
            "method_name": self.full_name,
            "test_type": self.test_type,
            "line_number": self.line_number,
            "language": self.language,
            "repository_path": self.repository_path,
        }


# ---------------------------------------------------------------------------
# Per-language result produced by each plugin
# ---------------------------------------------------------------------------

@dataclass
class LanguageResult:
    """All data extracted for a single language in the repository."""

    language: str
    framework: str = "unknown"
    tests: List[TestRecord] = field(default_factory=list)

    # reverse_index:  production_class → list of {test_id, file_path,
    #                 class_name, method_name, reference_type}
    reverse_index: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # function_mappings: list of {test_id, module_name, function_name,
    #                              call_type, source}
    function_mappings: List[Dict[str, Any]] = field(default_factory=list)

    # dependencies: flat list of {test_id, referenced_class, import_type}
    dependencies: List[Dict[str, Any]] = field(default_factory=list)

    # metadata: list of {test_id, description, markers, …}
    metadata: List[Dict[str, Any]] = field(default_factory=list)

    # Language-specific extras
    mocks: List[Dict[str, Any]] = field(default_factory=list)       # JS mocks / Python patches
    async_tests: List[Dict[str, Any]] = field(default_factory=list) # async test records

    # Java-specific
    java_reflection: List[Dict[str, Any]] = field(default_factory=list)
    java_di_fields: List[Dict[str, Any]] = field(default_factory=list)
    java_annotations: List[Dict[str, Any]] = field(default_factory=list)

    # Python-specific
    python_fixtures: List[Dict[str, Any]] = field(default_factory=list)
    python_decorators: List[Dict[str, Any]] = field(default_factory=list)

    # Summary stats (informational only)
    files_analyzed: int = 0
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level result aggregating all languages
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """
    Complete analysis of one test repository — all languages merged.

    This is the single in-memory object that flows from the engine to the
    loader and (optionally) to the embedding generator.  It replaces the
    8-file JSON hand-off between test_analysis/ and deterministic/.
    """

    repo_id: str = ""
    repo_path: str = ""
    detected_languages: List[str] = field(default_factory=list)
    framework: str = "unknown"

    # Per-language breakdown
    languages: Dict[str, LanguageResult] = field(default_factory=dict)

    # Aggregated views built by the Merger
    all_tests: List[TestRecord] = field(default_factory=list)

    # Merged reverse_index across all languages
    reverse_index: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # Merged function_mappings across all languages
    function_mappings: List[Dict[str, Any]] = field(default_factory=list)

    # Merged dependencies across all languages
    dependencies: List[Dict[str, Any]] = field(default_factory=list)

    # Merged metadata across all languages
    metadata: List[Dict[str, Any]] = field(default_factory=list)

    # ---------- convenience helpers ----------

    @property
    def total_tests(self) -> int:
        return len(self.all_tests)

    def get_language(self, lang: str) -> Optional[LanguageResult]:
        return self.languages.get(lang)

    def has_language(self, lang: str) -> bool:
        return lang in self.languages

    # ---------- serialisation (debug / analysis.json) ----------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (suitable for JSON output)."""
        return {
            "repo_id": self.repo_id,
            "repo_path": self.repo_path,
            "detected_languages": self.detected_languages,
            "framework": self.framework,
            "total_tests": self.total_tests,
            "tests": [
                {
                    "id": t.id,
                    "file": t.file,
                    "describe": t.describe,
                    "name": t.name,
                    "full_name": t.full_name,
                    "test_type": t.test_type,
                    "language": t.language,
                    "framework": t.framework,
                    "sources": t.sources,
                    "symbols": t.symbols,
                    "imports": t.imports,
                    "description": t.description,
                    "line_number": t.line_number,
                }
                for t in self.all_tests
            ],
            "reverse_index": {
                k: v for k, v in self.reverse_index.items()
            },
            "function_mappings": self.function_mappings,
            "language_stats": {
                lang: {
                    "framework": lr.framework,
                    "tests_found": len(lr.tests),
                    "files_analyzed": lr.files_analyzed,
                    "errors": lr.errors,
                }
                for lang, lr in self.languages.items()
            },
        }

    def write_consolidated_json(self, output_dir: Path) -> Path:
        """Write one analysis.json file for debugging. Returns the path written."""
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "analysis.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return path
