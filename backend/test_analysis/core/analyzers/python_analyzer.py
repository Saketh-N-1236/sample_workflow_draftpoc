"""
Python test analyzer.

Analyzes Python test repositories.

analyze() now returns BOTH:
  - AnalyzerResult  (backward-compatible)
  - a LanguageResult stored on self.language_result after each analyze() call

Set the env var DEBUG_WRITE_JSON=true to also write the legacy 8 JSON files.
"""

from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
import json
import os
import re
import logging
import ast
from datetime import datetime

from .base_analyzer import BaseAnalyzer, AnalyzerResult

# Import existing utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from test_analysis.utils.file_scanner import scan_directory, get_file_metadata, group_files_by_category
from test_analysis.utils.universal_parser import UniversalTestParser, detect_language
from test_analysis.utils.dependency_plugins import get_registry
from test_analysis.engine.models import LanguageResult, TestRecord

logger = logging.getLogger(__name__)


class PythonAnalyzer(BaseAnalyzer):
    """Python test analyzer implementation."""
    
    def __init__(self):
        super().__init__(
            language='python',
            supported_frameworks=['pytest', 'unittest', 'nose']
        )
        self.parser = UniversalTestParser()
        self.dependency_plugin = get_registry().get_plugin('python')
        # Populated by analyze() — callers can read this directly
        self.language_result: Optional[LanguageResult] = None
    
    def analyze(self, repo_path: Path, output_dir: Path) -> AnalyzerResult:
        """
        Analyze Python repository.

        Always populates self.language_result with a LanguageResult.
        Writes JSON files to disk only when DEBUG_WRITE_JSON=true.
        Returns AnalyzerResult for backward compatibility.
        """
        self._ensure_output_dir(output_dir)
        self._log_progress("Starting Python analysis")
        
        errors = []
        repo_path = Path(repo_path).resolve()
        
        # Step 1: Scan test files
        self._log_progress("Scanning test files...")
        test_files = scan_directory(repo_path)
        if not test_files:
            errors.append("No Python test files found")
            return AnalyzerResult(
                language='python',
                framework='unknown',
                output_dir=output_dir,
                errors=errors
            )
        
        # Step 2: Detect framework
        self._log_progress("Detecting framework...")
        framework, confidence = self._detect_framework(test_files)
        
        # Step 3: Extract tests
        self._log_progress("Extracting tests...")
        tests, test_id_counter = self._extract_tests(test_files, repo_path, framework)
        
        # Step 4: Extract dependencies
        self._log_progress("Extracting dependencies...")
        dependencies = self._extract_dependencies(test_files, tests, repo_path)
        
        # Step 5: Extract function calls
        self._log_progress("Extracting function calls...")
        function_calls = self._extract_function_calls(test_files, tests, repo_path)
        
        # Step 6: Extract metadata
        self._log_progress("Extracting metadata...")
        metadata = self._extract_metadata(tests, test_files, repo_path)
        
        # Step 7: Build reverse index
        self._log_progress("Building reverse index...")
        reverse_index = self._build_reverse_index(dependencies, function_calls)
        
        # Step 8: Map test structure
        self._log_progress("Mapping test structure...")
        structure = self._map_test_structure(test_files, tests, repo_path)
        
        # Step 9: Extract Python-specific data
        self._log_progress("Extracting fixtures...")
        fixtures = self._extract_fixtures(test_files, tests, repo_path)
        
        self._log_progress("Extracting decorators...")
        decorators = self._extract_decorators(test_files, tests, repo_path)
        
        self._log_progress("Extracting async tests...")
        async_tests = self._extract_async_tests(tests, test_files, repo_path)

        # ── Build LanguageResult (in-memory, no disk I/O) ─────────────────
        test_records: List[TestRecord] = []
        for t in tests:
            class_label = t.get('class_name') or ''
            method_label = t.get('method_name', '')
            if class_label:
                full_name = f"{class_label} > {method_label}" if method_label else class_label
            else:
                full_name = method_label
            tr = TestRecord(
                id=t['test_id'],
                file=t['file_path'],
                describe=class_label,
                name=method_label,
                full_name=full_name,
                test_type=t.get('test_type', 'unit'),
                language='python',
                framework=framework,
                line_number=t.get('line_number'),
                repository_path=t.get('repository_path', str(repo_path)),
            )
            test_records.append(tr)

        # Attach test body content from metadata (same order as tests)
        for i, tr in enumerate(test_records):
            if i < len(metadata):
                tr.content = metadata[i].get('description', '') or ''

        self.language_result = LanguageResult(
            language='python',
            framework=framework,
            tests=test_records,
            reverse_index=reverse_index,
            function_mappings=function_calls,
            dependencies=dependencies,
            metadata=metadata,
            async_tests=async_tests or [],
            python_fixtures=fixtures or [],
            python_decorators=decorators or [],
            files_analyzed=len(test_files),
            errors=errors,
        )
        # ──────────────────────────────────────────────────────────────────

        # Write JSON files only when explicitly requested (debug mode)
        if os.environ.get('DEBUG_WRITE_JSON', '').lower() in ('1', 'true', 'yes'):
            self._write_outputs(
                output_dir, test_files, framework, confidence,
                tests, dependencies, function_calls, metadata,
                reverse_index, structure, repo_path,
                fixtures, decorators, async_tests
            )
        
        # Generate summary
        summary = self._generate_summary(
            test_files, tests, dependencies, reverse_index,
            metadata, framework, confidence, function_calls
        )
        
        self._log_progress(f"Analysis complete: {len(tests)} tests found")
        
        return AnalyzerResult(
            language='python',
            framework=framework,
            output_dir=output_dir,
            summary=summary,
            files_analyzed=len(test_files),
            tests_found=len(tests),
            errors=errors
        )
    
    def _detect_framework(self, test_files: List[Path]) -> tuple:
        """Detect test framework from imports and files."""
        votes = defaultdict(int)
        sample_size = min(50, len(test_files))
        
        for filepath in test_files[:sample_size]:
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                # Check for pytest
                if re.search(r'import\s+pytest|from\s+pytest|@pytest\.', content):
                    votes['pytest'] += 2
                
                # Check for unittest
                if re.search(r'import\s+unittest|from\s+unittest|unittest\.TestCase', content):
                    votes['unittest'] += 2
                
                # Check for conftest.py (pytest indicator)
                if filepath.name == 'conftest.py':
                    votes['pytest'] += 3
                
                # Check for pytest.ini
                if (filepath.parent / 'pytest.ini').exists():
                    votes['pytest'] += 3
            except Exception as e:
                logger.debug(f"Error reading {filepath}: {e}")
        
        if votes:
            framework = max(votes, key=votes.get)
            confidence = 'high' if votes[framework] >= 10 else 'medium' if votes[framework] >= 5 else 'low'
            return framework, confidence
        return 'pytest', 'low'
    
    def _extract_tests(self, test_files: List[Path], repo_path: Path, framework: str) -> tuple:
        """Extract test methods from files using universal parser."""
        tests = []
        test_id_counter = 1
        
        for filepath in test_files:
            try:
                parsed = self.parser.parse_file(filepath)
                if parsed.get('error'):
                    logger.warning(f"Error parsing {filepath}: {parsed['error']}")
                    continue
                
                # Determine test type from path
                test_type = self._get_test_type(filepath)
                
                for method_info in parsed.get('test_methods', []):
                    test_id_str = f"test_{test_id_counter:04d}"
                    test_id_counter += 1
                    
                    tests.append({
                        'test_id': test_id_str,
                        'file_path': str(filepath),
                        'class_name': method_info.get('class_name'),
                        'method_name': method_info['name'],
                        'test_type': test_type,
                        'language': 'python',
                        'repository_path': str(repo_path),
                        'line_number': method_info.get('line_number'),
                        'framework': framework,
                        'parse_method': parsed.get('parse_method', 'unknown'),
                    })
            except Exception as e:
                logger.warning(f"Error extracting tests from {filepath}: {e}")
        
        return tests, test_id_counter
    
    def _get_test_type(self, filepath: Path) -> str:
        """Get test type from file path."""
        path_str = str(filepath).lower()
        if 'integration' in path_str or '/integration/' in path_str:
            return 'integration'
        elif 'e2e' in path_str or 'end.to.end' in path_str or 'acceptance' in path_str:
            return 'e2e'
        return 'unit'
    
    def _extract_dependencies(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract dependencies using Python dependency plugin."""
        dependencies = []
        test_by_file = {t['file_path']: t for t in tests}
        
        for filepath in test_files:
            test = test_by_file.get(str(filepath))
            if not test:
                continue
            
            if not self.dependency_plugin:
                # Fallback to universal parser
                try:
                    parsed = self.parser.parse_file(filepath)
                    all_imports = parsed.get('imports', [])
                    production_imports = [
                        imp for imp in all_imports
                        if self._is_production_import(imp)
                    ]
                    
                    dependencies.append({
                        'test_id': test['test_id'],
                        'file_path': str(filepath),
                        'class_name': test.get('class_name', ''),
                        'method_name': test['method_name'],
                        'referenced_classes': sorted(set(production_imports)),
                        'reference_types': {imp: 'direct_import' for imp in production_imports},
                        'import_count': len(production_imports),
                    })
                except Exception as e:
                    logger.warning(f"Error extracting dependencies from {filepath}: {e}")
                continue
            
            try:
                deps = self.dependency_plugin.extract_dependencies(filepath)
                production_classes = deps.get('production_classes', [])
                all_refs = deps.get('all_production_references', [])
                
                dependencies.append({
                    'test_id': test['test_id'],
                    'file_path': str(filepath),
                    'class_name': test.get('class_name', ''),
                    'method_name': test['method_name'],
                    'referenced_classes': sorted(set(production_classes + all_refs)),
                    'reference_types': {ref: 'direct_import' for ref in all_refs},
                    'import_count': len(all_refs),
                })
            except Exception as e:
                logger.warning(f"Error extracting dependencies from {filepath}: {e}")
        
        return dependencies
    
    def _is_production_import(self, import_name: str) -> bool:
        """Check if import is production code."""
        import_lower = import_name.lower()
        test_keywords = {'pytest', 'unittest', 'mock', 'test', 'spec'}
        parts = import_lower.split('.')
        return not any(kw in parts for kw in test_keywords)
    
    def _extract_function_calls(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract function calls from test methods."""
        function_calls = []
        # Create a map of file_path -> list of tests in that file
        tests_by_file = defaultdict(list)
        for test in tests:
            file_path = test.get('file_path', '')
            if file_path:
                tests_by_file[file_path].append(test)
        
        # Import function call extraction utilities
        try:
            from test_analysis.utils.language_parser import parse_file, extract_function_calls
            has_extractor = True
        except ImportError:
            has_extractor = False
        
        for filepath in test_files:
            file_path_str = str(filepath)
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                continue
            
            try:
                calls_extracted = False
                if has_extractor:
                    # Parse file to get AST
                    tree = parse_file(filepath)
                    if tree:
                        # Extract function calls using AST
                        calls = extract_function_calls(tree, filepath)
                        if calls and len(calls) > 0:
                            calls_extracted = True
                            # Map calls to tests in this file
                            for call in calls:
                                # Try to match call to specific test method
                                test_method = call.get('test_method', '')
                                matched_test = None
                                for test in file_tests:
                                    if test.get('method_name') == test_method or not test_method:
                                        matched_test = test
                                        break
                                
                                # If no specific match, use first test in file
                                if not matched_test and file_tests:
                                    matched_test = file_tests[0]
                                
                                if matched_test:
                                    for func_call in call.get('calls', []):
                                        function_calls.append({
                                            'test_id': matched_test['test_id'],
                                            'file_path': file_path_str,
                                            'class_name': matched_test.get('class_name', ''),
                                            'method_name': matched_test['method_name'],
                                            'module_name': func_call.get('module', ''),
                                            'function_name': func_call.get('function', ''),
                                            'object_name': func_call.get('object', ''),
                                            'call_type': func_call.get('type', 'method'),
                                            'source': 'method_call',
                                            'line_number': func_call.get('line_number'),
                                        })
                
                # Always use fallback if AST extraction didn't work or returned no results
                if not calls_extracted:
                    # Simple fallback: extract basic function calls using regex
                    content = filepath.read_text(encoding='utf-8', errors='replace')
                    # Pattern for module.function() calls - improved to catch more patterns
                    patterns = [
                        re.compile(r'(\w+)\.(\w+)\s*\(', re.MULTILINE),  # obj.method()
                        re.compile(r'^(\w+)\s*\(', re.MULTILINE),  # function() at start of line
                    ]
                    
                    for pattern in patterns:
                        for match in pattern.finditer(content):
                            if pattern == patterns[0]:  # obj.method() pattern
                                module = match.group(1)
                                func = match.group(2)
                                # Skip test framework calls and common Python keywords
                                if module.lower() not in ['pytest', 'unittest', 'mock', 'assert', 'self', 'cls', 'os', 'sys', 'json', 'pathlib', 'typing', 'collections', 'datetime', 'logging', 're']:
                                    # Assign to all tests in file (since we can't determine which test)
                                    for test in file_tests:
                                        function_calls.append({
                                            'test_id': test['test_id'],
                                            'file_path': file_path_str,
                                            'class_name': test.get('class_name', ''),
                                            'method_name': test['method_name'],
                                            'module_name': module,
                                            'function_name': func,
                                            'object_name': module,
                                            'call_type': 'method',
                                            'source': 'method_call',
                                            'line_number': content[:match.start()].count('\n') + 1,
                                        })
                            else:  # function() pattern
                                func = match.group(1)
                                # Skip Python built-ins and test framework functions
                                if func.lower() not in ['print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'isinstance', 'type', 'hasattr', 'getattr', 'setattr', 'delattr', 'assert', 'raise', 'return', 'yield', 'pass', 'break', 'continue', 'import', 'from', 'def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally', 'with', 'as', 'lambda']:
                                    # Assign to all tests in file
                                    for test in file_tests:
                                        function_calls.append({
                                            'test_id': test['test_id'],
                                            'file_path': file_path_str,
                                            'class_name': test.get('class_name', ''),
                                            'method_name': test['method_name'],
                                            'module_name': '',
                                            'function_name': func,
                                            'object_name': '',
                                            'call_type': 'direct',
                                            'source': 'method_call',
                                            'line_number': content[:match.start()].count('\n') + 1,
                                        })
            except Exception as e:
                logger.warning(f"Error extracting function calls from {filepath}: {e}")
        
        return function_calls
    
    def _extract_test_content(self, filepath: Path, method_name: str, line_number: Optional[int]) -> str:
        """
        Extract test function body content from source file.
        
        Returns full function body including:
        - Setup code
        - Function calls
        - Assertions
        - Teardown code
        """
        if not filepath.exists() or not line_number:
            return ''
        
        try:
            content = filepath.read_text(encoding='utf-8', errors='replace')
            lines = content.split('\n')
            
            # Try using AST to find the function
            try:
                tree = ast.parse(content, filename=str(filepath))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name == method_name and node.lineno == line_number:
                            # Found the function, extract its body
                            # Get the source lines for this function
                            start_line = node.lineno - 1  # 0-indexed
                            # Find the end line by looking at the last statement
                            end_line = start_line
                            for stmt in ast.walk(node):
                                if hasattr(stmt, 'lineno') and stmt.lineno:
                                    end_line = max(end_line, stmt.lineno - 1)
                            
                            # Extract function body (from def to end)
                            # We need to find where the function actually ends
                            # Use indentation to determine function end
                            if start_line < len(lines):
                                func_start = lines[start_line]
                                # Find base indentation (spaces before 'def')
                                base_indent = len(func_start) - len(func_start.lstrip())
                                
                                # Find the end of the function by looking for next line with same or less indentation
                                end_line = start_line + 1
                                while end_line < len(lines):
                                    line = lines[end_line]
                                    if line.strip():  # Non-empty line
                                        line_indent = len(line) - len(line.lstrip())
                                        if line_indent <= base_indent and not line.strip().startswith('@'):
                                            # Found end of function
                                            break
                                    end_line += 1
                                
                                # Extract function body (including decorators and def line)
                                func_lines = lines[start_line:end_line]
                                return '\n'.join(func_lines)
            except (SyntaxError, ValueError) as e:
                logger.debug(f"AST parsing failed for {filepath}:{line_number}, using regex fallback: {e}")
            
            # Fallback: Use regex to find function
            # Pattern to match function definition
            func_pattern = re.compile(
                r'^(?:async\s+)?def\s+' + re.escape(method_name) + r'\s*\([^)]*\)\s*:',
                re.MULTILINE
            )
            
            match = func_pattern.search(content)
            if match:
                start_pos = match.start()
                start_line_num = content[:start_pos].count('\n')
                
                # Find the function's indentation level
                func_line = content[start_pos:content.find('\n', start_pos)]
                base_indent = len(func_line) - len(func_line.lstrip())
                
                # Find the end of the function
                lines = content.split('\n')
                end_line_num = start_line_num + 1
                
                while end_line_num < len(lines):
                    line = lines[end_line_num]
                    if line.strip():  # Non-empty line
                        line_indent = len(line) - len(line.lstrip())
                        if line_indent <= base_indent and not line.strip().startswith('@'):
                            break
                    end_line_num += 1
                
                # Extract function body
                func_lines = lines[start_line_num:end_line_num]
                return '\n'.join(func_lines)
            
        except Exception as e:
            logger.warning(f"Failed to extract test content from {filepath}:{line_number}: {e}")
        
        return ''
    
    def _extract_metadata(
        self, tests: List[Dict], test_files: List[Path], repo_path: Path
    ) -> List[Dict]:
        """Extract test metadata."""
        metadata = []
        content_extracted = 0
        content_failed = 0
        
        for test in tests:
            # Try to extract docstring/description
            description = ''
            test_content = ''
            try:
                filepath = Path(test['file_path'])
                if filepath.exists():
                    content = filepath.read_text(encoding='utf-8', errors='replace')
                    # Simple docstring extraction (could be improved)
                    docstring_match = re.search(
                        r'def\s+' + re.escape(test['method_name']) + r'[^:]*:\s*["\']{3}(.*?)["\']{3}',
                        content, re.DOTALL
                    )
                    if docstring_match:
                        description = docstring_match.group(1).strip()
                    
                    # Extract full test content (function body)
                    test_content = self._extract_test_content(
                        filepath,
                        test['method_name'],
                        test.get('line_number')
                    )
                    if test_content:
                        content_extracted += 1
                    else:
                        content_failed += 1
                else:
                    logger.warning(f"Test file does not exist: {test['file_path']}")
                    content_failed += 1
            except Exception as e:
                logger.warning(f"Error extracting metadata for {test.get('test_id')}: {e}", exc_info=True)
                content_failed += 1
            
            # Combine docstring and test content
            # If we have test content, use it; otherwise use just description
            if test_content:
                # Prepend docstring if exists, then add test content
                if description:
                    full_description = f"{description}\n\n--- Test Code ---\n{test_content}"
                else:
                    full_description = test_content
            else:
                full_description = description
            
            # Extract markers (pytest markers)
            markers = []
            try:
                filepath = Path(test['file_path'])
                if filepath.exists():
                    content = filepath.read_text(encoding='utf-8', errors='replace')
                    marker_pattern = re.compile(r'@pytest\.mark\.(\w+)', re.MULTILINE)
                    markers = marker_pattern.findall(content)
            except:
                pass
            
            metadata.append({
                'test_id': test['test_id'],
                'file_path': test['file_path'],
                'class_name': test.get('class_name', ''),
                'method_name': test['method_name'],
                'name': test['method_name'],
                'description': full_description,  # Now contains test content
                'markers': markers,
                'annotations': [],
                'is_async': 'async' in test.get('method_name', '') or 'async def' in str(test),
                'is_parameterized': False,  # Would need to check for @pytest.mark.parametrize
                'is_disabled': False,  # Would need to check for @pytest.mark.skip
                'pattern': 'test_prefix' if test['method_name'].startswith('test_') else 'annotation_based',
                'line_number': test.get('line_number'),
            })
        
        self._log_progress(f"Test content extraction: {content_extracted} succeeded, {content_failed} failed out of {len(tests)} tests")
        return metadata
    
    def _extract_fixtures(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract pytest fixtures from test files."""
        fixtures = []
        tests_by_file = defaultdict(list)
        for test in tests:
            file_path = test.get('file_path', '')
            if file_path:
                tests_by_file[file_path].append(test)
        
        # Fixture pattern: @pytest.fixture(...) or @fixture(...)
        fixture_pattern = re.compile(
            r'@(?:pytest\.)?fixture\s*(?:\(([^)]*)\))?\s*\n\s*'
            r'(?:async\s+)?def\s+(\w+)\s*\(',
            re.MULTILINE
        )
        
        for filepath in test_files:
            file_path_str = str(filepath)
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                for match in fixture_pattern.finditer(content):
                    fixture_args = match.group(1) or ''
                    fixture_name = match.group(2)
                    line_num = content[:match.start()].count('\n') + 1
                    
                    # Determine scope from args
                    scope = 'function'  # default
                    if 'scope=' in fixture_args:
                        scope_match = re.search(r'scope\s*=\s*["\'](\w+)["\']', fixture_args)
                        if scope_match:
                            scope = scope_match.group(1)
                    
                    # Determine if async
                    is_async = 'async def' in content[max(0, match.start()-50):match.end()]
                    fixture_type = 'async' if is_async else 'sync'
                    
                    # Assign to all tests in file (fixtures are file-level)
                    for test in file_tests:
                        fixtures.append({
                            'test_id': test['test_id'],
                            'fixture_name': fixture_name,
                            'fixture_scope': scope,
                            'fixture_type': fixture_type,
                        })
            except Exception as e:
                logger.warning(f"Error extracting fixtures from {filepath}: {e}")
        
        return fixtures
    
    def _extract_decorators(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract test decorators from test files."""
        decorators = []
        tests_by_file = defaultdict(list)
        for test in tests:
            file_path = test.get('file_path', '')
            if file_path:
                tests_by_file[file_path].append(test)
        
        # Decorator pattern: @decorator(...) or @decorator
        decorator_pattern = re.compile(
            r'@([\w.]+)\s*(?:\(([^)]*)\))?',
            re.MULTILINE
        )
        
        # Common test decorators
        test_decorators = {
            'pytest.mark.parametrize', 'pytest.mark.skip', 'pytest.mark.skipif',
            'pytest.mark.xfail', 'pytest.mark.timeout', 'pytest.mark.asyncio',
            'pytest.fixture', 'fixture', 'mock', 'patch', 'unittest.mock.patch',
            'pytest.mark.usefixtures', 'pytest.mark.filterwarnings',
        }
        
        for filepath in test_files:
            file_path_str = str(filepath)
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                # Find test methods and their decorators
                for test in file_tests:
                    method_name = test.get('method_name', '')
                    if method_name:
                        # Find the method in content
                        method_pattern = re.compile(
                            rf'(?:async\s+)?def\s+{re.escape(method_name)}\s*\([^)]*\)',
                            re.MULTILINE
                        )
                        method_match = method_pattern.search(content)
                        if method_match:
                            method_start = method_match.start()
                            # Look backwards for decorators
                            decorator_block = content[max(0, method_start - 500):method_start]
                            for match in decorator_pattern.finditer(decorator_block):
                                decorator_name = match.group(1)
                                decorator_args = match.group(2) if match.group(2) else ''
                                
                                # Only include test-related decorators
                                if any(d in decorator_name for d in test_decorators) or decorator_name.startswith('pytest.'):
                                    # Parse args if present
                                    args_dict = {}
                                    if decorator_args:
                                        # Simple parsing for common patterns
                                        if '=' in decorator_args:
                                            for part in decorator_args.split(','):
                                                if '=' in part:
                                                    key, val = part.split('=', 1)
                                                    args_dict[key.strip()] = val.strip().strip('"\'')
                                    
                                    decorators.append({
                                        'test_id': test['test_id'],
                                        'decorator_name': decorator_name,
                                        'decorator_args': args_dict if args_dict else {},
                                    })
            except Exception as e:
                logger.warning(f"Error extracting decorators from {filepath}: {e}")
        
        return decorators
    
    def _extract_async_tests(
        self, tests: List[Dict], test_files: List[Path], repo_path: Path
    ) -> List[Dict]:
        """Extract async test information."""
        async_tests = []
        
        for test in tests:
            file_path = test.get('file_path', '')
            if not file_path:
                continue
            
            try:
                filepath = Path(file_path)
                if not filepath.exists():
                    continue
                
                content = filepath.read_text(encoding='utf-8', errors='replace')
                method_name = test.get('method_name', '')
                
                if method_name:
                    # Check if method is async
                    async_pattern = re.compile(
                        rf'async\s+def\s+{re.escape(method_name)}\s*\(',
                        re.MULTILINE
                    )
                    is_async = bool(async_pattern.search(content))
                    
                    if is_async:
                        # Determine async pattern
                        async_pattern_type = 'pytest-asyncio'
                        if '@pytest.mark.asyncio' in content:
                            async_pattern_type = 'pytest-asyncio'
                        elif 'asyncio.run' in content or 'await' in content:
                            async_pattern_type = 'asyncio'
                        
                        async_tests.append({
                            'test_id': test['test_id'],
                            'is_async': True,
                            'async_pattern': async_pattern_type,
                        })
            except Exception as e:
                logger.warning(f"Error extracting async test info from {file_path}: {e}")
        
        return async_tests
    
    def _build_reverse_index(
        self, dependencies: List[Dict], function_calls: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Build reverse index from dependencies and function calls."""
        reverse_index = defaultdict(list)
        
        for dep in dependencies:
            for ref_class in dep.get('referenced_classes', []):
                reverse_index[ref_class].append({
                    'test_id': dep['test_id'],
                    'file_path': dep['file_path'],
                    'class_name': dep.get('class_name', ''),
                    'method_name': dep['method_name'],
                    'reference_type': dep['reference_types'].get(ref_class, 'direct_import'),
                })
        
        for call in function_calls:
            if call.get('module_name'):
                reverse_index[call['module_name']].append({
                    'test_id': call['test_id'],
                    'file_path': call['file_path'],
                    'class_name': call.get('class_name', ''),
                    'method_name': call['method_name'],
                    'reference_type': call.get('source', 'method_call'),
                })
        
        return dict(reverse_index)
    
    def _map_test_structure(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> Dict:
        """Map test repository structure."""
        from test_analysis.utils.file_scanner import _categorize_directory
        
        grouped = group_files_by_category(test_files)
        by_category = defaultdict(list)
        
        for test in tests:
            test_type = test.get('test_type', 'unit')
            by_category[test_type].append(test)
        
        # Count tests per category using the same categorization logic
        test_counts_by_category = defaultdict(int)
        for test in tests:
            test_file_path = Path(test['file_path'])
            category = _categorize_directory(test_file_path)
            test_counts_by_category[category] += 1
        
        structure = {
            'directory_structure': {
                'root_path': str(repo_path),
                'directories': {
                    cat: {
                        'file_count': len(files),
                        'test_count': test_counts_by_category.get(cat, 0),
                        'total_lines': sum(get_file_metadata(f).get('line_count', 0) for f in files),
                    }
                    for cat, files in grouped.items()
                    if len(files) > 0  # Only include categories with files
                },
                'files_by_directory': {
                    cat: [
                        {
                            'path': str(f.relative_to(repo_path)) if f.is_relative_to(repo_path) else str(f),
                            'name': f.name,
                            'line_count': get_file_metadata(f).get('line_count', 0),
                        }
                        for f in files
                    ]
                    for cat, files in grouped.items()
                    if len(files) > 0  # Only include categories with files
                },
            },
            'summary': {
                'total_directories': len([cat for cat, files in grouped.items() if len(files) > 0]),
                'total_files': len(test_files),
                'categories': [cat for cat, files in grouped.items() if len(files) > 0],
                'test_categories': [cat for cat, files in grouped.items() if len(files) > 0],
            },
        }
        
        return structure
    
    def _write_outputs(
        self, output_dir: Path, test_files: List[Path], framework: str, confidence: str,
        tests: List[Dict], dependencies: List[Dict], function_calls: List[Dict],
        metadata: List[Dict], reverse_index: Dict, structure: Dict, repo_path: Path,
        fixtures: List[Dict] = None, decorators: List[Dict] = None, async_tests: List[Dict] = None
    ):
        """Write all JSON output files (8 core + 3 Python-specific)."""
        now = datetime.now().isoformat()
        grouped = group_files_by_category(test_files)
        
        # 01_test_files.json
        file_metadata = [get_file_metadata(f) for f in test_files]
        self._write_json(output_dir / '01_test_files.json', {
            'generated_at': now,
            'data': {
                'scan_directory': str(repo_path),
                'total_files': len(test_files),
                'total_lines': sum(m.get('line_count', 0) for m in file_metadata),
                'total_size_bytes': sum(m.get('size_bytes', 0) for m in file_metadata),
                'categories': {cat: len(files) for cat, files in grouped.items()},
                'files': file_metadata,
            },
        })
        
        # 02_framework_detection.json
        self._write_json(output_dir / '02_framework_detection.json', {
            'generated_at': now,
            'data': {
                'primary_framework': framework,
                'framework': framework,
                'confidence': confidence,
                'evidence': [f'{framework} detected'],
            },
        })
        
        # 03_test_registry.json
        by_type = defaultdict(int)
        by_file = defaultdict(int)
        for test in tests:
            by_type[test.get('test_type', 'unit')] += 1
            by_file[test['file_path']] += 1
        
        self._write_json(output_dir / '03_test_registry.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(tests),
                'total_classes': len(set(t.get('class_name') for t in tests if t.get('class_name'))),
                'total_files': len(test_files),
                'tests_by_type': dict(by_type),
                'tests_by_file': dict(by_file),
                'tests': tests,
            },
        })
        
        # 04_static_dependencies.json
        total_refs = sum(d.get('import_count', 0) for d in dependencies)
        self._write_json(output_dir / '04_static_dependencies.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(dependencies),
                'tests_with_dependencies': sum(1 for d in dependencies if d.get('import_count', 0) > 0),
                'total_references': total_refs,
                'average_references_per_test': round(total_refs / len(dependencies), 2) if dependencies else 0,
                'test_dependencies': dependencies,
            },
        })
        
        # 04b_function_calls.json
        self._write_json(output_dir / '04b_function_calls.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(tests),
                'tests_with_function_calls': len(set(c['test_id'] for c in function_calls)),
                'total_mappings': len(function_calls),
                'average_mappings_per_test': round(len(function_calls) / len(tests), 2) if tests else 0,
                'test_function_mappings': function_calls,
            },
        })
        
        # 05_test_metadata.json
        self._write_json(output_dir / '05_test_metadata.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(metadata),
                'tests_with_descriptions': sum(1 for m in metadata if m.get('description')),
                'tests_with_markers': sum(1 for m in metadata if m.get('markers')),
                'async_tests': sum(1 for m in metadata if m.get('is_async')),
                'parameterized_tests': sum(1 for m in metadata if m.get('is_parameterized')),
                'disabled_tests': sum(1 for m in metadata if m.get('is_disabled')),
                'test_metadata': metadata,
            },
        })
        
        # 06_reverse_index.json
        total_mappings = sum(len(v) for v in reverse_index.values())
        self._write_json(output_dir / '06_reverse_index.json', {
            'generated_at': now,
            'data': {
                'total_production_classes': len(reverse_index),
                'total_mappings': total_mappings,
                'average_tests_per_class': round(total_mappings / len(reverse_index), 2) if reverse_index else 0,
                'reverse_index': {k: v for k, v in reverse_index.items()},
            },
        })
        
        # 07_test_structure.json
        self._write_json(output_dir / '07_test_structure.json', {
            'generated_at': now,
            'data': structure,
        })
        
        # 08_summary_report.json
        summary = self._generate_summary(
            test_files, tests, dependencies, reverse_index,
            metadata, framework, confidence, function_calls
        )
        self._write_json(output_dir / '08_summary_report.json', {
            'generated_at': now,
            'data': summary,
        })
        
        # 09_python_fixtures.json (Python-specific)
        if fixtures:
            self._write_json(output_dir / '09_python_fixtures.json', {
                'generated_at': now,
                'data': {
                    'total_fixtures': len(fixtures),
                    'tests_with_fixtures': len(set(f['test_id'] for f in fixtures)),
                    'fixtures': fixtures,
                },
            })
        
        # 10_python_decorators.json (Python-specific)
        if decorators:
            self._write_json(output_dir / '10_python_decorators.json', {
                'generated_at': now,
                'data': {
                    'total_decorators': len(decorators),
                    'tests_with_decorators': len(set(d['test_id'] for d in decorators)),
                    'decorators': decorators,
                },
            })
        
        # 11_python_async_tests.json (Python-specific)
        if async_tests:
            self._write_json(output_dir / '11_python_async_tests.json', {
                'generated_at': now,
                'data': {
                    'total_async_tests': len(async_tests),
                    'async_tests': async_tests,
                },
            })
    
    def _write_json(self, path: Path, data: Dict):
        """Write JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _generate_summary(
        self, test_files: List[Path], tests: List[Dict],
        dependencies: List[Dict], reverse_index: Dict,
        metadata: List[Dict], framework: str, confidence: str,
        function_calls: List[Dict] = None
    ) -> Dict:
        """Generate summary report."""
        total_prod_classes = len(reverse_index)
        total_deps = sum(d.get('import_count', 0) for d in dependencies)
        file_metadata = [get_file_metadata(f) for f in test_files]
        
        # Calculate tests_by_type
        by_type = defaultdict(int)
        for test in tests:
            by_type[test.get('test_type', 'unit')] += 1
        
        return {
            'test_repository_overview': {
                'total_test_files': len(test_files),
                'total_lines_of_code': sum(m.get('line_count', 0) for m in file_metadata),
                'test_framework': framework,
                'framework_confidence': confidence,
                'language': 'python',
            },
            'test_inventory': {
                'total_tests': len(tests),
                'total_test_classes': len(set(t.get('class_name') for t in tests if t.get('class_name'))),
                'tests_by_type': dict(by_type),
            },
            'dependencies': {
                'total_production_classes_referenced': total_prod_classes,
                'total_dependency_mappings': total_deps,
                'average_tests_per_class': round(len(tests) / total_prod_classes, 2) if total_prod_classes else 0,
                'tests_with_dependencies': sum(1 for d in dependencies if d.get('import_count', 0) > 0),
            },
            'metadata': {
                'tests_with_descriptions': sum(1 for m in metadata if m.get('description')),
                'tests_with_markers': sum(1 for m in metadata if m.get('markers')),
                'async_tests': sum(1 for m in metadata if m.get('is_async')),
                'parameterized_tests': sum(1 for m in metadata if m.get('is_parameterized')),
                'disabled_tests': sum(1 for m in metadata if m.get('is_disabled')),
            },
            'summary_for_db': {
                'files_analyzed': len(test_files),
                'functions_extracted': len(function_calls) if function_calls else 0,
                'modules_identified': len(set(
                    call.get('module_name') 
                    for call in (function_calls or [])
                    if call.get('module_name')
                )) or len(set(
                    dep.get('referenced_classes', [])[0].split('.')[0] 
                    for dep in dependencies 
                    if dep.get('referenced_classes') and len(dep.get('referenced_classes', [])) > 0
                )) if dependencies else 0,
                'test_files': len(test_files),
                'total_tests': len(tests),
                'total_test_classes': len(set(t.get('class_name') for t in tests if t.get('class_name'))),
                'total_test_methods': len(tests),
                'total_dependencies': total_deps,
                'total_production_classes': total_prod_classes,
                'tests_with_descriptions': sum(1 for m in metadata if m.get('description')),
                'framework': framework,
            },
        }
