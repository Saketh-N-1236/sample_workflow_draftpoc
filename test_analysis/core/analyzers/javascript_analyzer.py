"""
JavaScript/TypeScript test analyzer.

Analyzes JavaScript/TypeScript test repositories and produces all 8 JSON output files.
"""

from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
import json
import re
import logging
from datetime import datetime

from .base_analyzer import BaseAnalyzer, AnalyzerResult

# Import existing utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from test_analysis.utils.universal_parser import UniversalTestParser
from test_analysis.utils.dependency_plugins import get_registry

logger = logging.getLogger(__name__)

# JS/TS test file patterns
JS_TEST_PATTERNS = [
    re.compile(r'.*\.test\.(js|ts|jsx|tsx)$'),
    re.compile(r'.*\.spec\.(js|ts|jsx|tsx)$'),
    re.compile(r'.*test.*\.(js|ts|jsx|tsx)$'),
]

EXCLUDE_DIRS = {'node_modules', '.git', '.idea', '.vscode', 'dist', 'build', '.next', '.nuxt'}


class JavaScriptAnalyzer(BaseAnalyzer):
    """JavaScript/TypeScript test analyzer implementation."""
    
    def __init__(self):
        super().__init__(
            language='javascript',
            supported_frameworks=['jest', 'mocha', 'jasmine', 'vitest']
        )
        self.parser = UniversalTestParser()
        self.dependency_plugin = get_registry().get_plugin('javascript')
    
    def analyze(self, repo_path: Path, output_dir: Path) -> AnalyzerResult:
        """Analyze JavaScript/TypeScript repository and produce all 8 JSON files."""
        self._ensure_output_dir(output_dir)
        self._log_progress("Starting JavaScript/TypeScript analysis")
        
        errors = []
        repo_path = Path(repo_path).resolve()
        
        # Step 1: Scan test files
        self._log_progress("Scanning test files...")
        test_files = self._scan_test_files(repo_path)
        if not test_files:
            errors.append("No JavaScript/TypeScript test files found")
            return AnalyzerResult(
                language='javascript',
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
        
        # Step 9: Extract JavaScript-specific data
        self._log_progress("Extracting mocks...")
        mocks = self._extract_mocks(test_files, tests, repo_path)
        
        self._log_progress("Extracting async tests...")
        async_tests = self._extract_async_tests(tests, test_files, repo_path)
        
        # Write all JSON files
        self._write_outputs(
            output_dir, test_files, framework, confidence,
            tests, dependencies, function_calls, metadata,
            reverse_index, structure, repo_path,
            mocks, async_tests
        )
        
        # Generate summary
        summary = self._generate_summary(
            test_files, tests, dependencies, reverse_index,
            metadata, framework, confidence
        )
        
        self._log_progress(f"Analysis complete: {len(tests)} tests found")
        
        return AnalyzerResult(
            language='javascript',
            framework=framework,
            output_dir=output_dir,
            summary=summary,
            files_analyzed=len(test_files),
            tests_found=len(tests),
            errors=errors
        )
    
    def _scan_test_files(self, repo_path: Path) -> List[Path]:
        """Scan for JavaScript/TypeScript test files."""
        test_files = []
        for filepath in repo_path.rglob('*'):
            if not filepath.is_file():
                continue
            if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
                continue
            if filepath.suffix.lower() in ['.js', '.ts', '.jsx', '.tsx']:
                if any(pattern.match(filepath.name) for pattern in JS_TEST_PATTERNS):
                    test_files.append(filepath)
        return sorted(test_files)
    
    def _detect_framework(self, test_files: List[Path]) -> tuple:
        """Detect test framework from imports."""
        votes = defaultdict(int)
        sample_size = min(50, len(test_files))
        
        for filepath in test_files[:sample_size]:
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                # Check for Jest
                if re.search(r"import.*from\s+['\"]jest['\"]|require\s*\(\s*['\"]jest['\"]|describe\(|it\(|expect\(", content):
                    votes['jest'] += 2
                
                # Check for Mocha
                if re.search(r"import.*from\s+['\"]mocha['\"]|require\s*\(\s*['\"]mocha['\"]|describe\(", content):
                    votes['mocha'] += 2
                
                # Check for Jasmine
                if re.search(r"import.*from\s+['\"]jasmine['\"]|require\s*\(\s*['\"]jasmine['\"]", content):
                    votes['jasmine'] += 1
                
                # Check for Vitest
                if re.search(r"import.*from\s+['\"]vitest['\"]|require\s*\(\s*['\"]vitest['\"]", content):
                    votes['vitest'] += 2
            except Exception as e:
                logger.debug(f"Error reading {filepath}: {e}")
        
        if votes:
            framework = max(votes, key=votes.get)
            confidence = 'high' if votes[framework] >= 10 else 'medium' if votes[framework] >= 5 else 'low'
            return framework, confidence
        return 'jest', 'low'
    
    def _extract_tests(self, test_files: List[Path], repo_path: Path, framework: str) -> tuple:
        """Extract test methods from files."""
        tests = []
        test_id_counter = 1
        
        for filepath in test_files:
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                test_type = self._get_test_type(filepath)
                
                # Extract test functions (describe, it, test)
                test_pattern = re.compile(
                    r'(?:describe|it|test)\s*\([^,]*,\s*(?:async\s*)?(?:\([^)]*\)\s*)?=>',
                    re.MULTILINE
                )
                
                for match in test_pattern.finditer(content):
                    # Extract test name from describe/it/test call
                    before = content[:match.start()]
                    line_num = before.count('\n') + 1
                    
                    # Try to extract test name (handle both single and double quotes)
                    test_name_match = re.search(r"(?:describe|it|test)\s*\(['\"]([^'\"]+)['\"]", content[max(0, match.start()-100):match.start()])
                    test_name = test_name_match.group(1) if test_name_match else f"test_{test_id_counter}"
                    
                    test_id_str = f"test_{test_id_counter:04d}"
                    test_id_counter += 1
                    
                    tests.append({
                        'test_id': test_id_str,
                        'file_path': str(filepath),
                        'class_name': None,
                        'method_name': test_name,
                        'test_type': test_type,
                        'language': 'javascript',
                        'repository_path': str(repo_path),
                        'line_number': line_num,
                        'framework': framework,
                    })
            except Exception as e:
                logger.warning(f"Error extracting tests from {filepath}: {e}")
        
        return tests, test_id_counter
    
    def _get_test_type(self, filepath: Path) -> str:
        """Get test type from file path."""
        path_str = str(filepath).lower()
        if 'integration' in path_str:
            return 'integration'
        elif 'e2e' in path_str or 'end.to.end' in path_str:
            return 'e2e'
        return 'unit'
    
    def _extract_dependencies(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract dependencies."""
        dependencies = []
        test_by_file = {t['file_path']: t for t in tests}
        
        for filepath in test_files:
            test = test_by_file.get(str(filepath))
            if not test:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                # Extract imports
                import_pattern = re.compile(
                    r"(?:import|require)\s*(?:\([^)]*\))?\s*\(?['\"`]([@\w./\-]+)['\"`]",
                    re.MULTILINE
                )
                
                imports = []
                for match in import_pattern.finditer(content):
                    imp = match.group(1)
                    # Filter out test frameworks
                    if not any(fw in imp.lower() for fw in ['jest', 'mocha', 'jasmine', 'vitest', 'chai', 'sinon']):
                        imports.append(imp)
                
                dependencies.append({
                    'test_id': test['test_id'],
                    'file_path': str(filepath),
                    'class_name': test.get('class_name', ''),
                    'method_name': test['method_name'],
                    'referenced_classes': sorted(set(imports)),
                    'reference_types': {imp: 'direct_import' for imp in imports},
                    'import_count': len(imports),
                })
            except Exception as e:
                logger.warning(f"Error extracting dependencies from {filepath}: {e}")
        
        return dependencies
    
    def _extract_function_calls(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract function calls."""
        function_calls = []
        test_by_file = {t['file_path']: t for t in tests}
        
        for filepath in test_files:
            test = test_by_file.get(str(filepath))
            if not test:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                # Simple pattern for method calls
                pattern = re.compile(r'(\w+)\.(\w+)\s*\(', re.MULTILINE)
                for match in pattern.finditer(content):
                    obj = match.group(1)
                    func = match.group(2)
                    if obj.lower() not in ['expect', 'describe', 'it', 'test', 'jest', 'mock']:
                        function_calls.append({
                            'test_id': test['test_id'],
                            'file_path': str(filepath),
                            'class_name': test.get('class_name', ''),
                            'method_name': test['method_name'],
                            'module_name': obj,
                            'function_name': func,
                            'object_name': obj,
                            'call_type': 'method',
                            'source': 'method_call',
                            'line_number': content[:match.start()].count('\n') + 1,
                        })
            except Exception as e:
                logger.warning(f"Error extracting function calls from {filepath}: {e}")
        
        return function_calls
    
    def _extract_metadata(
        self, tests: List[Dict], test_files: List[Path], repo_path: Path
    ) -> List[Dict]:
        """Extract test metadata."""
        metadata = []
        for test in tests:
            metadata.append({
                'test_id': test['test_id'],
                'file_path': test['file_path'],
                'class_name': test.get('class_name', ''),
                'method_name': test['method_name'],
                'name': test['method_name'],
                'description': '',
                'markers': [],
                'annotations': [],
                'is_async': False,
                'is_parameterized': False,
                'is_disabled': False,
                'pattern': 'annotation_based',
                'line_number': test.get('line_number'),
            })
        return metadata
    
    def _extract_mocks(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract mock usage from test files."""
        mocks = []
        tests_by_file = defaultdict(list)
        for test in tests:
            file_path = test.get('file_path', '')
            if file_path:
                tests_by_file[file_path].append(test)
        
        # Mock patterns: jest.mock(), jest.fn(), sinon.mock(), etc.
        mock_patterns = [
            (r'jest\.mock\s*\(([^)]+)\)', 'jest.mock', 'module'),
            (r'jest\.fn\s*\(', 'jest.fn', None),
            (r'jest\.spyOn\s*\(([^)]+)\)', 'jest.spyOn', 'object'),
            (r'sinon\.mock\s*\(([^)]+)\)', 'sinon.mock', 'object'),
            (r'sinon\.stub\s*\(([^)]+)\)', 'sinon.stub', 'object'),
            (r'mock\(([^)]+)\)', 'mock', 'module'),
            (r'vi\.mock\s*\(([^)]+)\)', 'vi.mock', 'module'),  # Vitest
            (r'vi\.fn\s*\(', 'vi.fn', None),  # Vitest
        ]
        
        for filepath in test_files:
            file_path_str = str(filepath)
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                for pattern, mock_type, target_type in mock_patterns:
                    regex = re.compile(pattern, re.MULTILINE)
                    for match in regex.finditer(content):
                        line_num = content[:match.start()].count('\n') + 1
                        target_value = match.group(1) if match.lastindex and match.lastindex >= 1 else None
                        
                        # Try to extract mock implementation if present
                        mock_impl = None
                        if target_value:
                            # Look for arrow function or function after the mock call
                            after_match = content[match.end():match.end()+200]
                            if '=>' in after_match or 'function' in after_match:
                                mock_impl = after_match[:100].strip()
                        
                        for test in file_tests:
                            mock_data = {
                                'test_id': test['test_id'],
                                'mock_type': mock_type,
                                'line_number': line_num,
                            }
                            
                            if target_type == 'module' and target_value:
                                mock_data['mock_target'] = target_value.strip().strip('"\'')
                            elif target_type == 'object' and target_value:
                                mock_data['mock_target'] = target_value.strip().strip('"\'')
                            
                            if mock_impl:
                                mock_data['mock_implementation'] = mock_impl
                            
                            mocks.append(mock_data)
            except Exception as e:
                logger.warning(f"Error extracting mocks from {filepath}: {e}")
        
        return mocks
    
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
                    # Check if test is async (async function, async arrow, etc.)
                    async_patterns = [
                        rf'async\s+function\s+{re.escape(method_name)}',
                        rf'async\s+\([^)]*\)\s*=>',
                        rf'async\s+{re.escape(method_name)}\s*\(',
                    ]
                    
                    is_async = any(re.search(pattern, content, re.MULTILINE) for pattern in async_patterns)
                    
                    if is_async:
                        # Determine async pattern
                        async_pattern_type = 'async/await'
                        if 'done()' in content or 'done =>' in content:
                            async_pattern_type = 'callback'
                        elif 'Promise' in content:
                            async_pattern_type = 'promise'
                        
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
        """Build reverse index."""
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
        """Map test structure."""
        by_category = defaultdict(list)
        for test in tests:
            by_category[test.get('test_type', 'unit')].append(test)
        
        return {
            'directory_structure': {
                'root_path': str(repo_path),
                'directories': {
                    cat: {
                        'file_count': len(set(t['file_path'] for t in tests)),
                        'test_count': len(tests),
                        'total_lines': 0,
                    }
                    for cat, tests in by_category.items()
                },
            },
            'summary': {
                'total_directories': len(by_category),
                'total_files': len(test_files),
                'categories': list(by_category.keys()),
            },
        }
    
    def _write_outputs(
        self, output_dir: Path, test_files: List[Path], framework: str, confidence: str,
        tests: List[Dict], dependencies: List[Dict], function_calls: List[Dict],
        metadata: List[Dict], reverse_index: Dict, structure: Dict, repo_path: Path,
        mocks: List[Dict] = None, async_tests: List[Dict] = None
    ):
        """Write all JSON output files (8 core + 2 JavaScript-specific)."""
        now = datetime.now().isoformat()
        
        # Write all 8 files with same structure as other analyzers
        self._write_json(output_dir / '01_test_files.json', {
            'generated_at': now,
            'data': {
                'scan_directory': str(repo_path),
                'total_files': len(test_files),
                'total_lines': sum(self._count_lines(f) for f in test_files),
                'total_size_bytes': sum(f.stat().st_size for f in test_files if f.exists()),
                'categories': self._categorize_files(test_files),
                'files': [
                    {
                        'path': str(f),
                        'file_path': str(f),
                        'name': f.name,
                        'directory': self._get_category(f),
                        'line_count': self._count_lines(f),
                        'size_bytes': f.stat().st_size if f.exists() else 0,
                        'language': 'javascript',
                    }
                    for f in test_files
                ],
            },
        })
        
        self._write_json(output_dir / '02_framework_detection.json', {
            'generated_at': now,
            'data': {
                'primary_framework': framework,
                'framework': framework,
                'confidence': confidence,
                'evidence': [f'{framework} detected'],
            },
        })
        
        by_type = defaultdict(int)
        by_file = defaultdict(int)
        for test in tests:
            by_type[test.get('test_type', 'unit')] += 1
            by_file[test['file_path']] += 1
        
        self._write_json(output_dir / '03_test_registry.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(tests),
                'total_classes': 0,
                'total_files': len(test_files),
                'tests_by_type': dict(by_type),
                'tests_by_file': dict(by_file),
                'tests': tests,
            },
        })
        
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
        
        self._write_json(output_dir / '05_test_metadata.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(metadata),
                'tests_with_descriptions': sum(1 for m in metadata if m.get('description')),
                'tests_with_markers': sum(1 for m in metadata if m.get('markers')),
                'async_tests': 0,
                'parameterized_tests': 0,
                'disabled_tests': 0,
                'test_metadata': metadata,
            },
        })
        
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
        
        self._write_json(output_dir / '07_test_structure.json', {
            'generated_at': now,
            'data': structure,
        })
        
        summary = self._generate_summary(
            test_files, tests, dependencies, reverse_index,
            metadata, framework, confidence
        )
        self._write_json(output_dir / '08_summary_report.json', {
            'generated_at': now,
            'data': summary,
        })
        
        # 09_js_mocks.json (JavaScript-specific)
        if mocks:
            self._write_json(output_dir / '09_js_mocks.json', {
                'generated_at': now,
                'data': {
                    'total_mocks': len(mocks),
                    'tests_with_mocks': len(set(m['test_id'] for m in mocks)),
                    'mocks': mocks,
                },
            })
        
        # 10_js_async_tests.json (JavaScript-specific)
        if async_tests:
            self._write_json(output_dir / '10_js_async_tests.json', {
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
    
    def _count_lines(self, filepath: Path) -> int:
        """Count lines in file."""
        try:
            return len(filepath.read_text(encoding='utf-8', errors='replace').splitlines())
        except:
            return 0
    
    def _get_category(self, filepath: Path) -> str:
        """Get test category."""
        return self._get_test_type(filepath)
    
    def _categorize_files(self, test_files: List[Path]) -> Dict[str, int]:
        """Categorize files."""
        cats = defaultdict(int)
        for f in test_files:
            cats[self._get_category(f)] += 1
        return dict(cats)
    
    def _generate_summary(
        self, test_files: List[Path], tests: List[Dict],
        dependencies: List[Dict], reverse_index: Dict,
        metadata: List[Dict], framework: str, confidence: str
    ) -> Dict:
        """Generate summary."""
        total_prod_classes = len(reverse_index)
        total_deps = sum(d.get('import_count', 0) for d in dependencies)
        
        # Calculate tests_by_type
        by_type = defaultdict(int)
        for test in tests:
            by_type[test.get('test_type', 'unit')] += 1
        
        return {
            'test_repository_overview': {
                'total_test_files': len(test_files),
                'total_lines_of_code': sum(self._count_lines(f) for f in test_files),
                'test_framework': framework,
                'framework_confidence': confidence,
                'language': 'javascript',
            },
            'test_inventory': {
                'total_tests': len(tests),
                'total_test_classes': 0,
                'tests_by_type': dict(by_type),
            },
            'dependencies': {
                'total_production_classes_referenced': total_prod_classes,
                'total_dependency_mappings': total_deps,
                'average_tests_per_class': round(len(tests) / total_prod_classes, 2) if total_prod_classes else 0,
                'tests_with_dependencies': sum(1 for d in dependencies if d.get('import_count', 0) > 0),
            },
            'metadata': {
                'tests_with_descriptions': 0,
                'tests_with_markers': 0,
                'async_tests': 0,
                'parameterized_tests': 0,
                'disabled_tests': 0,
            },
            'summary_for_db': {
                'files_analyzed': len(test_files),
                'functions_extracted': 0,
                'modules_identified': 0,
                'test_files': len(test_files),
                'total_tests': len(tests),
                'total_test_classes': 0,
                'total_test_methods': len(tests),
                'total_dependencies': total_deps,
                'total_production_classes': total_prod_classes,
                'tests_with_descriptions': 0,
                'framework': framework,
            },
        }
