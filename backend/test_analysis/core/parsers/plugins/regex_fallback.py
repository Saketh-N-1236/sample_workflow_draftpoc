"""
Regex / pattern-based parse plugin (fallback when Tree-sitter returns no tests).
"""

from pathlib import Path
from typing import Any, Dict


def regex_fallback_parse(
    universal_parser: Any,
    content: str,
    language: str,
    filepath: Path,
) -> Dict:
    """Delegate to UniversalTestParser._parse_with_regex."""
    return universal_parser._parse_with_regex(content, language, filepath)
