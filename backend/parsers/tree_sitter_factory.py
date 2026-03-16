"""
Factory for creating Tree-sitter parsers.

Automatically creates Tree-sitter parsers for supported languages.
"""

from pathlib import Path
from typing import Optional, Dict
import sys

try:
    from parsers.tree_sitter_parser import TreeSitterParser, TREE_SITTER_AVAILABLE
except ImportError:
    TREE_SITTER_AVAILABLE = False
    TreeSitterParser = None


def create_tree_sitter_parser(language_name: str, file_extensions: list) -> Optional[TreeSitterParser]:
    """
    Create a Tree-sitter parser for a language.
    
    Args:
        language_name: Language name (e.g., 'python', 'javascript', 'java')
        file_extensions: List of file extensions (e.g., ['.py'], ['.js', '.jsx'])
    
    Returns:
        TreeSitterParser instance, or None if Tree-sitter is not available
    """
    if not TREE_SITTER_AVAILABLE or TreeSitterParser is None:
        return None
    
    try:
        parser = TreeSitterParser(language_name, file_extensions)
        # Check if parser was successfully initialized
        if parser._parser is not None:
            return parser
    except Exception as e:
        print(f"Warning: Could not create Tree-sitter parser for {language_name}: {e}")
    
    return None


def get_tree_sitter_parser(language_name: str, file_extensions: list) -> Optional[TreeSitterParser]:
    """
    Get a Tree-sitter parser for a specific language (convenience function for registry).
    
    Args:
        language_name: Language name (e.g., 'python', 'javascript', 'java')
        file_extensions: List of file extensions (e.g., ['.py'], ['.js', '.jsx'])
    
    Returns:
        TreeSitterParser instance, or None if not available
    """
    return create_tree_sitter_parser(language_name, file_extensions)


def get_tree_sitter_parsers() -> Dict[str, TreeSitterParser]:
    """
    Get Tree-sitter parsers for all supported languages.
    
    Returns:
        Dictionary mapping language names to TreeSitterParser instances
    """
    parsers = {}
    
    if not TREE_SITTER_AVAILABLE:
        return parsers
    
    # Supported languages with their extensions
    languages = {
        'python': ['.py'],
        'javascript': ['.js', '.jsx'],
        'java': ['.java'],
        'typescript': ['.ts', '.tsx'],
    }
    
    for lang_name, extensions in languages.items():
        parser = create_tree_sitter_parser(lang_name, extensions)
        if parser:
            parsers[lang_name] = parser
    
    return parsers
