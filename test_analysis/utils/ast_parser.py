"""
AST (Abstract Syntax Tree) parsing utilities.

This module provides functions to:
- Parse Python files into AST
- Extract imports and dependencies
- Extract class and method definitions
- Extract test-related information from AST nodes

NOTE: This module now uses the new PythonParser class for implementation.
All functions are maintained for backward compatibility.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import ast
# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from parsers.python_parser import PythonParser

# Create a singleton parser instance
_parser = PythonParser()


def parse_file(filepath: Path, max_retries: int = 3, retry_delay: float = 0.5):
    """
    Parse a Python file into an AST (Abstract Syntax Tree).
    
    Handles OneDrive file locking issues with retry logic.
    
    Args:
        filepath: Path to the Python file
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Initial delay between retries in seconds (default: 0.5)
    
    Returns:
        AST Module node, or None if parsing fails
    
    Example:
        tree = parse_file(Path("test_agent.py"))
        # Returns an ast.Module object if successful
    """
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
    return _parser.extract_imports(tree)


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
    return _parser.extract_classes(tree)


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
    return _parser.extract_functions(tree)


def extract_test_classes(tree) -> List[Dict[str, Any]]:
    """
    Extract test classes (classes that start with 'Test' or inherit from TestCase).
    
    Args:
        tree: AST Module node
    
    Returns:
        List of test class dictionaries (same format as extract_classes)
    
    Example:
        # Parse a file with a test class
        # tree = ast.parse("class TestAgent:\\n    def test_method(self): pass")
        # test_classes = extract_test_classes(tree)
        # len(test_classes) will be 1
    """
    import ast
    all_classes = extract_classes(tree)
    
    # Filter for test classes
    test_classes = []
    for cls in all_classes:
        # Check if class name starts with 'Test'
        if cls['name'].startswith('Test'):
            test_classes.append(cls)
        # Check if it inherits from TestCase or similar
        elif any('Test' in base for base in cls['bases']):
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
    return _parser.extract_test_methods(tree)


def extract_docstrings(tree) -> Dict[str, str]:
    """
    Extract docstrings from module, classes, and functions.
    
    Args:
        tree: AST Module node
    
    Returns:
        Dictionary mapping names to docstrings:
        - 'module': Module-level docstring
        - 'classes': Dict of class_name -> docstring
        - 'functions': Dict of function_name -> docstring
    
    Example:
        # Parse a file with a class that has a docstring
        # tree = ast.parse('class Test: pass')  # Class with docstring
        # docs = extract_docstrings(tree)
        # docs['classes']['Test'] will contain the docstring if present
    """
    result = {
        'module': ast.get_docstring(tree),
        'classes': {},
        'functions': {}
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node)
            if docstring:
                result['classes'][node.name] = docstring
        
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = ast.get_docstring(node)
            if docstring:
                result['functions'][node.name] = docstring
    
    return result


def _get_attr_name(node) -> str:
    """
    Helper function to get full attribute name (e.g., 'pytest.mark.asyncio').
    
    Args:
        node: AST Attribute node
    
    Returns:
        Full attribute name as string
    """
    import ast
    return _parser._get_attr_name(node)


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
    return _parser.extract_string_references(tree)


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
    return _parser.extract_function_calls(tree)