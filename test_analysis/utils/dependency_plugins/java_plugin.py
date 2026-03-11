"""
Java dependency extraction plugin.

Handles:
- Java import statements (import com.example.Foo;)
- Production code identification (excludes java.*, javax.*, test frameworks)
- Class name extraction from fully qualified names
- String-based references (e.g., Mockito.when() calls)
"""

import re
from pathlib import Path
from typing import List, Optional
import logging

from .base import DependencyPlugin

logger = logging.getLogger(__name__)


class JavaDependencyPlugin(DependencyPlugin):
    """
    Plugin for extracting dependencies from Java files.
    """
    
    # Java test framework packages to exclude
    TEST_FRAMEWORK_PACKAGES = {
        'org.junit', 'org.testng', 'org.mockito', 'org.hamcrest',
        'org.assertj', 'junit', 'testng', 'mockito', 'hamcrest', 'assertj',
        'org.powermock', 'org.easymock', 'org.jmock',
    }
    
    # Java standard library prefixes to exclude
    STD_LIB_PREFIXES = {'java', 'javax', 'sun', 'com.sun', 'jdk'}
    
    def __init__(self):
        super().__init__('java')
    
    def extract_imports(self, filepath: Path, content: str) -> List[str]:
        """
        Extract Java import statements.
        
        Handles:
        - import com.example.Foo;
        - import static com.example.Bar.*;
        - import com.example.Baz.*;
        """
        imports = []
        
        # Pattern for: import [static] package.Class;
        pattern = re.compile(r'^import\s+(?:static\s+)?([\w.]+(?:\.[*])?)\s*;', re.MULTILINE)
        
        for match in pattern.finditer(content):
            import_stmt = match.group(1)
            # Remove wildcard imports (.*) - keep base package
            if import_stmt.endswith('.*'):
                import_stmt = import_stmt[:-2]
            if import_stmt and import_stmt not in imports:
                imports.append(import_stmt)
        
        if imports:
            logger.debug(f"Extracted {len(imports)} imports from {filepath.name}: {imports[:3]}")
        return imports
    
    def is_production_import(self, import_name: str) -> bool:
        """
        Check if import is production code.
        
        Excludes:
        - Standard library (java.*, javax.*, sun.*)
        - Test frameworks (org.junit.*, org.mockito.*, etc.)
        """
        if not import_name:
            return False
        
        import_lower = import_name.lower()
        
        # Check standard library
        first_part = import_name.split('.')[0]
        if first_part in self.STD_LIB_PREFIXES:
            logger.debug(f"Filtered out stdlib import: {import_name}")
            return False
        
        # Check test frameworks
        for test_pkg in self.TEST_FRAMEWORK_PACKAGES:
            if import_lower.startswith(test_pkg.lower()):
                logger.debug(f"Filtered out test framework import: {import_name}")
                return False
        
        # If it's not stdlib or test framework, it's likely production code
        logger.debug(f"Identified as production import: {import_name}")
        return True
    
    def extract_class_name(self, import_name: str) -> Optional[str]:
        """
        Extract class name from fully qualified import.
        
        Examples:
        - com.strmecast.istream.request.LoginRequest -> LoginRequest
        - com.example.Foo -> Foo
        - java.util.List -> None (stdlib, filtered out)
        """
        if not import_name:
            return None
        
        # Split by dots and get last part (class name)
        parts = import_name.split('.')
        if parts:
            class_name = parts[-1]
            # Validate it looks like a class name (starts with uppercase)
            if class_name and class_name[0].isupper():
                return class_name
        
        return None
    
    def extract_string_references(self, filepath: Path, content: str) -> List[str]:
        """
        Extract string-based references (e.g., in Mockito.when() calls).
        
        This is less common in Java than Python, but we can look for:
        - Class.forName("com.example.Foo")
        - Reflection patterns
        """
        references = []
        
        # Pattern for Class.forName("com.example.Foo")
        forname_pattern = re.compile(r'Class\.forName\s*\(\s*["\']([^"\']+)["\']', re.MULTILINE)
        for match in forname_pattern.finditer(content):
            ref = match.group(1)
            if ref and ref not in references:
                references.append(ref)
        
        # Pattern for string literals that look like class names (simple heuristic)
        # Look for strings that match package.ClassName pattern
        string_pattern = re.compile(r'["\']([a-z][\w.]*[A-Z][\w]*)[\'"]', re.MULTILINE)
        for match in string_pattern.finditer(content):
            ref = match.group(1)
            # Validate it looks like a fully qualified class name
            if '.' in ref and ref.split('.')[-1][0].isupper():
                if ref not in references:
                    references.append(ref)
        
        return references
    
    def infer_production_dependencies_from_test_structure(self, filepath: Path, content: str) -> List[str]:
        """
        Infer production code dependencies from test file structure when explicit imports are missing.
        
        Patterns:
        1. Package structure: com.strmecast.istream.test.authentication -> com.strmecast.istream.*
        2. Class naming: LoginServiceTest -> LoginService
        3. File path: test/authentication/LoginServiceTest.java -> LoginService
        
        Returns:
            List of inferred production class names or package paths
        """
        inferred = []
        
        # Extract package declaration
        package_match = re.search(r'^package\s+([\w.]+)\s*;', content, re.MULTILINE)
        if package_match:
            test_package = package_match.group(1)
            
            # Pattern 1: Remove .test from package to get production package
            # com.strmecast.istream.test.authentication -> com.strmecast.istream.authentication
            if '.test' in test_package:
                production_package = test_package.replace('.test', '')
                # Add the production package as a dependency
                inferred.append(production_package)
                logger.debug(f"Inferred production package from test package: {test_package} -> {production_package}")
        
        # Extract class name from file
        class_match = re.search(r'(?:public\s+)?class\s+(\w+)', content)
        if class_match:
            test_class_name = class_match.group(1)
            
            # Pattern 2: Remove "Test" suffix to get production class name
            # LoginServiceTest -> LoginService
            # AccountLockoutTest -> AccountLockout
            if test_class_name.endswith('Test') or test_class_name.endswith('Tests'):
                production_class_name = test_class_name[:-4] if test_class_name.endswith('Test') else test_class_name[:-5]
                if production_class_name:
                    inferred.append(production_class_name)
                    logger.debug(f"Inferred production class from test class: {test_class_name} -> {production_class_name}")
                    
                    # If we have a package, create fully qualified name
                    if package_match:
                        test_package = package_match.group(1)
                        if '.test' in test_package:
                            production_package = test_package.replace('.test', '')
                            # Try common package structures
                            # com.strmecast.istream.test.authentication -> com.strmecast.istream.service/controller/request/response
                            base_package = production_package.rsplit('.', 1)[0] if '.' in production_package else production_package
                            
                            # Common Java package patterns
                            for subpackage in ['service', 'controller', 'request', 'response', 'model', 'entity', 'dto']:
                                full_class = f"{base_package}.{subpackage}.{production_class_name}"
                                inferred.append(full_class)
                            
                            # Also try without subpackage
                            full_class = f"{base_package}.{production_class_name}"
                            inferred.append(full_class)
        
        # Pattern 3: Extract from file path
        # test/authentication/LoginServiceTest.java -> authentication/LoginService
        file_path_str = str(filepath)
        if 'test' in file_path_str.lower():
            # Extract directory structure
            parts = file_path_str.replace('\\', '/').split('/')
            test_idx = None
            for i, part in enumerate(parts):
                if 'test' in part.lower() and i < len(parts) - 1:
                    test_idx = i
                    break
            
            if test_idx is not None and test_idx + 1 < len(parts):
                # Get module/category after test directory
                module = parts[test_idx + 1] if test_idx + 1 < len(parts) else None
                if module:
                    # Extract class name from filename
                    filename = filepath.stem  # Without extension
                    if filename.endswith('Test') or filename.endswith('Tests'):
                        prod_class = filename[:-4] if filename.endswith('Test') else filename[:-5]
                        if prod_class:
                            # Build potential production package
                            if package_match:
                                test_package = package_match.group(1)
                                if '.test' in test_package:
                                    base_package = test_package.replace('.test', '').rsplit('.', 1)[0]
                                    for subpkg in ['service', 'controller', 'request', 'response', 'model']:
                                        inferred.append(f"{base_package}.{subpkg}.{prod_class}")
        
        # Remove duplicates and filter
        unique_inferred = []
        for inf in inferred:
            if inf and inf not in unique_inferred:
                # Filter out test-related names
                if 'test' not in inf.lower() or inf.endswith('Test'):
                    unique_inferred.append(inf)
        
        if unique_inferred:
            logger.debug(f"Inferred {len(unique_inferred)} production dependencies from test structure: {unique_inferred[:3]}")
        
        return unique_inferred
