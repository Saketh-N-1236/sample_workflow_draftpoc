"""
Python language parser implementation.

This module refactors the existing AST parsing utilities into a LanguageParser
implementation, maintaining backward compatibility while enabling multi-language support.
"""

import ast
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
import re
import time

from parsers.base import LanguageParser


class PythonParser(LanguageParser):
    """Python AST parser implementation."""
    
    @property
    def language_name(self) -> str:
        """Return language name."""
        return "python"
    
    @property
    def file_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return ['.py']
    
    def can_parse(self, filepath: Path) -> bool:
        """Check if this parser can handle the file."""
        return filepath.suffix == '.py'
    
    def parse_file(self, filepath: Path, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[ast.Module]:
        """
        Parse a Python file into an AST (Abstract Syntax Tree).
        
        Handles OneDrive file locking issues with retry logic.
        """
        for attempt in range(max_retries):
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                return ast.parse(content, filename=str(filepath))
            except PermissionError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Warning: Permission denied after {max_retries} attempts: {filepath}")
                    print(f"  This may be due to OneDrive syncing. Try closing OneDrive or waiting for sync to complete.")
                    return None
            except SyntaxError as e:
                print(f"Warning: Could not parse {filepath}: {e}")
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Warning: Error reading {filepath} after {max_retries} attempts: {e}")
                    return None
        
        return None
    
    def extract_imports(self, ast_tree: Any) -> Dict[str, List[str]]:
        """Extract all import statements from an AST."""
        if not isinstance(ast_tree, ast.Module):
            return {'imports': [], 'from_imports': [], 'all_imports': []}
        
        imports = []
        from_imports = []
        
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            
            elif isinstance(node, ast.ImportFrom):
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
    
    def extract_classes(self, ast_tree: Any) -> List[Dict[str, Any]]:
        """Extract all class definitions from an AST."""
        if not isinstance(ast_tree, ast.Module):
            return []
        
        classes = []
        
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ClassDef):
                # Get base class names
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(self._get_attr_name(base))
                
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
    
    def extract_functions(self, ast_tree: Any) -> List[Dict[str, Any]]:
        """Extract all function definitions from an AST."""
        if not isinstance(ast_tree, ast.Module):
            return []
        
        functions = []
        
        for node in ast.walk(ast_tree):
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
                        decorators.append(self._get_attr_name(decorator))
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            decorators.append(self._get_attr_name(decorator.func))
                
                # Determine class name if method
                class_name = None
                parent = node
                while hasattr(parent, 'parent'):
                    parent = parent.parent
                    if isinstance(parent, ast.ClassDef):
                        class_name = parent.name
                        break
                
                functions.append({
                    'name': node.name,
                    'is_async': is_async,
                    'parameters': parameters,
                    'line_number': node.lineno,
                    'decorators': decorators,
                    'class_name': class_name
                })
        
        return functions
    
    def extract_test_methods(self, ast_tree: Any) -> List[Dict[str, Any]]:
        """Extract test methods from AST."""
        if not isinstance(ast_tree, ast.Module):
            return []
        
        all_functions = self.extract_functions(ast_tree)
        
        # Filter for test methods
        test_methods = []
        for func in all_functions:
            if func['name'].startswith('test_'):
                test_methods.append({
                    'name': func['name'],
                    'class_name': func.get('class_name'),
                    'line_number': func['line_number'],
                    'is_async': func['is_async']
                })
        
        return test_methods
    
    def extract_function_calls(self, ast_tree: Any) -> List[Dict[str, Any]]:
        """Extract all function calls made inside each test method."""
        if not isinstance(ast_tree, ast.Module):
            return []
        
        test_function_calls = []
        
        # Test framework functions to exclude
        TEST_FRAMEWORK_FUNCTIONS = {
            'assert', 'assertEqual', 'assertNotEqual', 'assertTrue', 'assertFalse',
            'assertIn', 'assertNotIn', 'assertIs', 'assertIsNot', 'assertIsNone',
            'assertIsNotNone', 'assertRaises', 'assertRaisesRegex',
            'patch', 'Mock', 'MagicMock', 'AsyncMock', 'PropertyMock',
            'pytest', 'fixture', 'mark', 'raises', 'parametrize',
            'setUp', 'tearDown', 'setUpClass', 'tearDownClass'
        }
        
        def get_object_name(node) -> Optional[str]:
            """Extract object name from an AST node."""
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                current = node
                while isinstance(current, ast.Attribute):
                    current = current.value
                if isinstance(current, ast.Name):
                    return current.id
            return None
        
        # Walk through all nodes to find test methods
        for node in ast.walk(ast_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('test_'):
                    continue
                
                calls = []
                
                # Walk inside this specific test method to find calls
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func_name = None
                        object_name = None
                        call_type = 'direct'
                        
                        if isinstance(child.func, ast.Name):
                            func_name = child.func.id
                            call_type = 'direct'
                        elif isinstance(child.func, ast.Attribute):
                            func_name = child.func.attr
                            object_name = get_object_name(child.func.value)
                            call_type = 'method'
                        
                        if func_name and func_name not in TEST_FRAMEWORK_FUNCTIONS:
                            if object_name and ('mock' in object_name.lower() or 'Mock' in object_name):
                                pass  # Still include mock calls
                            
                            calls.append({
                                'function': func_name,
                                'object': object_name,
                                'type': call_type,
                                'line_number': child.lineno
                            })
                
                if calls:
                    test_function_calls.append({
                        'test_method': node.name,
                        'calls': calls
                    })
        
        return test_function_calls
    
    def extract_string_references(self, ast_tree: Any) -> List[str]:
        """Extract string-based references from function calls like patch('module.Class')."""
        if not isinstance(ast_tree, ast.Module):
            return []
        
        string_refs = []
        
        def is_patch_function(node) -> bool:
            """Check if a node represents a patch/mock function call."""
            if isinstance(node, ast.Name):
                return node.id in ('patch', 'Mock', 'MagicMock', 'PropertyMock', 'AsyncMock')
            elif isinstance(node, ast.Attribute):
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
        
        for node in ast.walk(ast_tree):
            # Check function calls (patch('module.Class'))
            if isinstance(node, ast.Call):
                if is_patch_function(node.func):
                    for arg in node.args:
                        ref = extract_string_from_node(arg)
                        if ref and '.' in ref and not ref.startswith('http'):
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
        
        return sorted(list(set(string_refs)))
    
    def resolve_module_name(self, filepath: Path, project_root: Path) -> str:
        """
        Convert file path to module name.
        
        Example:
            project_root = Path("/project")
            filepath = Path("/project/agent/langgraph_agent.py")
            Returns: "agent.langgraph_agent"
        """
        try:
            # Get relative path from project root
            relative_path = filepath.relative_to(project_root)
            
            # Remove .py extension and convert to module name
            parts = relative_path.parts[:-1] + (relative_path.stem,)
            module_name = '.'.join(parts)
            
            return module_name
        except ValueError:
            # File is not under project root, use stem as fallback
            return filepath.stem
    
    def _get_attr_name(self, node: ast.Attribute) -> str:
        """Helper function to get full attribute name (e.g., 'pytest.mark.asyncio')."""
        parts = []
        current = node
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.append(current.id)
        
        return '.'.join(reversed(parts))
