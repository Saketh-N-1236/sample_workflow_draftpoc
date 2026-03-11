"""
Unified parser registry.

Consolidates Tree-sitter and regex fallback parsing.
"""

from .registry import ParserRegistry, get_parser_registry

__all__ = [
    'ParserRegistry',
    'get_parser_registry',
]
