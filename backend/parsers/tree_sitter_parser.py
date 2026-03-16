"""
Tree-sitter based language parser implementation.

Uses Tree-sitter for accurate, language-agnostic parsing.
Supports multiple languages through Tree-sitter grammars.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

try:
    import tree_sitter
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = None
    Parser = None

from parsers.base import LanguageParser


class TreeSitterParser(LanguageParser):
    """
    Tree-sitter based parser that works for multiple languages.
    
    Uses Tree-sitter grammars for accurate parsing and provides
    language-specific extraction logic.
    """
    
    def __init__(self, language_name: str, file_extensions: List[str], grammar_path: Optional[str] = None):
        """
        Initialize Tree-sitter parser.
        
        Args:
            language_name: Language identifier (e.g., 'python', 'javascript')
            file_extensions: List of file extensions (e.g., ['.py'], ['.js', '.jsx'])
            grammar_path: Optional path to compiled grammar (.so file)
        """
        self._language_name = language_name
        self._file_extensions = file_extensions
        self._grammar_path = grammar_path
        self._parser = None
        self._language = None
        
        if TREE_SITTER_AVAILABLE:
            self._initialize_parser()
    
    def _initialize_parser(self):
        """Initialize Tree-sitter parser and language."""
        if not TREE_SITTER_AVAILABLE:
            return
        
        try:
            # Try to load language grammar from installed packages
            # tree-sitter-language packages return a PyCapsule that needs to be wrapped in Language()
            lang_capsule = self._load_language_grammar()
            
            if lang_capsule:
                # Wrap the PyCapsule in a Language object, then create Parser
                # The correct API: Language(capsule) -> Language object -> Parser(language)
                try:
                    self._language = Language(lang_capsule)
                    self._parser = Parser(self._language)
                except Exception as e:
                    print(f"Warning: Could not initialize Tree-sitter parser for {self._language_name}: {e}")
                    import traceback
                    print(f"  Error details: {traceback.format_exc()}")
        except Exception as e:
            print(f"Warning: Could not initialize Tree-sitter parser for {self._language_name}: {e}")
            import traceback
            print(f"  Error details: {traceback.format_exc()}")
    
    def _load_language_grammar(self):
        """Try to load language grammar from installed packages."""
        if not TREE_SITTER_AVAILABLE:
            return None
        
        try:
            # Try tree-sitter-language packages
            # These packages expose a language() function that returns a language object
            language_map = {
                'python': ('tree_sitter_python', 'language'),
                'javascript': ('tree_sitter_javascript', 'language'),
                'java': ('tree_sitter_java', 'language'),
                'typescript': ('tree_sitter_typescript', 'language'),
            }
            
            package_info = language_map.get(self._language_name)
            if package_info:
                package_name, attr_name = package_info
                # Try to import and get language function
                module = __import__(package_name, fromlist=[attr_name])
                if hasattr(module, attr_name):
                    language_func = getattr(module, attr_name)
                    # Call the function to get the language PyCapsule
                    # This PyCapsule needs to be wrapped in Language() before passing to Parser()
                    language_capsule = language_func()
                    return language_capsule
        except ImportError as e:
            print(f"Warning: Could not import {package_name} for {self._language_name}: {e}")
            print(f"  Install with: pip install {package_name}")
        except Exception as e:
            print(f"Warning: Could not load Tree-sitter grammar for {self._language_name}: {e}")
        
        return None
    
    @property
    def language_name(self) -> str:
        """Return language name."""
        return self._language_name
    
    @property
    def file_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return self._file_extensions
    
    def can_parse(self, filepath: Path) -> bool:
        """Check if this parser can handle the file."""
        return filepath.suffix.lower() in [ext.lower() for ext in self._file_extensions]
    
    def parse_file(self, filepath: Path, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[Any]:
        """
        Parse a file using Tree-sitter.
        
        Args:
            filepath: Path to the file to parse
            max_retries: Maximum retry attempts (for file locking issues)
            retry_delay: Delay between retries in seconds
        
        Returns:
            Tree-sitter tree object, or None if parsing fails
        """
        if not TREE_SITTER_AVAILABLE or not self._parser:
            return None
        
        import time
        
        for attempt in range(max_retries):
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Store source content for node text extraction
                self._source_content = content.encode('utf8')
                
                # Parse with Tree-sitter
                tree = self._parser.parse(self._source_content)
                return tree
            except PermissionError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                print(f"Warning: Could not read {filepath} after {max_retries} attempts: {e}")
                return None
            except Exception as e:
                print(f"Warning: Could not parse {filepath}: {e}")
                return None
        
        return None
    
    def extract_imports(self, ast: Any) -> Dict[str, List[str]]:
        """Extract imports from Tree-sitter AST."""
        if not ast:
            return {'imports': [], 'from_imports': [], 'all_imports': []}
        
        # Language-specific extraction logic
        if self._language_name == 'python':
            return self._extract_python_imports(ast)
        elif self._language_name == 'javascript':
            return self._extract_javascript_imports(ast)
        elif self._language_name == 'java':
            return self._extract_java_imports(ast)
        else:
            return {'imports': [], 'from_imports': [], 'all_imports': []}
    
    def extract_classes(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract class definitions from Tree-sitter AST."""
        if not ast:
            return []
        
        # Language-specific extraction logic
        if self._language_name == 'python':
            return self._extract_python_classes(ast)
        elif self._language_name == 'javascript':
            return self._extract_javascript_classes(ast)
        elif self._language_name == 'java':
            return self._extract_java_classes(ast)
        else:
            return []
    
    def extract_functions(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract function definitions from Tree-sitter AST."""
        if not ast:
            return []
        
        # Language-specific extraction logic
        if self._language_name == 'python':
            return self._extract_python_functions(ast)
        elif self._language_name == 'javascript':
            return self._extract_javascript_functions(ast)
        elif self._language_name == 'java':
            return self._extract_java_functions(ast)
        else:
            return []
    
    def extract_test_methods(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract test methods from Tree-sitter AST."""
        if not ast:
            return []
        
        # Language-specific extraction logic
        if self._language_name == 'python':
            return self._extract_python_test_methods(ast)
        elif self._language_name == 'javascript':
            return self._extract_javascript_test_methods(ast)
        elif self._language_name == 'java':
            return self._extract_java_test_methods(ast)
        else:
            return []
    
    def extract_function_calls(self, ast: Any) -> List[Dict[str, Any]]:
        """Extract function calls from Tree-sitter AST."""
        if not ast:
            return []
        
        # Language-specific extraction logic
        if self._language_name == 'python':
            return self._extract_python_function_calls(ast)
        elif self._language_name == 'javascript':
            return self._extract_javascript_function_calls(ast)
        elif self._language_name == 'java':
            return self._extract_java_function_calls(ast)
        else:
            return []
    
    def extract_string_references(self, ast: Any) -> List[str]:
        """Extract string-based references from Tree-sitter AST."""
        if not ast:
            return []
        
        # Language-specific extraction logic
        if self._language_name == 'python':
            return self._extract_python_string_references(ast)
        elif self._language_name == 'javascript':
            return self._extract_javascript_string_references(ast)
        elif self._language_name == 'java':
            return self._extract_java_string_references(ast)
        else:
            return []
    
    def resolve_module_name(self, filepath: Path, project_root: Path) -> str:
        """Convert file path to module name."""
        # Language-specific module resolution
        if self._language_name == 'python':
            return self._resolve_python_module(filepath, project_root)
        elif self._language_name == 'javascript':
            return self._resolve_javascript_module(filepath, project_root)
        elif self._language_name == 'java':
            return self._resolve_java_module(filepath, project_root)
        else:
            return str(filepath.stem)
    
    # Python-specific extraction methods
    def _extract_python_imports(self, tree) -> Dict[str, List[str]]:
        """Extract Python imports from Tree-sitter AST."""
        imports = []
        from_imports = []
        
        def traverse(node):
            if node.type == 'import_statement':
                # import X
                for child in node.children:
                    if child.type == 'dotted_name' or child.type == 'dotted_as_name':
                        name = self._get_node_text(node)
                        imports.append(name.split()[1] if 'import' in name else name)
            elif node.type == 'import_from_statement':
                # from X import Y
                module = None
                names = []
                for child in node.children:
                    if child.type == 'dotted_name':
                        module = self._get_node_text(child)
                    elif child.type == 'import_list':
                        for import_item in child.children:
                            if import_item.type == 'dotted_name' or import_item.type == 'aliased_import':
                                names.append(self._get_node_text(import_item).split(' as ')[0])
                if module:
                    from_imports.append((module, names))
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        
        all_imports = imports + [mod for mod, _ in from_imports]
        return {
            'imports': imports,
            'from_imports': from_imports,
            'all_imports': all_imports
        }
    
    def _extract_python_classes(self, tree) -> List[Dict[str, Any]]:
        """Extract Python classes from Tree-sitter AST, including their methods."""
        classes = []
        
        def traverse(node, current_class=None):
            if node.type == 'class_definition':
                name_node = None
                for child in node.children:
                    if child.type == 'identifier':
                        name_node = child
                        break
                
                if name_node:
                    class_name = self._get_node_text(name_node)
                    class_info = {
                        'name': class_name,
                        'line_number': node.start_point[0] + 1,
                        'methods': []
                    }
                    classes.append(class_info)
                    
                    # Traverse children to find methods within this class
                    for child in node.children:
                        if child.type == 'block':  # Class body
                            for block_child in child.children:
                                if block_child.type == 'function_definition':
                                    method_name_node = None
                                    for method_child in block_child.children:
                                        if method_child.type == 'identifier':
                                            method_name_node = method_child
                                            break
                                    
                                    if method_name_node:
                                        method_name = self._get_node_text(method_name_node)
                                        class_info['methods'].append(method_name)
                        elif child.type == 'function_definition':
                            # Direct function definition in class (less common)
                            method_name_node = None
                            for method_child in child.children:
                                if method_child.type == 'identifier':
                                    method_name_node = method_child
                                    break
                            
                            if method_name_node:
                                method_name = self._get_node_text(method_name_node)
                                class_info['methods'].append(method_name)
                else:
                    # Continue traversing children
                    for child in node.children:
                        traverse(child, current_class)
            else:
                # Continue traversing children
                for child in node.children:
                    traverse(child, current_class)
        
        traverse(tree.root_node)
        return classes
    
    def _extract_python_functions(self, tree) -> List[Dict[str, Any]]:
        """Extract Python functions from Tree-sitter AST."""
        functions = []
        
        def traverse(node):
            if node.type == 'function_definition':
                name_node = None
                is_async = False
                for child in node.children:
                    if child.type == 'identifier':
                        name_node = child
                    elif child.type == 'async':
                        is_async = True
                
                if name_node:
                    functions.append({
                        'name': self._get_node_text(name_node),
                        'line_number': node.start_point[0] + 1,
                        'class_name': None,  # Would need parent context
                        'is_async': is_async
                    })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return functions
    
    def _extract_python_test_methods(self, tree) -> List[Dict[str, Any]]:
        """Extract Python test methods from Tree-sitter AST."""
        test_methods = []
        
        def traverse(node):
            if node.type == 'function_definition':
                name_node = None
                for child in node.children:
                    if child.type == 'identifier':
                        name_node = child
                        break
                
                if name_node:
                    func_name = self._get_node_text(name_node)
                    if func_name.startswith('test_'):
                        test_methods.append({
                            'name': func_name,
                            'class_name': None,  # Would need parent context
                            'line_number': node.start_point[0] + 1,
                            'is_async': False
                        })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return test_methods
    
    def _extract_python_function_calls(self, tree) -> List[Dict[str, Any]]:
        """Extract Python function calls from Tree-sitter AST."""
        # Simplified - would need more complex traversal
        return []
    
    def _extract_python_string_references(self, tree) -> List[str]:
        """Extract string references from Python AST."""
        strings = []
        
        def traverse(node):
            if node.type == 'string':
                text = self._get_node_text(node)
                # Remove quotes
                text = text.strip('"\'').strip('"""').strip("'''")
                if '.' in text and len(text) > 3:  # Likely a module reference
                    strings.append(text)
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return strings
    
    def _resolve_python_module(self, filepath: Path, project_root: Path) -> str:
        """Resolve Python module name."""
        try:
            relative_path = filepath.relative_to(project_root)
            module_name = str(relative_path.with_suffix('')).replace('\\', '/').replace('/', '.')
            return module_name.lstrip('.')
        except Exception:
            return str(filepath.stem)
    
    # JavaScript-specific extraction methods
    def _extract_javascript_imports(self, tree) -> Dict[str, List[str]]:
        """Extract JavaScript imports from Tree-sitter AST."""
        imports = []
        from_imports = []
        
        def traverse(node):
            if node.type == 'import_statement':
                # import X from 'module' or import { X, Y } from 'module'
                source = None
                imported_names = []
                
                for child in node.children:
                    if child.type == 'string':
                        source = self._get_node_text(child).strip('"\'')
                    elif child.type == 'import_clause':
                        # Extract imported names
                        for import_child in child.children:
                            if import_child.type == 'identifier':
                                imported_names.append(self._get_node_text(import_child))
                            elif import_child.type == 'named_imports':
                                for named in import_child.children:
                                    if named.type == 'import_specifier' or named.type == 'identifier':
                                        name_text = self._get_node_text(named)
                                        if name_text and name_text not in ['{', '}']:
                                            imported_names.append(name_text)
                
                if source and source.strip():
                    imports.append(source)
                    if imported_names:
                        from_imports.append((source, imported_names))
            
            elif node.type == 'call_expression':
                # require('module')
                func_name = None
                module = None
                
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = self._get_node_text(child)
                    elif child.type == 'string':
                        module = self._get_node_text(child).strip('"\'')
                
                if func_name == 'require' and module and module.strip():
                    imports.append(module)
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        
        # Filter out empty strings
        imports = [imp for imp in imports if imp and imp.strip()]
        from_imports = [(mod, names) for mod, names in from_imports if mod and mod.strip()]
        
        return {
            'imports': imports,
            'from_imports': from_imports,
            'all_imports': imports
        }
    
    def _extract_javascript_classes(self, tree) -> List[Dict[str, Any]]:
        """Extract JavaScript classes from Tree-sitter AST."""
        classes = []
        
        def traverse(node):
            if node.type == 'class_declaration':
                name_node = None
                for child in node.children:
                    if child.type == 'class_heritage' or child.type == 'identifier':
                        if child.type == 'identifier':
                            name_node = child
                        break
                
                if name_node:
                    classes.append({
                        'name': self._get_node_text(name_node),
                        'line_number': node.start_point[0] + 1,
                        'methods': []
                    })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return classes
    
    def _extract_javascript_functions(self, tree) -> List[Dict[str, Any]]:
        """Extract JavaScript functions from Tree-sitter AST."""
        functions = []
        
        def traverse(node):
            if node.type in ['function_declaration', 'arrow_function', 'function_expression']:
                name = None
                is_async = False
                
                for child in node.children:
                    if child.type == 'identifier':
                        name = self._get_node_text(child)
                    elif child.type == 'async':
                        is_async = True
                
                if name:
                    functions.append({
                        'name': name,
                        'line_number': node.start_point[0] + 1,
                        'class_name': None,
                        'is_async': is_async
                    })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return functions
    
    def _extract_javascript_test_methods(self, tree) -> List[Dict[str, Any]]:
        """Extract JavaScript test methods from Tree-sitter AST."""
        test_methods = []
        
        def traverse(node):
            if node.type == 'call_expression':
                func_name = None
                test_name = None
                is_async = False
                
                # Check if parent is async function
                parent = node.parent
                while parent:
                    if parent.type == 'arrow_function' or parent.type == 'function_declaration':
                        # Check for async keyword
                        for sibling in parent.children:
                            if sibling.type == 'async':
                                is_async = True
                                break
                        break
                    parent = parent.parent
                
                # Extract function name and test name
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = self._get_node_text(child)
                    elif child.type == 'string' and func_name in ['test', 'it']:
                        test_name = self._get_node_text(child).strip('"\'')
                
                # Only extract test() and it(), NOT describe()
                if func_name in ['test', 'it'] and test_name:
                    test_methods.append({
                        'name': test_name,
                        'class_name': None,
                        'line_number': node.start_point[0] + 1,
                        'is_async': is_async
                    })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return test_methods
    
    def _extract_javascript_function_calls(self, tree) -> List[Dict[str, Any]]:
        """Extract JavaScript function calls from Tree-sitter AST."""
        test_function_calls = []
        test_contexts = []  # Stack of test contexts
        
        # Framework functions to exclude
        TEST_FRAMEWORK_FUNCTIONS = {
            'test', 'it', 'describe', 'beforeEach', 'afterEach', 'beforeAll', 'afterAll',
            'expect', 'assert', 'require', 'module', 'exports', 'console'
        }
        
        def traverse(node):
            # Detect test() or it() calls - push to context stack
            if node.type == 'call_expression':
                func_name = None
                test_name = None
                
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = self._get_node_text(child)
                    elif child.type == 'string' and func_name in ['test', 'it']:
                        test_name = self._get_node_text(child).strip('"\'')
                        if test_name:
                            test_contexts.append(test_name)
                            # Create entry for this test
                            test_entry = {
                                'test_method': test_name,
                                'calls': []
                            }
                            test_function_calls.append(test_entry)
                
                # Extract function calls within test context
                if test_contexts and func_name and func_name not in TEST_FRAMEWORK_FUNCTIONS:
                    current_test = test_contexts[-1]
                    object_name = None
                    call_type = 'direct'
                    actual_func_name = func_name
                    
                    # Check if it's a method call (obj.method())
                    if node.children and len(node.children) > 0:
                        first_child = node.children[0]
                        if first_child.type == 'member_expression':
                            # Extract object and method
                            parts = []
                            def get_member_parts(n):
                                for child in n.children:
                                    if child.type == 'identifier' or child.type == 'property_identifier':
                                        parts.append(self._get_node_text(child))
                                    elif child.type == 'member_expression':
                                        get_member_parts(child)
                            
                            get_member_parts(first_child)
                            if len(parts) >= 2:
                                object_name = '.'.join(parts[:-1])
                                actual_func_name = parts[-1]
                                call_type = 'method'
                            elif len(parts) == 1:
                                actual_func_name = parts[0]
                    
                    # Find test entry
                    test_entry = None
                    for entry in test_function_calls:
                        if entry['test_method'] == current_test:
                            test_entry = entry
                            break
                    
                    if test_entry:
                        test_entry['calls'].append({
                            'function': actual_func_name,
                            'object': object_name,
                            'type': call_type,
                            'line_number': node.start_point[0] + 1
                        })
            
            # Recursively traverse children
            for child in node.children:
                traverse(child)
            
            # Pop test context after traversing children (if we're exiting a test call)
            if node.type == 'call_expression':
                func_name = None
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = self._get_node_text(child)
                        break
                if func_name in ['test', 'it'] and test_contexts:
                    test_contexts.pop()
        
        if tree and tree.root_node:
            traverse(tree.root_node)
        return test_function_calls
    
    def _extract_javascript_string_references(self, tree) -> List[str]:
        """Extract string references from JavaScript AST."""
        strings = []
        
        def traverse(node):
            if node.type == 'string':
                text = self._get_node_text(node).strip('"\'')
                if '.' in text and len(text) > 3:
                    strings.append(text)
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return strings
    
    def _resolve_javascript_module(self, filepath: Path, project_root: Path) -> str:
        """Resolve JavaScript module name."""
        try:
            relative_path = filepath.relative_to(project_root)
            module_name = str(relative_path.with_suffix('')).replace('\\', '/').replace('/', '.')
            return module_name.lstrip('.')
        except Exception:
            return str(filepath.stem)
    
    # Java-specific extraction methods (stubs)
    def _extract_java_imports(self, tree) -> Dict[str, List[str]]:
        """Extract Java imports from Tree-sitter AST."""
        imports = []
        
        def traverse(node):
            if node.type == 'import_declaration':
                for child in node.children:
                    if child.type == 'scoped_identifier':
                        import_name = self._get_node_text(child)
                        imports.append(import_name)
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        
        return {
            'imports': imports,
            'from_imports': [],
            'all_imports': imports
        }
    
    def _extract_java_classes(self, tree) -> List[Dict[str, Any]]:
        """Extract Java classes from Tree-sitter AST."""
        classes = []
        
        def traverse(node):
            if node.type == 'class_declaration':
                for child in node.children:
                    if child.type == 'identifier':
                        classes.append({
                            'name': self._get_node_text(child),
                            'line_number': node.start_point[0] + 1,
                            'methods': []
                        })
                        break
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return classes
    
    def _extract_java_functions(self, tree) -> List[Dict[str, Any]]:
        """Extract Java methods from Tree-sitter AST."""
        functions = []
        
        def traverse(node):
            if node.type == 'method_declaration':
                for child in node.children:
                    if child.type == 'identifier':
                        functions.append({
                            'name': self._get_node_text(child),
                            'line_number': node.start_point[0] + 1,
                            'class_name': None,
                            'is_async': False
                        })
                        break
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return functions
    
    def _extract_java_test_methods(self, tree) -> List[Dict[str, Any]]:
        """Extract Java test methods from Tree-sitter AST."""
        test_methods = []
        
        def traverse(node):
            if node.type == 'method_declaration':
                has_test_annotation = False
                method_name = None
                
                for child in node.children:
                    if child.type == 'modifiers':
                        for mod in child.children:
                            if mod.type == 'annotation' and '@Test' in self._get_node_text(mod):
                                has_test_annotation = True
                    elif child.type == 'identifier':
                        method_name = self._get_node_text(child)
                
                if has_test_annotation and method_name:
                    test_methods.append({
                        'name': method_name,
                        'class_name': None,
                        'line_number': node.start_point[0] + 1,
                        'is_async': False
                    })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return test_methods
    
    def _extract_java_function_calls(self, tree) -> List[Dict[str, Any]]:
        """Extract Java method calls from Tree-sitter AST."""
        return []
    
    def _extract_java_string_references(self, tree) -> List[str]:
        """Extract string references from Java AST."""
        strings = []
        
        def traverse(node):
            if node.type == 'string_literal':
                text = self._get_node_text(node).strip('"')
                if '.' in text and len(text) > 3:
                    strings.append(text)
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return strings
    
    def _resolve_java_module(self, filepath: Path, project_root: Path) -> str:
        """Resolve Java package name."""
        try:
            relative_path = filepath.relative_to(project_root)
            path_str = str(relative_path.parent).replace('\\', '/')
            
            # Remove common source directory prefixes
            for prefix in ['src/main/java', 'src/test/java', 'src']:
                if path_str.startswith(prefix):
                    path_str = path_str[len(prefix):].lstrip('/')
                    break
            
            if path_str:
                package_name = path_str.replace('/', '.').replace('\\', '.')
                class_name = filepath.stem
                return f"{package_name}.{class_name}" if package_name else class_name
            else:
                return filepath.stem
        except Exception:
            return filepath.stem
    
    # Helper method
    def _get_node_text(self, node) -> str:
        """Get text content of a node."""
        if not node:
            return ""
        
        # Try to get text from node directly
        if hasattr(node, 'text'):
            if isinstance(node.text, bytes):
                return node.text.decode('utf8')
            return str(node.text)
        
        # Extract from source content using byte offsets
        if self._source_content and hasattr(node, 'start_byte') and hasattr(node, 'end_byte'):
            try:
                text = self._source_content[node.start_byte:node.end_byte].decode('utf8')
                return text
            except Exception:
                pass
        
        return ""
