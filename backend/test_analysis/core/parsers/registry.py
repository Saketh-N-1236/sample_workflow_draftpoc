"""
Unified parser registry.

Consolidates universal_parser, language_parser, and ast_parser functionality.
"""

from pathlib import Path
from typing import Dict, Optional, Union
import logging

# Import existing universal parser
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from test_analysis.utils.universal_parser import UniversalTestParser, detect_language

logger = logging.getLogger(__name__)

# Extensions treated as production source for diff-based selection (align with diff_parser.is_production_file)
_PRODUCTION_SUFFIXES = frozenset(
    {
        ".py",
        ".java",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".kt",
        ".go",
        ".rb",
        ".cs",
        ".c",
        ".h",
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".hh",
    }
)


class _DiffParserAdapter:
    """
    Minimal surface expected by deterministic.parsing.diff_parser:
    language_name, resolve_module_name(filepath, project_root).
    """

    __slots__ = ("language_name",)

    def __init__(self, language_name: str) -> None:
        self.language_name = language_name

    def resolve_module_name(
        self,
        filepath: Union[str, Path],
        project_root: Optional[Union[str, Path]],
    ) -> str:
        fp = Path(filepath)
        if project_root:
            pr = Path(project_root)
            try:
                candidate = fp if fp.is_absolute() else (pr / fp)
                rel = candidate.resolve().relative_to(pr.resolve())
                base = rel.with_suffix("")
            except (ValueError, OSError):
                base = fp.with_suffix("")
        else:
            base = fp.with_suffix("")
        return str(base).replace("\\", "/").replace("/", ".")


class ParserRegistry:
    """
    Unified parser registry.
    
    Consolidates Tree-sitter and regex fallback parsing.
    Replaces the need for separate universal_parser, language_parser, and ast_parser modules.
    """
    
    def __init__(self):
        """Initialize parser registry."""
        self._parser = UniversalTestParser()
        self._cache: Dict[str, Dict] = {}
    
    def parse_file(self, filepath: Path) -> Dict:
        """
        Parse a file using the universal parser.
        
        Args:
            filepath: Path to file to parse
            
        Returns:
            Dictionary with parsed information:
            {
                'filepath': str,
                'language': str,
                'test_methods': List[Dict],
                'test_classes': List[str],
                'imports': List[str],
                'framework': str,
                'parse_method': str,
                'error': Optional[str],
            }
        """
        filepath = Path(filepath).resolve()
        cache_key = str(filepath)
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Parse using universal parser
        result = self._parser.parse_file(filepath)
        
        # Cache result
        self._cache[cache_key] = result
        
        return result
    
    def detect_language(self, filepath: Path) -> str:
        """
        Detect language from file extension.

        Args:
            filepath: Path to file

        Returns:
            Language name or 'unknown'
        """
        return detect_language(filepath)

    def get_parser(self, filepath: Union[str, Path]) -> Optional[_DiffParserAdapter]:
        """
        Return a lightweight parser view for diff / module resolution.

        ``deterministic.parsing.diff_parser`` calls ``get_parser`` and expects
        ``language_name`` plus ``resolve_module_name``. The full Tree-sitter
        stack is not required for that path.
        """
        fp = Path(filepath)
        if fp.suffix.lower() not in _PRODUCTION_SUFFIXES:
            return None
        lang = self.detect_language(fp)
        if lang == "unknown":
            return None
        return _DiffParserAdapter(lang)

    def clear_cache(self):
        """Clear parser cache."""
        self._cache.clear()


# Global registry instance
_registry: Optional[ParserRegistry] = None


def get_parser_registry() -> ParserRegistry:
    """Get global parser registry instance."""
    global _registry
    if _registry is None:
        _registry = ParserRegistry()
    return _registry
