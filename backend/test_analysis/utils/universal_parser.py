"""
Universal test file parser (Tree-sitter first, then regex/plugins).

Languages: Python, Java, JavaScript, TypeScript/TSX, C, C++.
- Merges Tree-sitter + regex for C/C++ (GTest macros + void test_*).
- Regex/plugin layer when TS finds no tests (other languages).
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
    '.c':    'c',
    '.h':    'c',
    '.cpp':  'cpp',
    '.cc':   'cpp',
    '.cxx':  'cpp',
    '.hpp':  'cpp',
    '.hh':   'cpp',
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
        # test.each / it.each — chained title: .each(...)( 'row case' ,
        (
            re.compile(
                r"(?:it|test)\.each\s*\([^;]{0,4000}?\)\s*\(\s*['\"`]([^'\"`]+)['\"`]",
                re.MULTILINE | re.DOTALL,
            ),
            1,
        ),
    ],
    'typescript': [
        # Same as JavaScript
        (re.compile(r"(?:^|\s)(?:it|test)\s*\(\s*['\"`]([^'\"` ][^'\"` ]*)['\"`]", re.MULTILINE), 1),
        (re.compile(r"(?:^|\s)describe\s*\(\s*['\"`]([^'\"` ][^'\"` ]*)['\"`]", re.MULTILINE), 1),
        (
            re.compile(
                r"(?:it|test)\.each\s*\([^;]{0,4000}?\)\s*\(\s*['\"`]([^'\"`]+)['\"`]",
                re.MULTILINE | re.DOTALL,
            ),
            1,
        ),
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
    'c': [
        (re.compile(r'^\s*void\s+(test_\w+)\s*\(', re.MULTILINE), 1),
    ],
    'cpp': [
        (re.compile(r'TEST\s*\(\s*\w+\s*,\s*(\w+)\s*\)', re.MULTILINE), 1),
        (re.compile(r'TEST_F\s*\(\s*\w+\s*,\s*(\w+)\s*\)', re.MULTILINE), 1),
        (re.compile(r'TEST_P\s*\(\s*\w+\s*,\s*(\w+)\s*\)', re.MULTILINE), 1),
        (re.compile(r'FRIEND_TEST\s*\(\s*\w+\s*,\s*(\w+)\s*\)', re.MULTILINE), 1),
        (re.compile(r'TYPED_TEST\s*\(\s*\w+\s*,\s*(\w+)\s*\)', re.MULTILINE), 1),
        (re.compile(r'TYPED_TEST_P\s*\(\s*\w+\s*,\s*(\w+)\s*\)', re.MULTILINE), 1),
        (re.compile(r'^\s*(?:static\s+)?(?:inline\s+)?void\s+(test_\w+)\s*\(', re.MULTILINE), 1),
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
    'c': [
        (re.compile(r'^\s*void\s+(test_\w+)\s*\(', re.MULTILINE), 1),
    ],
    'cpp': [
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
    'c': [
        (re.compile(r'^\s*#include\s+[<"]([^>"]+)[>"]', re.MULTILINE), 1),
    ],
    'cpp': [
        (re.compile(r'^\s*#include\s+[<"]([^>"]+)[>"]', re.MULTILINE), 1),
        (re.compile(r'^import\s+([\w.]+)\s*;', re.MULTILINE), 1),
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
    'vitest':    [r"from 'vitest'", r"import\s*\{[^}]*\}\s*from\s*['\"]vitest['\"]", r'vi\.mock\('],
    'mocha':     [r"from 'mocha'", r"require\('mocha'\)", r"require\('chai'\)"],
    'jasmine':   [r'jasmine\.', r"require\('jasmine'\)"],
    'rspec':     [r'require .rspec', r'RSpec\.describe', r'describe.*do'],
    'go_test':   [r'testing\.T', r'func Test'],
    'nunit':     [r'\[TestFixture\]', r'\[Test\]', r'using NUnit'],
    'xunit':     [r'\[Fact\]', r'\[Theory\]', r'using Xunit'],
    'gtest':     [r'#include\s*[<"]gtest/', r'TEST\s*\(', r'TEST_F\s*\(', r'INSTANTIATE_TEST_SUITE_P'],
}


class UniversalTestParser:
    """
    Language-agnostic test file parser.
    Uses Tree-sitter when available, regex fallback always guaranteed.
    """

    def __init__(self):
        from test_analysis.core.parsers.treesitter_core import get_treesitter_parsers
        self._ts_parsers = get_treesitter_parsers()

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

        ts_lang = self._treesitter_language_key(filepath, language)
        used_ts = False
        ts_result = {'test_methods': [], 'test_classes': [], 'imports': []}

        # 1) Tree-sitter (primary) — always capture imports/structure when grammar exists
        if ts_lang and ts_lang in self._ts_parsers:
            try:
                ts_result = self._parse_with_treesitter(
                    content, ts_lang, language, filepath
                )
                used_ts = True
                result['test_methods'] = list(ts_result['test_methods'])
                result['test_classes'] = list(ts_result['test_classes'])
                result['imports'] = list(ts_result['imports'])
                logger.debug(
                    f"Tree-sitter {filepath.name}: "
                    f"{len(result['test_methods'])} methods, "
                    f"{len(result['test_classes'])} classes, "
                    f"{len(result['imports'])} imports"
                )
            except Exception as e:
                logger.debug(f"Tree-sitter failed for {filepath.name}: {e}")

        # 2) Plugins when TS missed tests, or C/C++ (GTest macros need regex merge)
        from test_analysis.core.parsers.plugins import default_plugin_chain
        need_plugins = (
            not (result['test_methods'] or result['test_classes'])
            or language in ('c', 'cpp')
        )
        n_after_ts = len(result['test_methods']) + len(result['test_classes'])
        if need_plugins:
            for plugin_name, plugin_fn in default_plugin_chain():
                try:
                    plugin_result = plugin_fn(self, content, language, filepath) or {}
                    self._merge_parse_layer(result, plugin_result)
                except Exception as ex:
                    logger.debug(f"Plugin {plugin_name} failed: {ex}")

        n_final = len(result['test_methods']) + len(result['test_classes'])
        if n_final > 0:
            if used_ts and n_final > n_after_ts:
                result['parse_method'] = 'treesitter+regex'
            elif used_ts:
                result['parse_method'] = 'treesitter'
            else:
                result['parse_method'] = 'regex'
        else:
            result['parse_method'] = 'failed'

        if not result['test_methods'] and not result['test_classes']:
            logger.warning(
                f"No tests found in {filepath.name} (lang={language}). "
                f"File may not be a test file or patterns need updating."
            )

        return result

    def _merge_parse_layer(self, target: Dict, extra: Dict) -> None:
        """Merge plugin/secondary layer into target (dedupe by name + line)."""
        seen = {
            (m.get('name'), m.get('line_number'))
            for m in target.get('test_methods', [])
        }
        for m in extra.get('test_methods') or []:
            key = (m.get('name'), m.get('line_number'))
            if key not in seen:
                seen.add(key)
                target.setdefault('test_methods', []).append(dict(m))
        for c in extra.get('test_classes') or []:
            if c and c not in target.setdefault('test_classes', []):
                target['test_classes'].append(c)
        for imp in extra.get('imports') or []:
            if imp and imp not in target.setdefault('imports', []):
                target['imports'].append(imp)

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
                        'ruby': 'rspec', 'csharp': 'nunit', 'c': 'gtest', 'cpp': 'gtest'}
            return defaults.get(language, 'unknown')

        return max(scores, key=scores.get)

    def _treesitter_language_key(self, filepath: Path, language: str) -> Optional[str]:
        """Map logical language to Tree-sitter grammar key present in self._ts_parsers."""
        suf = filepath.suffix.lower()
        if language == 'typescript' and suf == '.tsx':
            return 'tsx' if 'tsx' in self._ts_parsers else (
                'typescript' if 'typescript' in self._ts_parsers else None
            )
        if language == 'typescript':
            return 'typescript' if 'typescript' in self._ts_parsers else None
        if language in ('c', 'cpp'):
            return language if language in self._ts_parsers else None
        return language if language in self._ts_parsers else None

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

    def _parse_with_treesitter(
        self, content: str, ts_lang: str, language: str, filepath: Path
    ) -> Dict:
        """Parse using Tree-sitter grammar ts_lang (may differ from logical language, e.g. tsx)."""
        parser = self._ts_parsers[ts_lang]
        tree = parser.parse(bytes(content, 'utf-8'))

        test_methods = []
        test_classes = []
        imports = []

        if ts_lang == 'python':
            test_methods, test_classes, imports = self._extract_python_ts(tree, content)
        elif ts_lang == 'java':
            test_methods, test_classes, imports = self._extract_java_ts(tree, content)
        elif ts_lang in ('javascript', 'typescript', 'tsx'):
            test_methods, test_classes, imports = self._extract_js_ts(tree, content)
        elif ts_lang == 'c':
            test_methods, test_classes, imports = self._extract_c_ts(tree, content)
        elif ts_lang == 'cpp':
            test_methods, test_classes, imports = self._extract_cpp_ts(tree, content)

        return {'test_methods': test_methods, 'test_classes': test_classes, 'imports': imports}

    def _find_enclosing_class(self, content: str, pos: int, language: str) -> Optional[str]:
        """Find the class name that encloses a given position in the file."""
        # Look backwards from pos for a class definition
        content_before = content[:pos]
        if language == 'python':
            matches = list(re.finditer(r'^\s*class\s+(\w+)', content_before, re.MULTILINE))
        elif language == 'java':
            matches = list(re.finditer(r'(?:public\s+)?class\s+(\w+)', content_before))
        elif language in ('javascript', 'typescript', 'c', 'cpp'):
            matches = list(re.finditer(r'describe\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', content_before))
        else:
            return None

        if matches:
            return matches[-1].group(1)
        return None

    # ── Tree-sitter extraction helpers ──────────────────────────────────────

    def _extract_python_ts(self, tree, content: str):
        """Extract from Python Tree-sitter AST (pytest/unittest: class + test_*)."""
        test_methods, test_classes, imports = [], [], []
        class_stack = []

        def walk(node):
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    if 'test' in class_name.lower() or 'testcase' in class_name.lower():
                        test_classes.append(class_name)
                    class_stack.append(class_name)
                    for child in node.children:
                        walk(child)
                    class_stack.pop()
                    return
            elif node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = content[name_node.start_byte:name_node.end_byte]
                    if func_name.startswith('test'):
                        enclosing = class_stack[-1] if class_stack else None
                        test_methods.append({
                            'name': func_name,
                            'class_name': enclosing,
                            'line_number': node.start_point[0] + 1
                        })
            elif node.type in ('import_statement', 'import_from_statement'):
                imports.append(content[node.start_byte:node.end_byte].strip())
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return test_methods, test_classes, imports

    def _extract_java_ts(self, tree, content: str):
        """Extract from Java Tree-sitter AST (nested classes, JUnit 4/5)."""
        test_methods, test_classes, imports = [], [], []
        class_stack: List[str] = []

        def walk(node):
            if node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    if 'test' in class_name.lower():
                        test_classes.append(class_name)
                    class_stack.append(class_name)
                    for child in node.children:
                        walk(child)
                    class_stack.pop()
                    return
            elif node.type == 'method_declaration':
                # Check for @Test annotation in modifiers
                has_test = False
                for child in node.children:
                    if child.type == 'modifiers':
                        modifiers_text = content[child.start_byte:child.end_byte]
                        if any(
                            x in modifiers_text
                            for x in (
                                '@Test',
                                '@ParameterizedTest',
                                '@RepeatedTest',
                                '@org.junit',
                                '@org.junit.jupiter.api.Test',
                            )
                        ):
                            has_test = True
                            break
                if has_test:
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        test_methods.append({
                            'name': content[name_node.start_byte:name_node.end_byte],
                            'class_name': class_stack[-1] if class_stack else None,
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
                                'class_name': class_stack[-1] if class_stack else None,
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

    @staticmethod
    def _js_call_base_name(func_node, content: str) -> str:
        """Resolve it / test / describe from it.only, test.skip, etc."""
        if func_node is None:
            return ''
        if func_node.type == 'identifier':
            return content[func_node.start_byte : func_node.end_byte]
        if func_node.type == 'member_expression':
            obj = func_node.child_by_field_name('object')
            return UniversalTestParser._js_call_base_name(obj, content)
        return ''

    def _js_first_test_name_arg(self, args_node, content: str) -> Optional[str]:
        """First string/template argument to it('...') / describe('...')."""
        if not args_node:
            return None
        for c in args_node.children:
            if c.type in ('(', ')', ','):
                continue
            if c.type == 'string':
                raw = content[c.start_byte : c.end_byte]
                return raw.strip("'\"`") or None
            if c.type == 'template_string':
                raw = content[c.start_byte : c.end_byte]
                return re.sub(r'^`+|`+$', '', raw).strip() or raw.strip('`')
        return None

    def _extract_js_ts(self, tree, content: str):
        """Jest/Vitest/Mocha: it/test/describe (+ .only/.skip); suite = enclosing describe."""
        test_methods, test_classes, imports = [], [], []

        def walk(node, suite_stack: List[str]):
            if node.type == 'call_expression':
                func_node = node.child_by_field_name('function')
                # test.each(a)( 'title', fn ) / it.each`...` patterns: outer call
                if func_node and func_node.type == 'call_expression':
                    inner_f = func_node.child_by_field_name('function')
                    if inner_f and inner_f.type == 'member_expression':
                        prop = inner_f.child_by_field_name('property')
                        obj = inner_f.child_by_field_name('object')
                        prop_txt = (
                            content[prop.start_byte : prop.end_byte] if prop else ''
                        )
                        obj_base = (
                            self._js_call_base_name(obj, content) if obj else ''
                        )
                        if prop_txt == 'each' and obj_base in ('it', 'test'):
                            outer_args = node.child_by_field_name('arguments')
                            tname = self._js_first_test_name_arg(
                                outer_args, content
                            )
                            if tname:
                                test_methods.append({
                                    'name': tname,
                                    'class_name': suite_stack[-1]
                                    if suite_stack
                                    else None,
                                    'line_number': node.start_point[0] + 1,
                                })
                base = self._js_call_base_name(func_node, content)
                args = node.child_by_field_name('arguments')
                if base in ('describe', 'fdescribe') and args:
                    name = self._js_first_test_name_arg(args, content)
                    if name:
                        test_classes.append(name)
                        new_stack = suite_stack + [name]
                        for c in args.children:
                            if c.type in (
                                'arrow_function',
                                'function',
                                'function_expression',
                            ):
                                body = c.child_by_field_name('body')
                                if body:
                                    for ch in body.children:
                                        walk(ch, new_stack)
                        return
                if base in (
                    'it',
                    'test',
                    'xit',
                    'xtest',
                    'fit',
                ) and args:
                    name = self._js_first_test_name_arg(args, content)
                    if name:
                        test_methods.append({
                            'name': name,
                            'class_name': suite_stack[-1] if suite_stack else None,
                            'line_number': node.start_point[0] + 1,
                        })
            elif node.type in ('import_statement', 'import_declaration'):
                imports.append(content[node.start_byte:node.end_byte].strip())
            for child in node.children:
                walk(child, suite_stack)

        walk(tree.root_node, [])
        return test_methods, test_classes, imports

    def _c_function_identifier(self, node, content: str) -> Optional[str]:
        """First function name identifier under a function_definition."""
        if node.type != 'function_definition':
            return None

        def find_decl(n):
            for c in n.children:
                if c.type == 'function_declarator':
                    for d in c.children:
                        if d.type == 'identifier':
                            return content[d.start_byte : d.end_byte]
                    return find_decl(c)
                if c.type == 'pointer_declarator':
                    r = find_decl(c)
                    if r:
                        return r
            return None

        return find_decl(node)

    def _extract_c_ts(self, tree, content: str):
        """C: #include + void test_* functions (Tree-sitter)."""
        test_methods, test_classes, imports = [], [], []

        def walk(node):
            if node.type == 'preproc_include':
                txt = content[node.start_byte : node.end_byte].strip()
                if txt and txt not in imports:
                    imports.append(txt)
            elif node.type == 'function_definition':
                name = self._c_function_identifier(node, content)
                if name and name.startswith('test_'):
                    test_methods.append({
                        'name': name,
                        'class_name': None,
                        'line_number': node.start_point[0] + 1,
                    })
            for c in node.children:
                walk(c)

        walk(tree.root_node)
        return test_methods, test_classes, imports

    def _extract_cpp_ts(self, tree, content: str):
        """C++: includes + void test_* ; TS rarely sees GTEST macros — regex plugin fills TEST/TEST_F."""
        test_methods, test_classes, imports = [], [], []

        def walk(node):
            if node.type == 'preproc_include':
                txt = content[node.start_byte : node.end_byte].strip()
                if txt and txt not in imports:
                    imports.append(txt)
            elif node.type == 'using_declaration' or node.type == 'namespace_definition':
                pass
            elif node.type == 'function_definition':
                name = self._c_function_identifier(node, content)
                if name and (name.startswith('test_') or name.startswith('Test')):
                    test_methods.append({
                        'name': name,
                        'class_name': None,
                        'line_number': node.start_point[0] + 1,
                    })
            elif node.type in ('import_statement', 'using_declaration'):
                frag = content[node.start_byte : node.end_byte].strip()
                if frag and frag not in imports:
                    imports.append(frag)
            for c in node.children:
                walk(c)

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
