"""
Universal test file parser.
Supports Python, Java, JavaScript, TypeScript via Tree-sitter + regex fallback.
Never silently drops a file — always returns best-effort results.
"""

import re
import ast
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Language detection by file extension
# ─────────────────────────────────────────────

LANGUAGE_BY_EXTENSION = {
    '.py':   'python',
    '.java': 'java',
    '.js':   'javascript',
    '.ts':   'typescript',
    '.tsx':  'typescript',
    '.jsx':  'javascript',
    '.kt':   'kotlin',
    '.rb':   'ruby',
    '.cs':   'csharp',
    '.go':   'go',
}

def detect_language(filepath: Path) -> str:
    """Detect language from file extension. Returns 'unknown' if not recognized."""
    return LANGUAGE_BY_EXTENSION.get(filepath.suffix.lower(), 'unknown')


# ─────────────────────────────────────────────
# Test method name patterns per language
# ─────────────────────────────────────────────

# Each entry: (regex_pattern, group_index_for_name)
TEST_METHOD_PATTERNS = {
    'python': [
        (re.compile(r'^\s*(?:async\s+)?def\s+(test\w+)\s*\(', re.MULTILINE), 1),
    ],
    'java': [
        # JUnit 4/5: @Test annotation before method
        (re.compile(r'@Test[^\n]*\n\s*(?:public\s+)?(?:void\s+|[\w<>]+\s+)(\w+)\s*\(', re.MULTILINE), 1),
        # TestNG: @Test annotation
        (re.compile(r'@Test\s*(?:\([^)]*\))?\s*\n?\s*(?:public\s+)?(?:void\s+)(test\w+)\s*\(', re.MULTILINE | re.IGNORECASE), 1),
        # Method names starting with test (JUnit 3 style)
        (re.compile(r'(?:public|protected)\s+void\s+(test\w+)\s*\(', re.MULTILINE), 1),
    ],
    'javascript': [
        # Jest/Jasmine: it('...') or test('...')
        (re.compile(r"(?:^|\s)(?:it|test)\s*\(\s*['\"`]([^'\"` ][^'\"` ]*)['\"`]", re.MULTILINE), 1),
        # describe blocks
        (re.compile(r"(?:^|\s)describe\s*\(\s*['\"`]([^'\"` ][^'\"` ]*)['\"`]", re.MULTILINE), 1),
    ],
    'typescript': [
        # Same as JavaScript
        (re.compile(r"(?:^|\s)(?:it|test)\s*\(\s*['\"`]([^'\"` ][^'\"` ]*)['\"`]", re.MULTILINE), 1),
        (re.compile(r"(?:^|\s)describe\s*\(\s*['\"`]([^'\"` ][^'\"` ]*)['\"`]", re.MULTILINE), 1),
    ],
    'kotlin': [
        (re.compile(r'@Test\s+fun\s+(test\w+)\s*\(', re.MULTILINE), 1),
        (re.compile(r'fun\s+(test\w+)\s*\(', re.MULTILINE), 1),
    ],
    'go': [
        (re.compile(r'func\s+(Test\w+)\s*\(\s*t\s+\*testing\.T\s*\)', re.MULTILINE), 1),
    ],
    'ruby': [
        (re.compile(r"(?:it|test)\s+['\"]([^'\"]+)['\"]", re.MULTILINE), 1),
        (re.compile(r'def\s+(test_\w+)', re.MULTILINE), 1),
    ],
    'csharp': [
        (re.compile(r'\[(?:Test|TestMethod|Fact|Theory)\]\s*\n?\s*(?:public\s+)?(?:void\s+|Task\s+|async\s+Task\s+)(\w+)\s*\(', re.MULTILINE), 1),
    ],
}

# Test class patterns per language
TEST_CLASS_PATTERNS = {
    'python': [
        (re.compile(r'^\s*class\s+(Test\w+|.*TestCase)\s*(?:\(|:)', re.MULTILINE), 1),
    ],
    'java': [
        # Class ending with Test, Tests, TestCase
        (re.compile(r'(?:public\s+)?class\s+(\w*[Tt]est\w*)\s*(?:extends|implements|\{)', re.MULTILINE), 1),
        # Any class with @Test methods inside (detected post-hoc)
    ],
    'javascript': [
        (re.compile(r"describe\s*\(\s*['\"`]([^'\"` ][^'\"` ]*)['\"`]", re.MULTILINE), 1),
    ],
    'typescript': [
        (re.compile(r"describe\s*\(\s*['\"`]([^'\"` ][^'\"` ]*)['\"`]", re.MULTILINE), 1),
    ],
    'kotlin': [
        (re.compile(r'class\s+(\w*[Tt]est\w*)\s*(?::|{)', re.MULTILINE), 1),
    ],
}

# Import patterns per language
IMPORT_PATTERNS = {
    'python': [
        (re.compile(r'^import\s+([\w.]+)', re.MULTILINE), 1),
        (re.compile(r'^from\s+([\w.]+)\s+import', re.MULTILINE), 1),
    ],
    'java': [
        (re.compile(r'^import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;', re.MULTILINE), 1),
    ],
    'javascript': [
        (re.compile(r"(?:import|require)\s*\(?['\"`]([@\w./\-]+)['\"`]", re.MULTILINE), 1),
    ],
    'typescript': [
        (re.compile(r"(?:import|require)\s*\(?['\"`]([@\w./\-]+)['\"`]", re.MULTILINE), 1),
    ],
    'kotlin': [
        (re.compile(r'^import\s+([\w.]+)', re.MULTILINE), 1),
    ],
    'csharp': [
        (re.compile(r'^using\s+([\w.]+)\s*;', re.MULTILINE), 1),
    ],
    'go': [
        (re.compile(r'"([\w./\-]+)"', re.MULTILINE), 1),
    ],
}

# Test framework detection patterns
FRAMEWORK_PATTERNS = {
    'pytest':    [r'import pytest', r'from pytest', r'@pytest\.mark', r'pytest\.fixture'],
    'unittest':  [r'import unittest', r'unittest\.TestCase', r'from unittest'],
    'junit':     [r'import org\.junit', r'@Test', r'import junit', r'@RunWith'],
    'junit5':    [r'import org\.junit\.jupiter', r'@ExtendWith', r'@BeforeEach', r'@AfterEach'],
    'testng':    [r'import org\.testng', r'@Test.*groups', r'testng\.xml'],
    'jest':      [r"from 'jest'", r"require\('jest'\)", r'describe\(', r'it\(', r'expect\('],
    'mocha':     [r"from 'mocha'", r"require\('mocha'\)", r"require\('chai'\)"],
    'jasmine':   [r'jasmine\.', r"require\('jasmine'\)"],
    'rspec':     [r'require .rspec', r'RSpec\.describe', r'describe.*do'],
    'go_test':   [r'testing\.T', r'func Test'],
    'nunit':     [r'\[TestFixture\]', r'\[Test\]', r'using NUnit'],
    'xunit':     [r'\[Fact\]', r'\[Theory\]', r'using Xunit'],
}


class UniversalTestParser:
    """
    Language-agnostic test file parser.
    Uses Tree-sitter when available, regex fallback always guaranteed.
    """

    def __init__(self):
        self._ts_parsers = {}
        self._init_treesitter()

    def _init_treesitter(self):
        """Initialize Tree-sitter parsers for available languages."""
        ts_languages = {
            'python':     ('tree_sitter_python',     'python'),
            'java':       ('tree_sitter_java',        'java'),
            'javascript': ('tree_sitter_javascript',  'javascript'),
            'typescript': ('tree_sitter_typescript',  'typescript'),
        }
        for lang, (module_name, lang_key) in ts_languages.items():
            try:
                import importlib
                mod = importlib.import_module(module_name)
                from tree_sitter import Language, Parser
                language = Language(mod.language())
                parser = Parser(language)
                self._ts_parsers[lang] = parser
                logger.info(f"Tree-sitter parser loaded: {lang}")
            except Exception as e:
                logger.debug(f"Tree-sitter not available for {lang}, using regex fallback: {e}")

    def parse_file(self, filepath: Path) -> Dict:
        """
        Parse a test file and extract all relevant information.
        NEVER returns empty silently — always logs what happened.

        Returns:
            {
                'filepath': str,
                'language': str,
                'test_methods': [{'name': str, 'class_name': str|None, 'line_number': int|None}],
                'test_classes': [str],
                'imports': [str],
                'framework': str,
                'parse_method': 'treesitter' | 'regex' | 'failed'
            }
        """
        language = detect_language(filepath)
        result = {
            'filepath': str(filepath),
            'language': language,
            'test_methods': [],
            'test_classes': [],
            'imports': [],
            'framework': 'unknown',
            'parse_method': 'failed',
            'error': None,
        }

        try:
            content = filepath.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            result['error'] = f"Cannot read file: {e}"
            logger.error(f"Cannot read {filepath}: {e}")
            return result

        # Detect framework from content
        result['framework'] = self._detect_framework(content, language)

        # Try Tree-sitter first, fall back to regex
        if language in self._ts_parsers:
            try:
                ts_result = self._parse_with_treesitter(content, language, filepath)
                if ts_result['test_methods'] or ts_result['test_classes']:
                    result.update(ts_result)
                    result['parse_method'] = 'treesitter'
                    logger.debug(f"Tree-sitter parsed {filepath.name}: "
                                 f"{len(result['test_methods'])} methods, "
                                 f"{len(result['test_classes'])} classes")
                    return result
                else:
                    logger.debug(f"Tree-sitter returned empty for {filepath.name}, trying regex")
            except Exception as e:
                logger.debug(f"Tree-sitter failed for {filepath.name}: {e}, using regex")

        # Regex fallback — always runs if Tree-sitter fails or returns empty
        regex_result = self._parse_with_regex(content, language, filepath)
        result.update(regex_result)
        result['parse_method'] = 'regex'

        logger.debug(f"Regex parsed {filepath.name}: "
                     f"{len(result['test_methods'])} methods, "
                     f"{len(result['test_classes'])} classes")

        if not result['test_methods'] and not result['test_classes']:
            logger.warning(f"No tests found in {filepath.name} (lang={language}). "
                           f"File may not be a test file or patterns need updating.")

        return result

    def _detect_framework(self, content: str, language: str) -> str:
        """Detect test framework from file content."""
        scores = {}
        for framework, patterns in FRAMEWORK_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, content, re.IGNORECASE))
            if score > 0:
                scores[framework] = score

        if not scores:
            # Language-based default
            defaults = {'python': 'pytest', 'java': 'junit', 'javascript': 'jest',
                        'typescript': 'jest', 'kotlin': 'junit5', 'go': 'go_test',
                        'ruby': 'rspec', 'csharp': 'nunit'}
            return defaults.get(language, 'unknown')

        return max(scores, key=scores.get)

    def _parse_with_regex(self, content: str, language: str, filepath: Path) -> Dict:
        """Parse test file using regex patterns."""
        test_methods = []
        test_classes = []
        imports = []

        # Extract test methods
        method_patterns = TEST_METHOD_PATTERNS.get(language, [])
        for pattern, group_idx in method_patterns:
            for match in pattern.finditer(content):
                name = match.group(group_idx).strip()
                if name and name not in [m['name'] for m in test_methods]:
                    # Find line number
                    line_num = content[:match.start()].count('\n') + 1
                    # Try to find enclosing class
                    class_name = self._find_enclosing_class(content, match.start(), language)
                    test_methods.append({
                        'name': name,
                        'class_name': class_name,
                        'line_number': line_num
                    })

        # Extract test classes
        class_patterns = TEST_CLASS_PATTERNS.get(language, [])
        for pattern, group_idx in class_patterns:
            for match in pattern.finditer(content):
                name = match.group(group_idx).strip()
                if name and name not in test_classes:
                    test_classes.append(name)

        # For Java: if @Test annotations exist, find the class even if not named *Test
        if language == 'java' and test_methods and not test_classes:
            class_match = re.search(r'(?:public\s+)?class\s+(\w+)', content)
            if class_match:
                test_classes.append(class_match.group(1))

        # Extract imports
        import_patterns = IMPORT_PATTERNS.get(language, [])
        for pattern, group_idx in import_patterns:
            for match in pattern.finditer(content):
                imp = match.group(group_idx).strip()
                # Clean up imports
                if language == 'java':
                    imp = imp.rstrip(';').replace('.*', '')
                elif language in ('javascript', 'typescript'):
                    imp = imp.strip("'\"`")
                if imp and imp not in imports:
                    imports.append(imp)

        return {
            'test_methods': test_methods,
            'test_classes': test_classes,
            'imports': imports,
        }

    def _parse_with_treesitter(self, content: str, language: str, filepath: Path) -> Dict:
        """Parse using Tree-sitter — returns same structure as regex parser."""
        parser = self._ts_parsers[language]
        tree = parser.parse(bytes(content, 'utf-8'))

        test_methods = []
        test_classes = []
        imports = []

        if language == 'python':
            test_methods, test_classes, imports = self._extract_python_ts(tree, content)
        elif language == 'java':
            test_methods, test_classes, imports = self._extract_java_ts(tree, content)
        elif language in ('javascript', 'typescript'):
            test_methods, test_classes, imports = self._extract_js_ts(tree, content)

        return {'test_methods': test_methods, 'test_classes': test_classes, 'imports': imports}

    def _find_enclosing_class(self, content: str, pos: int, language: str) -> Optional[str]:
        """Find the class name that encloses a given position in the file."""
        # Look backwards from pos for a class definition
        content_before = content[:pos]
        if language == 'python':
            matches = list(re.finditer(r'^\s*class\s+(\w+)', content_before, re.MULTILINE))
        elif language == 'java':
            matches = list(re.finditer(r'(?:public\s+)?class\s+(\w+)', content_before))
        elif language in ('javascript', 'typescript'):
            matches = list(re.finditer(r'describe\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', content_before))
        else:
            return None

        if matches:
            return matches[-1].group(1)
        return None

    # ── Tree-sitter extraction helpers ──────────────────────────────────────

    def _extract_python_ts(self, tree, content: str):
        """Extract from Python Tree-sitter AST."""
        test_methods, test_classes, imports = [], [], []
        lines = content.split('\n')

        def walk(node):
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    if 'test' in class_name.lower() or 'testcase' in class_name.lower():
                        test_classes.append(class_name)
            elif node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = content[name_node.start_byte:name_node.end_byte]
                    if func_name.startswith('test'):
                        class_name = None  # simplified
                        test_methods.append({
                            'name': func_name,
                            'class_name': class_name,
                            'line_number': node.start_point[0] + 1
                        })
            elif node.type in ('import_statement', 'import_from_statement'):
                imports.append(content[node.start_byte:node.end_byte].strip())
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return test_methods, test_classes, imports

    def _extract_java_ts(self, tree, content: str):
        """Extract from Java Tree-sitter AST."""
        test_methods, test_classes, imports = [], []
        current_class = [None]  # Use list to allow modification in nested function

        def walk(node):
            if node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    # Track all classes (not just test classes) for method association
                    current_class[0] = class_name
                    if 'test' in class_name.lower():
                        test_classes.append(class_name)
                    # Recursively walk children to find methods in this class
                    for child in node.children:
                        walk(child)
                    # Reset class when exiting
                    current_class[0] = None
                return
            elif node.type == 'method_declaration':
                # Check for @Test annotation in modifiers
                has_test = False
                for child in node.children:
                    if child.type == 'modifiers':
                        modifiers_text = content[child.start_byte:child.end_byte]
                        if '@Test' in modifiers_text or '@org.junit' in modifiers_text:
                            has_test = True
                            break
                if has_test:
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        test_methods.append({
                            'name': content[name_node.start_byte:name_node.end_byte],
                            'class_name': current_class[0],  # Use tracked class name
                            'line_number': node.start_point[0] + 1
                        })
                else:
                    # JUnit 3: methods starting with 'test'
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        name = content[name_node.start_byte:name_node.end_byte]
                        if name.startswith('test'):
                            test_methods.append({
                                'name': name,
                                'class_name': current_class[0],  # Use tracked class name
                                'line_number': node.start_point[0] + 1
                            })
            elif node.type == 'import_declaration':
                # Extract the import statement and clean it
                import_text = content[node.start_byte:node.end_byte].strip().rstrip(';')
                # Extract just the package/class name (remove 'import' and 'static' keywords)
                import_match = re.search(r'import\s+(?:static\s+)?([\w.]+(?:\.[*])?)', import_text)
                if import_match:
                    import_name = import_match.group(1)
                    # Clean up: remove wildcard imports, keep base package
                    if import_name.endswith('.*'):
                        import_name = import_name[:-2]  # Remove .*
                    if import_name and import_name not in imports:
                        imports.append(import_name)
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return test_methods, test_classes, imports

    def _extract_js_ts(self, tree, content: str):
        """Extract from JavaScript/TypeScript Tree-sitter AST."""
        test_methods, test_classes, imports = [], [], []

        def walk(node):
            if node.type == 'call_expression':
                func_node = node.child_by_field_name('function')
                if func_node:
                    func_text = content[func_node.start_byte:func_node.end_byte]
                    if func_text in ('it', 'test', 'describe', 'xit', 'xtest'):
                        args = node.child_by_field_name('arguments')
                        if args and args.child_count > 0:
                            first_arg = args.children[1] if args.child_count > 1 else args.children[0]
                            if first_arg.type in ('string', 'template_string'):
                                name = content[first_arg.start_byte:first_arg.end_byte].strip("'\"` ")
                                if func_text == 'describe':
                                    test_classes.append(name)
                                else:
                                    test_methods.append({
                                        'name': name,
                                        'class_name': None,
                                        'line_number': node.start_point[0] + 1
                                    })
            elif node.type in ('import_statement', 'import_declaration'):
                imports.append(content[node.start_byte:node.end_byte].strip())
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return test_methods, test_classes, imports


# Global instance
_parser_instance = None

def get_parser() -> UniversalTestParser:
    """Get or create the global parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = UniversalTestParser()
    return _parser_instance
