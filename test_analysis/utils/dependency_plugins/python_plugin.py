"""
Python dependency extraction plugin.

Handles:
- Python import statements (import foo, from bar import baz)
- Production code identification (excludes stdlib, test frameworks)
- Module/class name extraction
- String-based references (e.g., patch() calls)
"""

import re
import ast
from pathlib import Path
from typing import List, Optional
import logging

from .base import DependencyPlugin

logger = logging.getLogger(__name__)


class PythonDependencyPlugin(DependencyPlugin):
    """
    Plugin for extracting dependencies from Python files.
    """
    
    # Python test framework packages
    TEST_FRAMEWORK_PACKAGES = {
        'pytest', 'unittest', 'mock', 'unittest.mock',
        'pytest_mock', 'pytest_asyncio', 'pytest_cov',
        'nose', 'nose2', 'doctest',
    }
    
    # Python standard library (common modules)
    STD_LIB_MODULES = {
        'os', 'sys', 'pathlib', 'json', 'datetime', 'typing',
        'collections', 'itertools', 'functools', 'asyncio',
        'abc', 'dataclasses', 'enum', 'logging', 're', 'io',
        'time', 'copy', 'math', 'random', 'string', 'struct',
        'urllib', 'http', 'socket', 'threading', 'multiprocessing',
    }
    
    def __init__(self):
        super().__init__('python')
    
    def extract_imports(self, filepath: Path, content: str) -> List[str]:
        """
        Extract Python import statements.
        
        Handles:
        - import foo
        - from bar import baz
        - from foo.bar import baz, qux
        """
        imports = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fallback to regex if AST parsing fails
            return self._extract_imports_regex(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in imports:
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    if node.module not in imports:
                        imports.append(node.module)
                    # Also add individual names from "from X import Y"
                    for alias in node.names:
                        full_name = f"{node.module}.{alias.name}"
                        if full_name not in imports:
                            imports.append(full_name)
        
        logger.debug(f"Extracted {len(imports)} imports from {filepath.name}")
        return imports
    
    def _extract_imports_regex(self, content: str) -> List[str]:
        """Fallback regex-based import extraction."""
        imports = []
        
        # Pattern for: import module
        pattern1 = re.compile(r'^import\s+([\w.]+)', re.MULTILINE)
        for match in pattern1.finditer(content):
            if match.group(1) not in imports:
                imports.append(match.group(1))
        
        # Pattern for: from module import name
        pattern2 = re.compile(r'^from\s+([\w.]+)\s+import', re.MULTILINE)
        for match in pattern2.finditer(content):
            if match.group(1) not in imports:
                imports.append(match.group(1))
        
        return imports
    
    def is_production_import(self, import_name: str) -> bool:
        """
        Check if import is production code.
        
        Excludes:
        - Standard library modules
        - Test frameworks (pytest, unittest, mock, etc.)
        """
        if not import_name:
            return False
        
        import_lower = import_name.lower()
        
        # Check standard library
        first_part = import_name.split('.')[0]
        if first_part in self.STD_LIB_MODULES:
            return False
        
        # Check test frameworks
        for test_pkg in self.TEST_FRAMEWORK_PACKAGES:
            if import_lower.startswith(test_pkg.lower()):
                return False
        
        # Check for test keywords in import path
        parts = import_lower.split('.')
        test_keywords = {'test', 'tests', 'testing', 'spec', 'specs'}
        if any(kw in parts for kw in test_keywords):
            return False
        
        return True
    
    def extract_class_name(self, import_name: str) -> Optional[str]:
        """
        Extract class/module name from import.
        
        Examples:
        - foo.bar.Baz -> Baz
        - foo -> foo
        """
        if not import_name:
            return None
        
        parts = import_name.split('.')
        if parts:
            # Get last part
            name = parts[-1]
            # If it starts with uppercase, it's likely a class
            if name and name[0].isupper():
                return name
            # Otherwise return module name
            return name
        
        return None
    
    def extract_string_references(self, filepath: Path, content: str) -> List[str]:
        """
        Extract string-based references (e.g., patch() calls).
        
        Handles:
        - patch('module.Class.method')
        - mock.patch('foo.bar')
        """
        references = []
        
        # Pattern for patch('module.Class.method')
        patch_pattern = re.compile(
            r'(?:patch|mock\.patch|unittest\.mock\.patch)\s*\(\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        for match in patch_pattern.finditer(content):
            ref = match.group(1)
            if ref and ref not in references:
                references.append(ref)
        
        return references
