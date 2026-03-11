"""
Java test analyzer.

Analyzes Java test repositories and produces all 8 JSON output files.
Uses the Java dependency plugin for dependency extraction.
"""

from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
import json
import re
import logging
from datetime import datetime

from .base_analyzer import BaseAnalyzer, AnalyzerResult

# Import Java dependency plugin
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from test_analysis.utils.dependency_plugins import get_registry

logger = logging.getLogger(__name__)

# Java test file patterns
JAVA_TEST_PATTERNS = [
    re.compile(r'.*Test\.java$'),
    re.compile(r'.*Tests\.java$'),
    re.compile(r'.*TestCase\.java$'),
    re.compile(r'Test.*\.java$'),
]

# Test annotations
TEST_ANNOTATIONS = {
    'Test', 'ParameterizedTest', 'TestFactory', 'RepeatedTest',
    'org.junit.Test', 'org.junit.jupiter.api.Test',
    'org.testng.annotations.Test',
}

# Framework detection
FRAMEWORK_IMPORTS = {
    'junit5': ['org.junit.jupiter'],
    'junit4': ['org.junit'],
    'testng': ['org.testng'],
    'mockito': ['org.mockito'],
}

EXCLUDE_DIRS = {'target', 'build', '.git', '.gradle', '.mvn', 'node_modules', '.idea', '.vscode', 'bin', 'out'}


class JavaAnalyzer(BaseAnalyzer):
    """Java test analyzer implementation."""
    
    def __init__(self):
        super().__init__(
            language='java',
            supported_frameworks=['junit5', 'junit4', 'junit3', 'testng', 'mockito', 'spring']
        )
        self.dependency_plugin = get_registry().get_plugin('java')
    
    def analyze(self, repo_path: Path, output_dir: Path) -> AnalyzerResult:
        """Analyze Java repository and produce all 8 JSON files."""
        self._ensure_output_dir(output_dir)
        self._log_progress("Starting Java analysis")
        
        errors = []
        repo_path = Path(repo_path).resolve()
        
        # Step 1: Scan test files
        self._log_progress("Scanning test files...")
        test_files = self._scan_test_files(repo_path)
        if not test_files:
            errors.append("No Java test files found")
            return AnalyzerResult(
                language='java',
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
        
        # Step 9: Extract Java-specific data
        self._log_progress("Extracting reflection calls...")
        reflection_calls = self._extract_reflection_calls(test_files, tests, repo_path)
        
        self._log_progress("Extracting DI fields...")
        di_fields = self._extract_di_fields(test_files, tests, repo_path)
        
        self._log_progress("Extracting annotations...")
        annotations = self._extract_annotations(test_files, tests, repo_path)
        
        # Write all JSON files
        self._write_outputs(
            output_dir, test_files, framework, confidence,
            tests, dependencies, function_calls, metadata,
            reverse_index, structure, repo_path,
            reflection_calls, di_fields, annotations
        )
        
        # Generate summary
        summary = self._generate_summary(
            test_files, tests, dependencies, reverse_index,
            metadata, framework, confidence
        )
        
        self._log_progress(f"Analysis complete: {len(tests)} tests found")
        
        return AnalyzerResult(
            language='java',
            framework=framework,
            output_dir=output_dir,
            summary=summary,
            files_analyzed=len(test_files),
            tests_found=len(tests),
            errors=errors
        )
    
    def _scan_test_files(self, repo_path: Path) -> List[Path]:
        """Scan for Java test files."""
        test_files = []
        for filepath in repo_path.rglob('*.java'):
            if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
                continue
            if any(pattern.match(filepath.name) for pattern in JAVA_TEST_PATTERNS):
                test_files.append(filepath)
        return sorted(test_files)
    
    def _detect_framework(self, test_files: List[Path]) -> tuple:
        """Detect test framework from imports."""
        votes = defaultdict(int)
        sample_size = min(50, len(test_files))
        
        for filepath in test_files[:sample_size]:
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                for fw, imports in FRAMEWORK_IMPORTS.items():
                    for imp in imports:
                        if re.search(rf'import\s+{re.escape(imp)}', content):
                            votes[fw] += 1
            except Exception as e:
                logger.debug(f"Error reading {filepath}: {e}")
        
        if votes:
            framework = max(votes, key=votes.get)
            confidence = 'high' if votes[framework] >= 10 else 'medium' if votes[framework] >= 5 else 'low'
            return framework, confidence
        return 'junit', 'low'
    
    def _extract_tests(self, test_files: List[Path], repo_path: Path, framework: str) -> tuple:
        """Extract test methods from files."""
        tests = []
        test_id_counter = 1
        
        for filepath in test_files:
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                file_tests = self._extract_tests_from_file(filepath, content, repo_path, framework, test_id_counter)
                tests.extend(file_tests)
                test_id_counter += len(file_tests)
            except Exception as e:
                logger.warning(f"Error extracting tests from {filepath}: {e}")
        
        return tests, test_id_counter
    
    def _extract_tests_from_file(
        self, filepath: Path, content: str, repo_path: Path, framework: str, start_id: int
    ) -> List[Dict]:
        """Extract test methods from a single file."""
        tests = []
        test_id = start_id
        
        # Extract package
        package_match = re.search(r'^package\s+([\w.]+)\s*;', content, re.MULTILINE)
        package = package_match.group(1) if package_match else ''
        
        # Extract class name
        class_match = re.search(r'(?:public\s+)?class\s+(\w+)', content)
        class_name = class_match.group(1) if class_match else filepath.stem
        
        # Determine test type from path
        path_str = str(filepath).lower()
        if 'integration' in path_str or '/it/' in path_str:
            test_type = 'integration'
        elif 'e2e' in path_str or 'end.to.end' in path_str:
            test_type = 'e2e'
        else:
            test_type = 'unit'
        
        # Find test methods (@Test annotation)
        test_pattern = re.compile(
            r'@(?:Test|ParameterizedTest|RepeatedTest)\b[^\n]*\n\s*(?:public\s+)?(?:void\s+|[\w<>]+\s+)?(\w+)\s*\([^)]*\)',
            re.MULTILINE
        )
        
        for match in test_pattern.finditer(content):
            method_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            test_id_str = f"test_{test_id:04d}"
            test_id += 1
            
            tests.append({
                'test_id': test_id_str,
                'file_path': str(filepath),
                'class_name': class_name,
                'method_name': method_name,
                'test_type': test_type,
                'language': 'java',
                'repository_path': str(repo_path),
                'line_number': line_num,
                'framework': framework,
                'package': package,
            })
        
        return tests
    
    def _extract_dependencies(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract dependencies using Java dependency plugin."""
        dependencies = []
        test_by_file = {t['file_path']: t for t in tests}
        
        for filepath in test_files:
            test = test_by_file.get(str(filepath))
            if not test:
                continue
            
            if not self.dependency_plugin:
                continue
            
            try:
                deps = self.dependency_plugin.extract_dependencies(filepath)
                production_classes = deps.get('production_classes', [])
                all_refs = deps.get('all_production_references', [])
                # Separate actual imports from inferred
                actual_imports = deps.get('production_imports', [])
                inferred_refs = deps.get('inferred_references', [])
                
                dependencies.append({
                    'test_id': test['test_id'],
                    'file_path': str(filepath),
                    'class_name': test.get('class_name', ''),
                    'method_name': test['method_name'],
                    'referenced_classes': sorted(set(production_classes + all_refs)),
                    'reference_types': {ref: 'direct_import' for ref in actual_imports},
                    'import_count': len(actual_imports),  # Only count actual imports, not inferred
                    'inferred_count': len(inferred_refs),  # Track inferred separately
                })
            except Exception as e:
                logger.warning(f"Error extracting dependencies from {filepath}: {e}")
        
        return dependencies
    
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
        
        for filepath in test_files:
            # Try multiple path formats to match
            file_path_str = str(filepath)
            file_path_relative = str(filepath.relative_to(repo_path)) if filepath.is_relative_to(repo_path) else file_path_str
            file_path_abs = str(filepath.resolve())
            
            # Try to find tests for this file using any path format
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                file_tests = tests_by_file.get(file_path_relative, [])
            if not file_tests:
                file_tests = tests_by_file.get(file_path_abs, [])
            if not file_tests:
                # Last resort: try to match by filename
                filename = filepath.name
                file_tests = [t for t in tests if Path(t.get('file_path', '')).name == filename]
            
            if not file_tests:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                # Improved extraction: find method calls (basic pattern)
                method_call_pattern = re.compile(r'(\w+)\.(\w+)\s*\(', re.MULTILINE)
                
                for match in method_call_pattern.finditer(content):
                    obj_name = match.group(1)
                    method_name = match.group(2)
                    
                    # Skip test framework methods and Java keywords
                    if obj_name.lower() in ['mockito', 'assert', 'verify', 'when', 'then', 'given', 'mock', 'spy', 'self', 'this', 'super', 'system', 'out', 'print']:
                        continue
                    
                    # Skip if it's a Java keyword or common test framework
                    if obj_name[0].isupper() and obj_name not in ['String', 'Integer', 'Long', 'Double', 'Float', 'Boolean', 'List', 'Map', 'Set']:
                        # Likely a class name - extract module from it
                        module_name = obj_name
                    else:
                        module_name = obj_name
                    
                    # Assign to all tests in file (since we can't determine which specific test)
                    for test in file_tests:
                        function_calls.append({
                            'test_id': test['test_id'],
                            'file_path': file_path_str,
                            'class_name': test.get('class_name', ''),
                            'method_name': test['method_name'],
                            'module_name': module_name,
                            'function_name': method_name,
                            'object_name': obj_name,
                            'call_type': 'method',
                            'source': 'method_call',
                            'line_number': content[:match.start()].count('\n') + 1,
                        })
            except Exception as e:
                logger.warning(f"Error extracting function calls from {filepath}: {e}")
        
        return function_calls
    
    def _extract_reflection_calls(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract reflection API calls from test files."""
        reflection_calls = []
        tests_by_file = defaultdict(list)
        for test in tests:
            file_path = test.get('file_path', '')
            if file_path:
                tests_by_file[file_path].append(test)
        
        # Reflection method patterns
        reflection_patterns = [
            (r'Class\.forName\s*\(\s*["\']([^"\']+)["\']', 'forName', 'target_class'),
            (r'\.getDeclaredMethod\s*\(\s*["\']([^"\']+)["\']', 'getDeclaredMethod', 'target_method'),
            (r'\.getMethod\s*\(\s*["\']([^"\']+)["\']', 'getMethod', 'target_method'),
            (r'\.getDeclaredField\s*\(\s*["\']([^"\']+)["\']', 'getDeclaredField', 'target_field'),
            (r'\.getField\s*\(\s*["\']([^"\']+)["\']', 'getField', 'target_field'),
            (r'\.getDeclaredConstructor\s*\(', 'getDeclaredConstructor', None),
            (r'\.getConstructor\s*\(', 'getConstructor', None),
            (r'\.newInstance\s*\(', 'newInstance', None),
            (r'\.invoke\s*\(', 'invoke', None),
            (r'MethodHandles\.lookup\s*\(', 'lookup', None),
            (r'MethodHandles\.findVirtual\s*\(', 'findVirtual', None),
            (r'MethodHandles\.findStatic\s*\(', 'findStatic', None),
            (r'ReflectionUtils\.findMethod\s*\(', 'findMethod', None),
            (r'ReflectionUtils\.findField\s*\(', 'findField', None),
            (r'ReflectionTestUtils\.setField\s*\(', 'setField', None),
            (r'ReflectionTestUtils\.getField\s*\(', 'getField', None),
            (r'ReflectionTestUtils\.invokeMethod\s*\(', 'invokeMethod', None),
        ]
        
        for filepath in test_files:
            file_path_str = str(filepath)
            file_path_relative = str(filepath.relative_to(repo_path)) if filepath.is_relative_to(repo_path) else file_path_str
            file_path_abs = str(filepath.resolve())
            
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                file_tests = tests_by_file.get(file_path_relative, [])
            if not file_tests:
                file_tests = tests_by_file.get(file_path_abs, [])
            if not file_tests:
                filename = filepath.name
                file_tests = [t for t in tests if Path(t.get('file_path', '')).name == filename]
            
            if not file_tests:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                for pattern, method_name, target_type in reflection_patterns:
                    regex = re.compile(pattern, re.MULTILINE)
                    for match in regex.finditer(content):
                        line_num = content[:match.start()].count('\n') + 1
                        target_value = match.group(1) if match.lastindex and match.lastindex >= 1 else None
                        
                        for test in file_tests:
                            call_data = {
                                'test_id': test['test_id'],
                                'reflection_method': method_name,
                                'line_number': line_num,
                            }
                            
                            if target_type == 'target_class' and target_value:
                                call_data['target_class'] = target_value
                            elif target_type == 'target_method' and target_value:
                                call_data['target_method'] = target_value
                            elif target_type == 'target_field' and target_value:
                                call_data['target_field'] = target_value
                            
                            reflection_calls.append(call_data)
            except Exception as e:
                logger.warning(f"Error extracting reflection calls from {filepath}: {e}")
        
        return reflection_calls
    
    def _extract_di_fields(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract dependency injection fields from test files."""
        di_fields = []
        tests_by_file = defaultdict(list)
        for test in tests:
            file_path = test.get('file_path', '')
            if file_path:
                tests_by_file[file_path].append(test)
        
        # DI annotation patterns
        di_annotations = ['Autowired', 'Inject', 'Mock', 'MockBean', 'Spy', 'SpyBean', 
                         'InjectMocks', 'Captor', 'Value', 'Resource', 'Qualifier']
        di_pattern = re.compile(
            r'@(' + '|'.join(di_annotations) + r')\s*(?:\([^)]*\))?\s*\n\s*'
            r'(?:private|protected|public)?\s*(?:static\s+)?(?:final\s+)?'
            r'([\w<>\[\].,? ]+?)\s+(\w+)\s*[;=]',
            re.MULTILINE
        )
        
        for filepath in test_files:
            file_path_str = str(filepath)
            file_path_relative = str(filepath.relative_to(repo_path)) if filepath.is_relative_to(repo_path) else file_path_str
            file_path_abs = str(filepath.resolve())
            
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                file_tests = tests_by_file.get(file_path_relative, [])
            if not file_tests:
                file_tests = tests_by_file.get(file_path_abs, [])
            if not file_tests:
                filename = filepath.name
                file_tests = [t for t in tests if Path(t.get('file_path', '')).name == filename]
            
            if not file_tests:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                for match in di_pattern.finditer(content):
                    annotation_name = match.group(1)
                    field_type = match.group(2).strip()
                    field_name = match.group(3)
                    line_num = content[:match.start()].count('\n') + 1
                    
                    # Determine injection type
                    injection_type = 'field'
                    if '@Autowired' in match.group(0) or '@Inject' in match.group(0):
                        # Check if it's in constructor
                        before_match = content[:match.start()]
                        if re.search(r'@(?:Autowired|Inject)\s+.*\n\s*(?:public\s+)?\w+\s*\(', before_match):
                            injection_type = 'constructor'
                    
                    for test in file_tests:
                        di_fields.append({
                            'test_id': test['test_id'],
                            'field_name': field_name,
                            'field_type': field_type,
                            'injection_type': injection_type,
                            'annotation_names': [annotation_name],
                        })
            except Exception as e:
                logger.warning(f"Error extracting DI fields from {filepath}: {e}")
        
        return di_fields
    
    def _extract_annotations(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract all annotations from test classes and methods."""
        annotations = []
        tests_by_file = defaultdict(list)
        for test in tests:
            file_path = test.get('file_path', '')
            if file_path:
                tests_by_file[file_path].append(test)
        
        # Annotation pattern: @AnnotationName(...) or @AnnotationName
        annotation_pattern = re.compile(
            r'@([\w.]+)\s*(?:\(([^)]*)\))?',
            re.MULTILINE
        )
        
        for filepath in test_files:
            file_path_str = str(filepath)
            file_path_relative = str(filepath.relative_to(repo_path)) if filepath.is_relative_to(repo_path) else file_path_str
            file_path_abs = str(filepath.resolve())
            
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                file_tests = tests_by_file.get(file_path_relative, [])
            if not file_tests:
                file_tests = tests_by_file.get(file_path_abs, [])
            if not file_tests:
                filename = filepath.name
                file_tests = [t for t in tests if Path(t.get('file_path', '')).name == filename]
            
            if not file_tests:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                # Extract class-level annotations
                class_match = re.search(r'(?:public\s+)?class\s+(\w+)', content)
                if class_match:
                    class_start = class_match.start()
                    class_ann_block = content[:class_start]
                    for match in annotation_pattern.finditer(class_ann_block):
                        annotation_name = match.group(1)
                        annotation_attrs = match.group(2) if match.group(2) else ''
                        
                        # Assign to all tests in the class
                        for test in file_tests:
                            annotations.append({
                                'test_id': test['test_id'],
                                'annotation_name': annotation_name,
                                'annotation_attributes': annotation_attrs if annotation_attrs else {},
                                'target_type': 'class',
                            })
                
                # Extract method-level annotations
                for test in file_tests:
                    method_name = test.get('method_name', '')
                    if method_name:
                        # Find the method in the content
                        method_pattern = re.compile(
                            rf'(?:public|protected|private)?\s+(?:void|[\w<>\[\]]+)\s+{re.escape(method_name)}\s*\([^)]*\)',
                            re.MULTILINE
                        )
                        method_match = method_pattern.search(content)
                        if method_match:
                            method_start = method_match.start()
                            # Look backwards for annotations before the method
                            method_ann_block = content[max(0, method_start - 500):method_start]
                            for match in annotation_pattern.finditer(method_ann_block):
                                annotation_name = match.group(1)
                                annotation_attrs = match.group(2) if match.group(2) else ''
                                
                                annotations.append({
                                    'test_id': test['test_id'],
                                    'annotation_name': annotation_name,
                                    'annotation_attributes': annotation_attrs if annotation_attrs else {},
                                    'target_type': 'method',
                                })
            except Exception as e:
                logger.warning(f"Error extracting annotations from {filepath}: {e}")
        
        return annotations
    
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
        from test_analysis.utils.file_scanner import group_files_by_category, get_file_metadata, _categorize_directory
        
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
        reflection_calls: List[Dict] = None, di_fields: List[Dict] = None, annotations: List[Dict] = None
    ):
        """Write all JSON output files (8 core + 3 Java-specific)."""
        now = datetime.now().isoformat()
        
        # 01_test_files.json
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
                        'language': 'java',
                    }
                    for f in test_files
                ],
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
        total_refs = sum(d.get('import_count', 0) for d in dependencies)  # Actual imports only
        total_inferred = sum(d.get('inferred_count', 0) for d in dependencies)  # Inferred refs
        self._write_json(output_dir / '04_static_dependencies.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(dependencies),
                'tests_with_dependencies': sum(1 for d in dependencies if d.get('import_count', 0) > 0),
                'total_references': total_refs,  # Actual imports only
                'total_inferred': total_inferred,  # Track inferred separately
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
                'async_tests': 0,
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
            metadata, framework, confidence
        )
        self._write_json(output_dir / '08_summary_report.json', {
            'generated_at': now,
            'data': summary,
        })
        
        # 09_java_reflection_calls.json (Java-specific)
        if reflection_calls:
            self._write_json(output_dir / '09_java_reflection_calls.json', {
                'generated_at': now,
                'data': {
                    'total_reflection_calls': len(reflection_calls),
                    'tests_with_reflection': len(set(c['test_id'] for c in reflection_calls)),
                    'reflection_calls': reflection_calls,
                },
            })
        
        # 10_java_di_fields.json (Java-specific)
        if di_fields:
            self._write_json(output_dir / '10_java_di_fields.json', {
                'generated_at': now,
                'data': {
                    'total_di_fields': len(di_fields),
                    'tests_with_di': len(set(f['test_id'] for f in di_fields)),
                    'di_fields': di_fields,
                },
            })
        
        # 11_java_annotations.json (Java-specific)
        if annotations:
            self._write_json(output_dir / '11_java_annotations.json', {
                'generated_at': now,
                'data': {
                    'total_annotations': len(annotations),
                    'tests_with_annotations': len(set(a['test_id'] for a in annotations)),
                    'annotations': annotations,
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
        """Get test category from file path."""
        path_str = str(filepath).lower()
        if 'integration' in path_str or '/it/' in path_str:
            return 'integration'
        elif 'e2e' in path_str:
            return 'e2e'
        return 'unit'
    
    def _categorize_files(self, test_files: List[Path]) -> Dict[str, int]:
        """Categorize files by type."""
        cats = defaultdict(int)
        for f in test_files:
            cats[self._get_category(f)] += 1
        return dict(cats)
    
    def _generate_summary(
        self, test_files: List[Path], tests: List[Dict],
        dependencies: List[Dict], reverse_index: Dict,
        metadata: List[Dict], framework: str, confidence: str
    ) -> Dict:
        """Generate summary report."""
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
                'language': 'java',
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
                'async_tests': 0,
                'parameterized_tests': sum(1 for m in metadata if m.get('is_parameterized')),
                'disabled_tests': sum(1 for m in metadata if m.get('is_disabled')),
            },
            'summary_for_db': {
                'files_analyzed': len(test_files),
                'functions_extracted': 0,  # Would need to calculate
                'modules_identified': len(set(t.get('package', '') for t in tests)),
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
