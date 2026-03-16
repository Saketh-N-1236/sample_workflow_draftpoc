"""
Language parser registry - dynamically loads and manages parsers.

This module provides a registry pattern for language parsers,
allowing dynamic discovery and loading of parsers based on file extensions.
"""

from typing import Dict, Optional, List
from pathlib import Path
from parsers.base import LanguageParser
import importlib
import sys


class ParserRegistry:
    """
    Registry for language parsers.
    
    Maintains a mapping of file extensions to parsers and provides
    factory methods to get appropriate parsers for files.
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._parsers: Dict[str, LanguageParser] = {}
        self._extensions: Dict[str, str] = {}  # .py -> python
    
    def register(self, parser: LanguageParser):
        """
        Register a language parser.
        
        Args:
            parser: LanguageParser instance to register
        """
        language = parser.language_name
        self._parsers[language] = parser
        
        # Map all extensions to this language
        for ext in parser.file_extensions:
            ext_lower = ext.lower()
            if ext_lower not in self._extensions:
                self._extensions[ext_lower] = language
            else:
                # Extension already mapped - warn but allow override
                existing_lang = self._extensions[ext_lower]
                if existing_lang != language:
                    print(f"Warning: Extension {ext} already mapped to {existing_lang}, "
                          f"overriding with {language}")
                    self._extensions[ext_lower] = language
    
    def get_parser(self, filepath: Path) -> Optional[LanguageParser]:
        """
        Get appropriate parser for file based on extension.
        
        Args:
            filepath: Path to the file
            
        Returns:
            LanguageParser instance, or None if no parser found
        """
        ext = filepath.suffix.lower()
        language = self._extensions.get(ext)
        if language:
            return self._parsers.get(language)
        return None
    
    def detect_language(self, filepath: Path) -> Optional[str]:
        """
        Detect language from file extension.
        
        Args:
            filepath: Path to the file
            
        Returns:
            Language name, or None if unknown
        """
        ext = filepath.suffix.lower()
        return self._extensions.get(ext)
    
    def get_all_languages(self) -> List[str]:
        """
        Get list of all registered languages.
        
        Returns:
            List of language names
        """
        return list(self._parsers.keys())
    
    def load_from_config(self, config: Dict):
        """
        Load Tree-sitter parsers from language configuration dictionary.
        
        Args:
            config: Dictionary with 'languages' key containing language configs
        """
        languages_config = config.get('languages', {})
        
        for lang_name, lang_config in languages_config.items():
            # Skip if already registered
            if lang_name in self._parsers:
                continue
            
            # Use Tree-sitter factory instead of manual parser classes
            try:
                from parsers.tree_sitter_factory import get_tree_sitter_parser
                
                # Get file extensions from config
                extensions = lang_config.get('extensions', [])
                if not extensions:
                    print(f"Warning: No extensions specified for {lang_name}, skipping")
                    continue
                
                # Create Tree-sitter parser
                parser = get_tree_sitter_parser(lang_name, extensions)
                if parser:
                    self.register(parser)
                    print(f"Registered Tree-sitter parser for {lang_name}")
                else:
                    # Only warn for typescript once (it's optional)
                    if lang_name == 'typescript':
                        if not hasattr(self, '_typescript_warned'):
                            print(f"Warning: Tree-sitter parser for {lang_name} is not available. "
                                  f"Install tree-sitter-{lang_name} package.")
                            self._typescript_warned = True
                    else:
                        print(f"Warning: Tree-sitter parser for {lang_name} is not available. "
                              f"Install tree-sitter-{lang_name} package.")
                
            except ImportError as e:
                print(f"Warning: Could not import Tree-sitter factory for {lang_name}: {e}")
            except Exception as e:
                print(f"Warning: Error loading Tree-sitter parser for {lang_name}: {e}")


# Global registry instance
_registry = ParserRegistry()


def get_parser(filepath: Path) -> Optional[LanguageParser]:
    """
    Get parser for file (convenience function).
    
    Args:
        filepath: Path to the file
        
    Returns:
        LanguageParser instance, or None
    """
    return _registry.get_parser(filepath)


def register_parser(parser: LanguageParser):
    """
    Register a parser (convenience function).
    
    Args:
        parser: LanguageParser instance
    """
    _registry.register(parser)


def detect_language(filepath: Path) -> Optional[str]:
    """
    Detect language from file (convenience function).
    
    Args:
        filepath: Path to the file
        
    Returns:
        Language name, or None
    """
    return _registry.detect_language(filepath)


def initialize_registry(config_path: Path = None):
    """
    Initialize registry from config file or with default parsers.
    
    Args:
        config_path: Optional path to language config YAML file
    """
    if config_path and config_path.exists():
        try:
            from config.config_loader import load_language_configs
            config = load_language_configs(config_path)
            _registry.load_from_config(config)
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
            print("Falling back to default Python parser")
            _register_default_parsers()
    else:
        # Default: register Python parser
        _register_default_parsers()


def _register_default_parsers():
    """Register Tree-sitter parsers for all supported languages (Tree-sitter only)."""
    try:
        from parsers.tree_sitter_factory import get_tree_sitter_parser
        
        # Register Tree-sitter parsers for supported languages
        languages = [
            ('python', ['.py']),
            ('javascript', ['.js', '.jsx']),
            ('java', ['.java']),
            ('typescript', ['.ts', '.tsx'])
        ]
        
        for lang_name, extensions in languages:
            try:
                parser = get_tree_sitter_parser(lang_name, extensions)
                if parser:
                    _registry.register(parser)
                    print(f"Registered Tree-sitter parser for {lang_name}")
                else:
                    print(f"Warning: Tree-sitter parser for {lang_name} is not available. "
                          f"Install tree-sitter-{lang_name} package.")
            except Exception as e:
                print(f"Warning: Could not register Tree-sitter parser for {lang_name}: {e}")
    except ImportError as e:
        print(f"Warning: Tree-sitter not available: {e}")
        print("Please install tree-sitter and language-specific packages:")
        print("  pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-java tree-sitter-typescript")


def get_registry() -> ParserRegistry:
    """
    Get the global registry instance.
    
    Returns:
        ParserRegistry instance
    """
    return _registry
