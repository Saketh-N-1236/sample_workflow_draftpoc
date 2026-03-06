"""
AST (Abstract Syntax Tree) parsing utilities.

This module provides functions to:
- Parse Python files into AST
- Extract imports and dependencies
- Extract class and method definitions
- Extract test-related information from AST nodes

NOTE: This module now uses Tree-sitter parsers via the registry.
All functions are maintained for backward compatibility.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from parsers.registry import get_parser, initialize_registry

# Initialize registry and get parser for Python files
initialize_registry()
_parser = None  # Will be lazily initialized


def _ensure_parser_initialized():
    """Ensure parser is initialized. Initialize if None."""
    global _parser
    if _parser is None:
        # Try to get Python parser from registry
        from pathlib import Path
        dummy_path = Path('dummy.py')
        _parser = get_parser(dummy_path)
        if _parser is None:
            # Fallback: try to get Python parser specifically
            from parsers.tree_sitter_factory import get_tree_sitter_parser
            _parser = get_tree_sitter_parser('python', ['.py'])
    return _parser


def parse_file(filepath: Path, max_retries: int = 3, retry_delay: float = 0.5):
    """
    Parse a Python file into an AST (Abstract Syntax Tree).
    
    Handles OneDrive file locking issues with retry logic.
    Uses Tree-sitter parser via registry.
    
    Args:
        filepath: Path to the Python file
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Initial delay between retries in seconds (default: 0.5)
    
    Returns:
        Tree-sitter tree object, or None if parsing fails
    
    Example:
        tree = parse_file(Path("test_agent.py"))
        # Returns a Tree-sitter tree object if successful
    """
    global _parser
    if _parser is None:
        _parser = get_parser(filepath)
        if _parser is None:
            # Fallback: try to get Python parser specifically
            from parsers.tree_sitter_factory import get_tree_sitter_parser
            _parser = get_tree_sitter_parser('python', ['.py'])
    
    if _parser is None:
        return None
    
    return _parser.parse_file(filepath, max_retries, retry_delay)


def extract_imports(tree) -> Dict[str, List[str]]:
    """
    Extract all import statements from an AST.
    
    Args:
        tree: AST Module node
    
    Returns:
        Dictionary with:
        - 'imports': List of module names imported (import X)
        - 'from_imports': List of (module, [names]) tuples (from X import Y)
        - 'all_imports': Combined list of all imported modules
    
    Example:
        # Parse a file with imports
        # tree = ast.parse("import os\\nfrom pathlib import Path")
        # imports = extract_imports(tree)
        # 'os' will be in imports['imports']
    """
    parser = _ensure_parser_initialized()
    if parser is None or tree is None:
        return {'imports': [], 'from_imports': [], 'all_imports': []}
    return parser.extract_imports(tree)


def extract_classes(tree) -> List[Dict[str, Any]]:
    """
    Extract all class definitions from an AST.
    
    Args:
        tree: AST Module node
    
    Returns:
        List of dictionaries with class information:
        - name: Class name
        - bases: List of base class names
        - methods: List of method names
        - line_number: Line where class is defined
    
    Example:
        # Parse a file with a class
        # tree = ast.parse("class TestAgent:\\n    def test_method(self): pass")
        # classes = extract_classes(tree)
        # classes[0]['name'] will be 'TestAgent'
    """
    parser = _ensure_parser_initialized()
    if parser is None or tree is None:
        return []
    return parser.extract_classes(tree)


def extract_functions(tree) -> List[Dict[str, Any]]:
    """
    Extract all function definitions from an AST.
    
    Args:
        tree: AST Module node
    
    Returns:
        List of dictionaries with function information:
        - name: Function name
        - is_async: Whether function is async
        - parameters: List of parameter names
        - line_number: Line where function is defined
        - decorators: List of decorator names
    
    Example:
        # Parse a file with a decorated function
        # tree = ast.parse("@pytest.mark.asyncio\\ndef test_func(): pass")
        # funcs = extract_functions(tree)
        # funcs[0]['name'] will be 'test_func'
    """
    parser = _ensure_parser_initialized()
    if parser is None or tree is None:
        return []
    return parser.extract_functions(tree)


def extract_test_classes(tree) -> List[Dict[str, Any]]:
    """
    Extract test classes (classes that start with 'Test' or inherit from TestCase).
    
    Args:
        tree: Tree-sitter tree object
    
    Returns:
        List of test class dictionaries (same format as extract_classes)
    
    Example:
        # Parse a file with a test class
        # tree = parse_file(Path("test_agent.py"))
        # test_classes = extract_test_classes(tree)
        # len(test_classes) will be 1
    """
    all_classes = extract_classes(tree)
    
    # Filter for test classes
    test_classes = []
    for cls in all_classes:
        # Check if class name starts with 'Test'
        if cls.get('name', '').startswith('Test'):
            test_classes.append(cls)
        # Check if it has 'Test' in any base class (if bases are available)
        bases = cls.get('bases', [])
        if bases and any('Test' in str(base) for base in bases):
            test_classes.append(cls)
    
    return test_classes


def extract_test_methods(tree) -> List[Dict[str, Any]]:
    """
    Extract test methods (methods that start with 'test_').
    
    Args:
        tree: AST Module node
    
    Returns:
        List of test method dictionaries (same format as extract_functions)
    
    Example:
        # Parse a file with a test function
        # tree = ast.parse("def test_agent(): pass")
        # test_methods = extract_test_methods(tree)
        # len(test_methods) will be 1
    """
    parser = _ensure_parser_initialized()
    if parser is None or tree is None:
        return []
    return parser.extract_test_methods(tree)


def extract_docstrings(tree) -> Dict[str, str]:
    """
    Extract docstrings from module, classes, and functions.
    
    Note: Tree-sitter parser doesn't have direct docstring extraction.
    This is a simplified version that returns empty docstrings.
    For full docstring support, consider using Python's ast module directly.
    
    Args:
        tree: Tree-sitter tree object
    
    Returns:
        Dictionary mapping names to docstrings:
        - 'module': Module-level docstring (empty for Tree-sitter)
        - 'classes': Dict of class_name -> docstring (empty for Tree-sitter)
        - 'functions': Dict of function_name -> docstring (empty for Tree-sitter)
    """
    # Tree-sitter doesn't provide easy docstring extraction
    # Return empty structure for compatibility
    return {
        'module': None,
        'classes': {},
        'functions': {}
    }


def _get_attr_name(node) -> str:
    """
    Helper function to get full attribute name (e.g., 'pytest.mark.asyncio').
    
    Note: This is Tree-sitter specific and may not work the same as Python AST.
    
    Args:
        node: Tree-sitter node
    
    Returns:
        Full attribute name as string
    """
    parser = _ensure_parser_initialized()
    # Tree-sitter parser should have this method if needed
    if parser and hasattr(parser, '_get_attr_name'):
        return parser._get_attr_name(node)
    # Fallback: return node text
    if hasattr(node, 'text'):
        return node.text.decode('utf-8') if isinstance(node.text, bytes) else node.text
    return ""


def extract_string_references(tree) -> List[str]:
    """
    Extract string-based references from function calls like:
    - patch('agent.agent_pool.LangGraphAgent')
    - mock.patch('module.Class')
    - @patch('module.function')
    - unittest.mock.patch('module.method')
    
    This is important because many tests use string-based references
    in patch() calls that aren't captured by regular import analysis.
    
    Args:
        tree: AST Module node
    
    Returns:
        List of module/class names found in string literals
    
    Example:
        # Code: @patch('agent.agent_pool.LangGraphAgent')
        # tree = ast.parse("...")
        # refs = extract_string_references(tree)
        # refs will contain 'agent.agent_pool.LangGraphAgent'
    """
    parser = _ensure_parser_initialized()
    if parser is None or tree is None:
        return []
    return parser.extract_string_references(tree)


def extract_function_calls(tree) -> List[Dict[str, Any]]:
    """
    Extract all function calls made inside each test method.
    
    For each test method, finds:
    - What functions it directly calls (e.g., initialize())
    - What methods it calls on objects (e.g., agent.initialize())
    - Filters out test framework calls (assert, patch, Mock, etc.)
    
    Args:
        tree: AST Module node
    
    Returns:
        List of dictionaries, one per test method:
        - test_method: Name of the test method
        - calls: List of call dictionaries with:
            - function: Function/method name
            - object: Object name (if method call, e.g., 'agent')
            - type: 'direct' or 'method'
            - line_number: Line where call occurs
    
    Example:
        # Code: 
        # def test_agent_initialization(self, agent):
        #     await agent.initialize()
        #     assert agent._initialized is True
        # 
        # tree = ast.parse("...")
        # calls = extract_function_calls(tree)
        # calls[0]['calls'] will contain {'function': 'initialize', 'object': 'agent', 'type': 'method'}
    """
    parser = _ensure_parser_initialized()
    if parser is None or tree is None:
        return []
    return parser.extract_function_calls(tree)