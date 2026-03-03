"""
JavaScript language parser implementation (minimal stub).

This is a minimal implementation that allows file scanning and basic operations.
Full AST parsing can be added later using libraries like esprima or babel.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional

from parsers.base import LanguageParser


class JavaScriptParser(LanguageParser):
    """JavaScript parser implementation (minimal stub)."""
    
    @property
    def language_name(self) -> str:
        """Return language name."""
        return "javascript"
    
    @property
    def file_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return ['.js', '.jsx']
    
    def can_parse(self, filepath: Path) -> bool:
        """Check if this parser can handle the file."""
        return filepath.suffix.lower() in ['.js', '.jsx']
    
    def parse_file(self, filepath: Path, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[Any]:
        """
        Parse a JavaScript file (stub - returns file content for now).
        
        TODO: Implement full AST parsing using esprima or babel.
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return {'content': f.read(), 'filepath': str(filepath)}
        except Exception:
            return None
    
    def extract_imports(self, ast: Any) -> Dict[str, List[str]]:
        """Extract imports from JavaScript AST (stub)."""
        if not ast or not isinstance(ast, dict):
            return {'imports': [], 'from_imports': [], 'all_imports': []}
        
        # TODO: Implement using regex or esprima
        imports = []
        content = ast.get('content', '')
        
        # Simple regex for require() and import statements
        import re
        require_pattern = r"require\(['\"]([^'\"]+)['\"]\)"
        import_pattern = r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"
        
        requires = re.findall(require_pattern, content)
        imports_found = re.findall(import_pattern, content)
        
        all_imports = list(set(requires + imports_found))
        
        return {
            'imports': all_imports,
            'from_imports': [],
            'all_imports': all_imports
        }
    
    def extract_classes(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract class definitions from JavaScript AST (stub)."""
        if not ast or not isinstance(ast, dict):
            return []
        
        # TODO: Implement using esprima
        classes = []
        content = ast.get('content', '')
        
        # Simple regex for class definitions
        import re
        class_pattern = r"class\s+(\w+)"
        matches = re.finditer(class_pattern, content)
        
        for match in matches:
            classes.append({
                'name': match.group(1),
                'line_number': content[:match.start()].count('\n') + 1,
                'methods': []
            })
        
        return classes
    
    def extract_functions(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract function definitions from JavaScript AST (stub)."""
        if not ast or not isinstance(ast, dict):
            return []
        
        # TODO: Implement using esprima
        functions = []
        content = ast.get('content', '')
        
        # Simple regex for function definitions
        import re
        func_pattern = r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\(|(\w+)\s*:\s*(?:async\s+)?function)"
        matches = re.finditer(func_pattern, content)
        
        for match in matches:
            func_name = match.group(1) or match.group(2) or match.group(3)
            if func_name:
                functions.append({
                    'name': func_name,
                    'line_number': content[:match.start()].count('\n') + 1,
                    'class_name': None,
                    'is_async': 'async' in match.group(0)
                })
        
        return functions
    
    def extract_test_methods(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract test methods from JavaScript AST."""
        if not ast or not isinstance(ast, dict):
            return []
        
        test_methods = []
        content = ast.get('content', '')
        
        import re
        
        # Pattern 1: test('name', ...) or it('name', ...)
        # Matches: test('test name', ...), it("test name", ...)
        # Also check for async keyword
        pattern1 = r"(?:test|it)\s*\(\s*['\"]([^'\"]+)['\"]"
        matches = re.finditer(pattern1, content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # Check if async - look for 'async' between test name and arrow function
            start_pos = match.end()
            # Look ahead up to 50 chars for 'async' keyword
            ahead_text = content[start_pos:start_pos+50]
            is_async = 'async' in ahead_text.lower()
            
            test_methods.append({
                'name': match.group(1),
                'class_name': None,
                'line_number': content[:match.start()].count('\n') + 1,
                'is_async': is_async
            })
        
        # Pattern 2: describe('suite', () => { ... })
        # DO NOT extract describe blocks - they are test suites, not tests
        # Only extract test() and it() calls
        
        return test_methods
    
    def extract_function_calls(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract function calls from JavaScript AST."""
        if not ast or not isinstance(ast, dict):
            return []
        
        test_function_calls = []
        content = ast.get('content', '')
        
        import re
        
        # Framework functions to exclude
        TEST_FRAMEWORK_FUNCTIONS = {
            'test', 'it', 'describe', 'beforeEach', 'afterEach', 'beforeAll', 'afterAll',
            'expect', 'assert', 'require', 'module', 'exports', 'console'
        }
        
        # Find all test() and it() calls - simpler approach
        # Match: test('name', ...) or it('name', ...)
        test_pattern = r"(?:test|it)\s*\(\s*['\"]([^'\"]+)['\"]"
        test_matches = list(re.finditer(test_pattern, content, re.IGNORECASE | re.MULTILINE))
        
        # For each test, find its body by looking for the arrow function
        test_bodies = []
        for match in test_matches:
            test_name = match.group(1)
            start_pos = match.end()
            
            # Look for arrow function start: => {
            arrow_match = re.search(r'=>\s*\{', content[start_pos:start_pos+50])
            if not arrow_match:
                continue
            
            body_start = start_pos + arrow_match.end()
            
            # Find matching closing brace
            brace_count = 1
            pos = body_start
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                pos += 1
            
            if brace_count == 0:
                test_body = content[body_start:pos-1]
                test_bodies.append((test_name, test_body, body_start))
        
        for test_name, test_body, test_start_pos in test_bodies:
            # Extract function calls from test body
            calls = []
            
            # Pattern 1: Direct function calls: functionName(...)
            func_call_pattern = r'\b(\w+)\s*\('
            func_matches = re.finditer(func_call_pattern, test_body)
            for func_match in func_matches:
                func_name = func_match.group(1)
                if func_name not in TEST_FRAMEWORK_FUNCTIONS and not func_name[0].islower() or func_name in ['createMockMessage', 'createMockUser', 'createMockSession']:
                    # Include camelCase function names that look like helper functions
                    if func_name not in TEST_FRAMEWORK_FUNCTIONS:
                        calls.append({
                            'function': func_name,
                            'object': None,
                            'type': 'direct',
                            'line_number': content[:test_start_pos + func_match.start()].count('\n') + 1
                        })
            
            # Pattern 2: Method calls: object.method(...)
            method_call_pattern = r'(\w+(?:\.\w+)+)\s*\('
            method_matches = re.finditer(method_call_pattern, test_body)
            for method_match in method_matches:
                full_call = method_match.group(1)
                parts = full_call.split('.')
                if len(parts) >= 2:
                    object_name = '.'.join(parts[:-1])
                    method_name = parts[-1]
                    if method_name not in TEST_FRAMEWORK_FUNCTIONS:
                        calls.append({
                            'function': method_name,
                            'object': object_name,
                            'type': 'method',
                            'line_number': content[:test_start_pos + method_match.start()].count('\n') + 1
                        })
            
            if calls:
                test_function_calls.append({
                    'test_method': test_name,
                    'calls': calls
                })
        
        return test_function_calls
    
    def extract_string_references(self, ast: Any) -> List[str]:
        """Extract string-based references from JavaScript AST (stub)."""
        # TODO: Implement
        return []
    
    def resolve_module_name(self, filepath: Path, project_root: Path) -> str:
        """Convert file path to module name (JavaScript style)."""
        try:
            relative_path = filepath.relative_to(project_root)
            # Remove extension and convert path separators
            module_name = str(relative_path.with_suffix('')).replace('\\', '/').replace('/', '.')
            # Remove leading dots
            module_name = module_name.lstrip('.')
            return module_name
        except Exception:
            return str(filepath.stem)
