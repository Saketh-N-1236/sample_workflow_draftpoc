"""
JavaScript/TypeScript dependency extraction plugin.

Handles:
- ES6 import statements (import Foo from 'bar')
- CommonJS require() calls
- Production code identification
- Module name extraction
"""

import re
from pathlib import Path
from typing import List, Optional
import logging

from .base import DependencyPlugin

logger = logging.getLogger(__name__)


class JavaScriptDependencyPlugin(DependencyPlugin):
    """
    Plugin for extracting dependencies from JavaScript/TypeScript files.
    """
    
    # JavaScript test framework packages
    TEST_FRAMEWORK_PACKAGES = {
        'jest', 'mocha', 'chai', 'sinon', 'supertest',
        'ava', 'tape', 'jasmine', 'vitest', 'qunit',
    }
    
    # Node.js standard library (built-in modules)
    STD_LIB_MODULES = {
        'fs', 'path', 'http', 'https', 'url', 'util',
        'events', 'stream', 'crypto', 'os', 'child_process',
        'cluster', 'net', 'dgram', 'dns', 'readline',
    }
    
    def __init__(self):
        super().__init__('javascript')
    
    def extract_imports(self, filepath: Path, content: str) -> List[str]:
        """
        Extract JavaScript/TypeScript import statements.
        
        Handles:
        - import Foo from 'module'
        - import { Foo, Bar } from 'module'
        - import * as Foo from 'module'
        - require('module')
        - const Foo = require('module')
        """
        imports = []
        
        # ES6 import patterns
        # import Foo from 'module'
        # import { Foo } from 'module'
        # import * as Foo from 'module'
        import_pattern = re.compile(
            r"import\s+(?:(?:\*\s+as\s+\w+)|(?:\{[^}]*\})|(?:\w+))\s+from\s+['\"]([@\w./\-]+)['\"]",
            re.MULTILINE
        )
        for match in import_pattern.finditer(content):
            module = match.group(1)
            # Remove @scope/ if present (e.g., @types/node -> node)
            if module.startswith('@'):
                parts = module.split('/')
                if len(parts) > 1:
                    module = '/'.join(parts[1:])
            if module and module not in imports:
                imports.append(module)
        
        # CommonJS require() patterns
        # require('module')
        # const Foo = require('module')
        require_pattern = re.compile(
            r"require\s*\(\s*['\"]([@\w./\-]+)['\"]\s*\)",
            re.MULTILINE
        )
        for match in require_pattern.finditer(content):
            module = match.group(1)
            if module.startswith('@'):
                parts = module.split('/')
                if len(parts) > 1:
                    module = '/'.join(parts[1:])
            if module and module not in imports:
                imports.append(module)
        
        logger.debug(f"Extracted {len(imports)} imports from {filepath.name}")
        return imports
    
    def is_production_import(self, import_name: str) -> bool:
        """
        Check if import is production code.
        
        Excludes:
        - Node.js standard library
        - Test frameworks (jest, mocha, chai, etc.)
        """
        if not import_name:
            return False
        
        import_lower = import_name.lower()
        
        # Check standard library
        first_part = import_name.split('/')[0].split('@')[-1]  # Handle @scope/name
        if first_part in self.STD_LIB_MODULES:
            return False
        
        # Check test frameworks
        for test_pkg in self.TEST_FRAMEWORK_PACKAGES:
            if import_lower.startswith(test_pkg.lower()):
                return False
        
        # Check for test keywords
        parts = import_lower.split('/')
        test_keywords = {'test', 'tests', 'testing', 'spec', 'specs', '__tests__'}
        if any(kw in parts for kw in test_keywords):
            return False
        
        return True
    
    def extract_class_name(self, import_name: str) -> Optional[str]:
        """
        Extract class/module name from import.
        
        Examples:
        - @types/node -> node
        - foo/bar/baz -> baz
        - ./local/module -> module
        """
        if not import_name:
            return None
        
        # Remove @scope/ prefix
        if import_name.startswith('@'):
            parts = import_name.split('/')
            if len(parts) > 1:
                import_name = '/'.join(parts[1:])
        
        # Remove relative path prefixes
        import_name = import_name.lstrip('./')
        
        # Get last part
        parts = import_name.split('/')
        if parts:
            name = parts[-1]
            # Remove file extension if present
            name = name.split('.')[0]
            return name
        
        return None
    
    def extract_string_references(self, filepath: Path, content: str) -> List[str]:
        """
        Extract string-based references (less common in JS/TS).
        
        Could look for:
        - Dynamic imports: import('module')
        - require() with variables (harder to extract)
        """
        references = []
        
        # Dynamic import() calls
        dynamic_import_pattern = re.compile(
            r"import\s*\(\s*['\"]([@\w./\-]+)['\"]\s*\)",
            re.MULTILINE
        )
        for match in dynamic_import_pattern.finditer(content):
            ref = match.group(1)
            if ref and ref not in references:
                references.append(ref)
        
        return references
