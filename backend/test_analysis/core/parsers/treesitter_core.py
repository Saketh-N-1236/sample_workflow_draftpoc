"""
Tree-sitter grammar registry (primary AST path).
Languages: Python, Java, JavaScript, TypeScript/TSX, C, C++ (best-effort).
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_parsers: Dict[str, Any] = {}


def _try_load_parser(lang_key: str, loader) -> None:
    global _parsers
    try:
        from tree_sitter import Language, Parser
        parser = Parser(Language(loader()))
        _parsers[lang_key] = parser
        logger.info(f"Tree-sitter grammar ready: {lang_key}")
    except Exception as e:
        logger.debug(f"Tree-sitter unavailable for {lang_key}: {e}")


def load_all_treesitter_parsers() -> Dict[str, Any]:
    """Idempotent load of all supported grammars."""
    global _parsers
    if _parsers:
        return _parsers

    try:
        from tree_sitter import Language, Parser  # noqa: F401
    except ImportError:
        logger.warning("tree_sitter not installed")
        return _parsers

    mods = [
        ("python", lambda: importlib.import_module("tree_sitter_python").language()),
        ("java", lambda: importlib.import_module("tree_sitter_java").language()),
        ("javascript", lambda: importlib.import_module("tree_sitter_javascript").language()),
    ]
    for key, loader in mods:
        _try_load_parser(key, loader)

    try:
        tst = importlib.import_module("tree_sitter_typescript")
        _try_load_parser("typescript", lambda: tst.language_typescript())
        _try_load_parser("tsx", lambda: tst.language_tsx())
    except Exception as e:
        logger.debug(f"tree_sitter_typescript: {e}")

    try:
        _try_load_parser("c", lambda: importlib.import_module("tree_sitter_c").language())
    except Exception:
        pass

    try:
        _try_load_parser("cpp", lambda: importlib.import_module("tree_sitter_cpp").language())
    except Exception:
        pass

    return _parsers


def get_treesitter_parsers() -> Dict[str, Any]:
    return load_all_treesitter_parsers()
