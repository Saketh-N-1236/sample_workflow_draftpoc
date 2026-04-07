"""
C and C++ language plugins — UniversalTestParser (Tree-sitter + GTest regex).

No extra DB tables; core test_registry / dependencies only.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

from test_analysis.engine.models import LanguageResult, TestRecord
from test_analysis.plugins.base_plugin import LanguagePlugin
from test_analysis.utils.universal_parser import UniversalTestParser

logger = logging.getLogger(__name__)

_EXCLUDE_DIRS = {
    "node_modules", ".git", "target", "build", ".gradle", ".mvn",
    "bin", "out", ".idea", "__pycache__", ".venv", "venv",
}

_C_EXT = {".c", ".h"}
_CPP_EXT = {".cpp", ".cc", ".cxx", ".hpp", ".hh"}

_C_TEST_NAME = re.compile(
    r"^(test_.+\.c|.+_test\.c|.+_tests\.c)$", re.IGNORECASE
)
_CPP_TEST_NAME = re.compile(
    r"^(.+_test\.(cpp|cc|cxx)|test_.+\.(cpp|cc|cxx)|.+Test\.(cpp|cc|cxx)|.+Tests\.(cpp|cc|cxx))$",
    re.IGNORECASE,
)


def _test_type(path: Path) -> str:
    s = str(path).lower()
    if "integration" in s:
        return "integration"
    if "e2e" in s:
        return "e2e"
    return "unit"


class CPlugin(LanguagePlugin):
    language = "c"
    file_patterns = ["test_*.c", "*_test.c"]

    def scan(self, repo_path: Path) -> List[Path]:
        found = []
        for fp in repo_path.rglob("*"):
            if not fp.is_file():
                continue
            if any(x in fp.parts for x in _EXCLUDE_DIRS):
                continue
            if fp.suffix.lower() not in _C_EXT:
                continue
            if _C_TEST_NAME.match(fp.name):
                found.append(fp)
        return sorted(found)

    def extract(self, files: List[Path], repo_path: Path) -> LanguageResult:
        return _extract_native(files, repo_path, "c")

    def get_table_names(self) -> List[str]:
        return []

    def load_to_db(self, conn, result: LanguageResult, schema: str) -> None:
        pass


class CppPlugin(LanguagePlugin):
    language = "cpp"
    file_patterns = ["*_test.cpp", "test_*.cpp", "*Test.cpp"]

    def scan(self, repo_path: Path) -> List[Path]:
        found = []
        for fp in repo_path.rglob("*"):
            if not fp.is_file():
                continue
            if any(x in fp.parts for x in _EXCLUDE_DIRS):
                continue
            if fp.suffix.lower() not in _CPP_EXT:
                continue
            if _CPP_TEST_NAME.match(fp.name):
                found.append(fp)
        return sorted(found)

    def extract(self, files: List[Path], repo_path: Path) -> LanguageResult:
        return _extract_native(files, repo_path, "cpp")

    def get_table_names(self) -> List[str]:
        return []

    def load_to_db(self, conn, result: LanguageResult, schema: str) -> None:
        pass


def _extract_native(
    files: List[Path], repo_path: Path, default_lang: str
) -> LanguageResult:
    parser = UniversalTestParser()
    tests: List[TestRecord] = []
    dependencies: List[dict] = []
    reverse_index: dict = {}
    metadata: List[dict] = []
    repo_s = str(repo_path.resolve())
    tid = 0

    for fp in files:
        fp = fp.resolve()
        try:
            parsed = parser.parse_file(fp)
        except Exception as e:
            logger.debug("[%s] parse %s: %s", default_lang, fp, e)
            continue
        if parsed.get("error"):
            continue
        lang = parsed.get("language") or default_lang
        fw = parsed.get("framework") or "gtest"
        methods = parsed.get("test_methods") or []
        if not methods:
            continue

        imports = parsed.get("imports") or []
        for m in methods:
            tid += 1
            test_id = f"test_{tid:04d}"
            suite = m.get("class_name") or ""
            name = m.get("name") or "case"
            full = f"{suite}::{name}" if suite else name
            tests.append(
                TestRecord(
                    id=test_id,
                    file=str(fp),
                    describe=suite or "",
                    name=name,
                    full_name=full,
                    test_type=_test_type(fp),
                    language=lang,
                    framework=fw,
                    imports=list(imports),
                    line_number=m.get("line_number"),
                    repository_path=repo_s,
                    extra={"parse_method": parsed.get("parse_method", "")},
                )
            )
            for imp in imports:
                sym = imp.split("/")[-1].replace(".h", "").strip("<>\"")
                if sym and len(sym) < 256:
                    reverse_index.setdefault(sym, []).append(
                        {
                            "test_id": test_id,
                            "file_path": str(fp),
                            "class_name": suite or None,
                            "method_name": full,
                            "reference_type": "include",
                        }
                    )
                    dependencies.append(
                        {
                            "test_id": test_id,
                            "referenced_class": sym,
                            "import_type": "include",
                        }
                    )
            metadata.append(
                {
                    "test_id": test_id,
                    "description": full,
                    "markers": [],
                    "framework": fw,
                }
            )

    framework = "gtest" if tests else "unknown"
    return LanguageResult(
        language=default_lang,
        framework=framework,
        tests=tests,
        reverse_index=reverse_index,
        dependencies=dependencies,
        metadata=metadata,
        files_analyzed=len(files),
    )
