"""
Java language parser implementation (minimal stub).

This is a minimal implementation that allows file scanning and basic operations.
Full AST parsing can be added later using libraries like javalang or antlr.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import re

from parsers.base import LanguageParser


class JavaParser(LanguageParser):
    """Java parser implementation (minimal stub)."""
    
    @property
    def language_name(self) -> str:
        """Return language name."""
        return "java"
    
    @property
    def file_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return ['.java']
    
    def can_parse(self, filepath: Path) -> bool:
        """Check if this parser can handle the file."""
        return filepath.suffix.lower() == '.java'
    
    def parse_file(self, filepath: Path, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[Any]:
        """
        Parse a Java file (stub - returns file content for now).
        
        TODO: Implement full AST parsing using javalang or antlr.
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return {'content': f.read(), 'filepath': str(filepath)}
        except Exception:
            return None
    
    def extract_imports(self, ast: Any) -> Dict[str, List[str]]:
        """Extract imports from Java AST (stub)."""
        if not ast or not isinstance(ast, dict):
            return {'imports': [], 'from_imports': [], 'all_imports': []}
        
        # Simple regex for import statements
        imports = []
        content = ast.get('content', '')
        
        import_pattern = r"import\s+(?:static\s+)?([\w.]+(?:\.[\w*]+)?)"
        matches = re.finditer(import_pattern, content)
        
        for match in matches:
            import_stmt = match.group(1)
            # Remove wildcards
            import_stmt = import_stmt.replace('*', '').rstrip('.')
            if import_stmt:
                imports.append(import_stmt)
        
        return {
            'imports': imports,
            'from_imports': [],
            'all_imports': imports
        }
    
    def extract_classes(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract class definitions from Java AST (stub)."""
        if not ast or not isinstance(ast, dict):
            return []
        
        classes = []
        content = ast.get('content', '')
        
        # Simple regex for class definitions
        class_pattern = r"(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?(?:final\s+)?class\s+(\w+)"
        matches = re.finditer(class_pattern, content)
        
        for match in matches:
            classes.append({
                'name': match.group(1),
                'line_number': content[:match.start()].count('\n') + 1,
                'methods': []
            })
        
        return classes
    
    def extract_functions(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract method definitions from Java AST (stub)."""
        if not ast or not isinstance(ast, dict):
            return []
        
        methods = []
        content = ast.get('content', '')
        
        # Simple regex for method definitions
        method_pattern = r"(?:public|private|protected)\s+(?:static\s+)?(?:[\w<>]+\s+)?(\w+)\s*\("
        matches = re.finditer(method_pattern, content)
        
        for match in matches:
            method_name = match.group(1)
            # Skip constructors (same name as class)
            if method_name and method_name[0].islower():
                methods.append({
                    'name': method_name,
                    'line_number': content[:match.start()].count('\n') + 1,
                    'class_name': None,  # TODO: Extract from context
                    'is_async': False
                })
        
        return methods
    
    def extract_test_methods(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract test methods from Java AST (stub)."""
        if not ast or not isinstance(ast, dict):
            return []
        
        test_methods = []
        content = ast.get('content', '')
        
        # Simple regex for JUnit test methods (@Test annotation)
        test_pattern = r"@Test\s+(?:public\s+)?(?:void\s+)?(\w+)\s*\("
        matches = re.finditer(test_pattern, content)
        
        for match in matches:
            test_methods.append({
                'name': match.group(1),
                'class_name': None,  # TODO: Extract from context
                'line_number': content[:match.start()].count('\n') + 1,
                'is_async': False
            })
        
        # Also check for methods starting with "test"
        test_name_pattern = r"(?:public\s+)?(?:void\s+)?(test\w+)\s*\("
        matches = re.finditer(test_name_pattern, content, re.IGNORECASE)
        
        for match in matches:
            method_name = match.group(1)
            if method_name.lower().startswith('test'):
                test_methods.append({
                    'name': method_name,
                    'class_name': None,
                    'line_number': content[:match.start()].count('\n') + 1,
                    'is_async': False
                })
        
        return test_methods
    
    def extract_function_calls(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract function calls from Java AST (stub)."""
        # TODO: Implement using javalang
        return []
    
    def extract_string_references(self, ast: Any) -> List[str]:
        """Extract string-based references from Java AST (stub)."""
        # TODO: Implement
        return []
    
    def resolve_module_name(self, filepath: Path, project_root: Path) -> str:
        """Convert file path to package name (Java style)."""
        try:
            relative_path = filepath.relative_to(project_root)
            # Java uses package notation
            # Remove src/main/java or src/test/java prefixes
            path_str = str(relative_path.parent).replace('\\', '/')
            
            # Remove common source directory prefixes
            for prefix in ['src/main/java', 'src/test/java', 'src']:
                if path_str.startswith(prefix):
                    path_str = path_str[len(prefix):].lstrip('/')
                    break
            
            # Convert path to package name
            if path_str:
                package_name = path_str.replace('/', '.').replace('\\', '.')
                # Add class name
                class_name = filepath.stem
                return f"{package_name}.{class_name}" if package_name else class_name
            else:
                return filepath.stem
        except Exception:
            return filepath.stem
