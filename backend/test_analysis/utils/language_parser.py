"""
Language-agnostic parser utility.

Provides a unified interface for parsing files regardless of language.
Automatically selects the appropriate parser based on file extension.
"""

from pathlib import Path
from typing import Optional, Dict, List, Any
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from parsers.registry import get_parser, initialize_registry
    from config.config_loader import load_language_configs
    PARSER_REGISTRY_AVAILABLE = True
except ImportError:
    PARSER_REGISTRY_AVAILABLE = False

# Try to use Tree-sitter if available
try:
    from parsers.tree_sitter_parser import TreeSitterParser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

# Fallback to Python parser
try:
    from utils.ast_parser import (
        parse_file as parse_python_file,
        extract_test_classes as extract_python_test_classes,
        extract_test_methods as extract_python_test_methods,
        extract_imports as extract_python_imports,
        extract_string_references as extract_python_string_references,
        extract_function_calls as extract_python_function_calls
    )
except ImportError:
    # If ast_parser not available, create stub functions
    def parse_python_file(*args, **kwargs):
        return None
    def extract_python_test_classes(*args, **kwargs):
        return []
    def extract_python_test_methods(*args, **kwargs):
        return []
    def extract_python_imports(*args, **kwargs):
        return {'imports': [], 'from_imports': [], 'all_imports': []}
    def extract_python_string_references(*args, **kwargs):
        return []
    def extract_python_function_calls(*args, **kwargs):
        return []


def _initialize_parser_registry():
    """Initialize parser registry if not already done."""
    if not PARSER_REGISTRY_AVAILABLE:
        return False
    
    try:
        config_path = project_root / "config" / "language_configs.yaml"
        if config_path.exists():
            initialize_registry(config_path)
            return True
    except Exception:
        pass
    
    return False


def parse_file(filepath: Path) -> Optional[Any]:
    """
    Parse a file using the appropriate language parser.
    
    Args:
        filepath: Path to the file to parse
    
    Returns:
        Language-specific AST or None if parsing fails
    """
    _initialize_parser_registry()
    
    if PARSER_REGISTRY_AVAILABLE:
        parser = get_parser(filepath)
        if parser:
            try:
                return parser.parse_file(filepath)
            except Exception as e:
                print(f"Warning: Could not parse {filepath} with {parser.language_name} parser: {e}")
                return None
    
    # Fallback to Python parser
    if filepath.suffix == '.py':
        return parse_python_file(filepath)
    
    return None


def extract_test_methods(ast: Any, filepath: Path) -> List[Dict[str, Any]]:
    """
    Extract test methods from AST using appropriate parser.
    
    Args:
        ast: Language-specific AST
        filepath: Path to the file (for parser detection)
    
    Returns:
        List of test method dictionaries
    """
    _initialize_parser_registry()
    
    if PARSER_REGISTRY_AVAILABLE:
        parser = get_parser(filepath)
        if parser and ast:
            try:
                return parser.extract_test_methods(ast)
            except Exception:
                pass
    
    # Fallback to Python parser
    if filepath.suffix == '.py' and ast:
        return extract_python_test_methods(ast)
    
    return []


def extract_test_classes(ast: Any, filepath: Path) -> List[Dict[str, Any]]:
    """
    Extract test classes from AST using appropriate parser.
    
    Args:
        ast: Language-specific AST
        filepath: Path to the file (for parser detection)
    
    Returns:
        List of test class dictionaries
    """
    _initialize_parser_registry()
    
    if PARSER_REGISTRY_AVAILABLE:
        parser = get_parser(filepath)
        if parser and ast:
            try:
                return parser.extract_classes(ast)
            except Exception:
                pass
    
    # Fallback to Python parser
    if filepath.suffix == '.py' and ast:
        return extract_python_test_classes(ast)
    
    return []


def extract_imports(ast: Any, filepath: Path) -> Dict[str, List[str]]:
    """
    Extract imports from AST using appropriate parser.
    
    Args:
        ast: Language-specific AST
        filepath: Path to the file (for parser detection)
    
    Returns:
        Dictionary with 'imports', 'from_imports', 'all_imports'
    """
    _initialize_parser_registry()
    
    if PARSER_REGISTRY_AVAILABLE:
        parser = get_parser(filepath)
        if parser and ast:
            try:
                return parser.extract_imports(ast)
            except Exception:
                pass
    
    # Fallback to Python parser
    if filepath.suffix == '.py' and ast:
        return extract_python_imports(ast)
    
    return {'imports': [], 'from_imports': [], 'all_imports': []}


def extract_string_references(ast: Any, filepath: Path) -> List[str]:
    """
    Extract string-based references from AST using appropriate parser.
    
    Args:
        ast: Language-specific AST
        filepath: Path to the file (for parser detection)
    
    Returns:
        List of module/class names found in string literals
    """
    _initialize_parser_registry()
    
    if PARSER_REGISTRY_AVAILABLE:
        parser = get_parser(filepath)
        if parser and ast:
            try:
                return parser.extract_string_references(ast)
            except Exception:
                pass
    
    # Fallback to Python parser
    if filepath.suffix == '.py' and ast:
        return extract_python_string_references(ast)
    
    return []


def extract_function_calls(ast: Any, filepath: Path) -> List[Dict[str, Any]]:
    """
    Extract function calls from AST using appropriate parser.
    
    Args:
        ast: Language-specific AST
        filepath: Path to the file (for parser detection)
    
    Returns:
        List of function call dictionaries
    """
    _initialize_parser_registry()
    
    if PARSER_REGISTRY_AVAILABLE:
        parser = get_parser(filepath)
        if parser and ast:
            try:
                return parser.extract_function_calls(ast)
            except Exception:
                pass
    
    # Fallback to Python parser
    if filepath.suffix == '.py' and ast:
        return extract_python_function_calls(ast)
    
    return []
