"""
Language parser package for multi-language support.

This package provides:
- Abstract LanguageParser interface
- Parser registry for dynamic loading
- Language-specific parser implementations
"""

from parsers.registry import get_parser, register_parser, initialize_registry, detect_language, ParserRegistry

__all__ = [
    'get_parser',
    'register_parser',
    'initialize_registry',
    'detect_language',
    'ParserRegistry',
]
