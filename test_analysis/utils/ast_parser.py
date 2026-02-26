"""
AST (Abstract Syntax Tree) parsing utilities.

This module provides functions to:
- Parse Python files into AST
- Extract imports and dependencies
- Extract class and method definitions
- Extract test-related information from AST nodes
"""

import ast
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
import re


def parse_file(filepath: Path) -> Optional[ast.Module]:
    """
    Parse a Python file into an AST (Abstract Syntax Tree).
    
    Args:
        filepath: Path to the Python file
    
    Returns:
        AST Module node, or None if parsing fails
    
    Example:
        tree = parse_file(Path("test_agent.py"))
        # Returns an ast.Module object if successful
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return ast.parse(content, filename=str(filepath))
    except SyntaxError as e:
        print(f"Warning: Could not parse {filepath}: {e}")
        return None
    except Exception as e:
        print(f"Warning: Error reading {filepath}: {e}")
        return None


def extract_imports(tree: ast.Module) -> Dict[str, List[str]]:
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
    imports = []
    from_imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # Handle: import module
            for alias in node.names:
                imports.append(alias.name)
        
        elif isinstance(node, ast.ImportFrom):
            # Handle: from module import name
            if node.module:  # module can be None for relative imports
                imported_names = [alias.name for alias in node.names]
                from_imports.append((node.module, imported_names))
                imports.append(node.module)  # Also add the module itself
    
    # Combine all unique imports
    all_imports = list(set(imports))
    
    return {
        'imports': imports,
        'from_imports': from_imports,
        'all_imports': all_imports
    }


def extract_classes(tree: ast.Module) -> List[Dict[str, Any]]:
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
    classes = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Get base class names
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    # Handle dotted names like unittest.TestCase
                    bases.append(_get_attr_name(base))
            
            # Get method names (including async methods)
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            
            classes.append({
                'name': node.name,
                'bases': bases,
                'methods': methods,
                'line_number': node.lineno
            })
    
    return classes


def extract_functions(tree: ast.Module) -> List[Dict[str, Any]]:
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
    functions = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            is_async = isinstance(node, ast.AsyncFunctionDef)
            
            # Get parameter names
            parameters = [arg.arg for arg in node.args.args]
            
            # Get decorator names
            decorators = []
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorators.append(decorator.id)
                elif isinstance(decorator, ast.Attribute):
                    decorators.append(_get_attr_name(decorator))
                elif isinstance(decorator, ast.Call):
                    # Handle @pytest.mark.asyncio() style
                    if isinstance(decorator.func, ast.Attribute):
                        decorators.append(_get_attr_name(decorator.func))
            
            functions.append({
                'name': node.name,
                'is_async': is_async,
                'parameters': parameters,
                'line_number': node.lineno,
                'decorators': decorators
            })
    
    return functions


def extract_test_classes(tree: ast.Module) -> List[Dict[str, Any]]:
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


def extract_test_methods(tree: ast.Module) -> List[Dict[str, Any]]:
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
    all_functions = extract_functions(tree)
    
    # Filter for test methods
    test_methods = []
    for func in all_functions:
        if func['name'].startswith('test_'):
            test_methods.append(func)
    
    return test_methods


def extract_docstrings(tree: ast.Module) -> Dict[str, str]:
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


def _get_attr_name(node: ast.Attribute) -> str:
    """
    Helper function to get full attribute name (e.g., 'pytest.mark.asyncio').
    
    Args:
        node: AST Attribute node
    
    Returns:
        Full attribute name as string
    """
    parts = []
    current = node
    
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    
    if isinstance(current, ast.Name):
        parts.append(current.id)
    
    return '.'.join(reversed(parts))


def extract_string_references(tree: ast.Module) -> List[str]:
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
    string_refs = []
    
    def is_patch_function(node) -> bool:
        """Check if a node represents a patch/mock function call."""
        if isinstance(node, ast.Name):
            return node.id in ('patch', 'Mock', 'MagicMock', 'PropertyMock', 'AsyncMock')
        elif isinstance(node, ast.Attribute):
            # Handle mock.patch, unittest.mock.patch, etc.
            return node.attr in ('patch', 'Mock', 'MagicMock', 'PropertyMock', 'AsyncMock')
        return False
    
    def extract_string_from_node(node) -> Optional[str]:
        """Extract string value from various AST node types."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8 compatibility
            return node.s
        return None
    
    for node in ast.walk(tree):
        # Check function calls (patch('module.Class'))
        if isinstance(node, ast.Call):
            if is_patch_function(node.func):
                # Extract string arguments
                for arg in node.args:
                    ref = extract_string_from_node(arg)
                    if ref and '.' in ref and not ref.startswith('http'):
                        # Filter out URLs and non-module strings
                        # Module paths typically have dots and don't start with http
                        if not ref.startswith('/') and not ref.startswith('\\'):
                            string_refs.append(ref)
        
        # Check decorators with string arguments (@patch('module.Class'))
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    if is_patch_function(decorator.func):
                        for arg in decorator.args:
                            ref = extract_string_from_node(arg)
                            if ref and '.' in ref and not ref.startswith('http'):
                                if not ref.startswith('/') and not ref.startswith('\\'):
                                    string_refs.append(ref)
    
    # Remove duplicates and return
    return sorted(list(set(string_refs)))
