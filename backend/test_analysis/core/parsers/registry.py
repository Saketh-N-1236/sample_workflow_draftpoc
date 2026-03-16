"""
Unified parser registry.

Consolidates universal_parser, language_parser, and ast_parser functionality.
"""

from pathlib import Path
from typing import Dict, Optional
import logging

# Import existing universal parser
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from test_analysis.utils.universal_parser import UniversalTestParser, detect_language

logger = logging.getLogger(__name__)


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
