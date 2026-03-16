"""
Tree-sitter fallback analyzer for unknown languages.

Uses Tree-sitter and regex fallback to analyze test files in languages
that don't have dedicated analyzers.
"""

from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
import json
import re
import logging
from datetime import datetime

from .base_analyzer import BaseAnalyzer, AnalyzerResult

# Import universal parser
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from test_analysis.utils.universal_parser import UniversalTestParser, detect_language

logger = logging.getLogger(__name__)


class TreeSitterFallbackAnalyzer(BaseAnalyzer):
    """Fallback analyzer for unknown languages using Tree-sitter."""
    
    def __init__(self):
        super().__init__(
            language='unknown',
            supported_frameworks=[]  # Generic, supports any framework
        )
        self.parser = UniversalTestParser()
    
    def analyze(self, repo_path: Path, output_dir: Path) -> AnalyzerResult:
        """Analyze repository using Tree-sitter fallback."""
        self._ensure_output_dir(output_dir)
        self._log_progress("Starting Tree-sitter fallback analysis")
        
        errors = []
        repo_path = Path(repo_path).resolve()
        
        # Detect language from files
        test_files = self._scan_test_files(repo_path)
        if not test_files:
            errors.append("No test files found")
            return AnalyzerResult(
                language='unknown',
                framework='unknown',
                output_dir=output_dir,
                errors=errors
            )
        
        # Detect primary language
        languages = defaultdict(int)
        for f in test_files:
            lang = detect_language(f)
            if lang != 'unknown':
                languages[lang] += 1
        
        primary_language = max(languages, key=languages.get) if languages else 'unknown'
        
        # Detect framework (basic)
        framework, confidence = self._detect_framework(test_files)
        
        # Extract tests
        self._log_progress("Extracting tests...")
        tests, test_id_counter = self._extract_tests(test_files, repo_path, framework)
        
        # Extract dependencies
        self._log_progress("Extracting dependencies...")
        dependencies = self._extract_dependencies(test_files, tests, repo_path)
        
        # Extract function calls
        self._log_progress("Extracting function calls...")
        function_calls = self._extract_function_calls(test_files, tests, repo_path)
        
        # Extract metadata
        self._log_progress("Extracting metadata...")
        metadata = self._extract_metadata(tests, test_files, repo_path)
        
        # Build reverse index
        self._log_progress("Building reverse index...")
        reverse_index = self._build_reverse_index(dependencies, function_calls)
        
        # Map structure
        self._log_progress("Mapping test structure...")
        structure = self._map_test_structure(test_files, tests, repo_path)
        
        # Write outputs
        self._write_outputs(
            output_dir, test_files, framework, confidence,
            tests, dependencies, function_calls, metadata,
            reverse_index, structure, repo_path, primary_language
        )
        
        # Generate summary
        summary = self._generate_summary(
            test_files, tests, dependencies, reverse_index,
            metadata, framework, confidence, primary_language
        )
        
        self._log_progress(f"Analysis complete: {len(tests)} tests found")
        
        return AnalyzerResult(
            language=primary_language,
            framework=framework,
            output_dir=output_dir,
            summary=summary,
            files_analyzed=len(test_files),
            tests_found=len(tests),
            errors=errors
        )
    
    def _scan_test_files(self, repo_path: Path) -> List[Path]:
        """Scan for test files using universal patterns."""
        test_files = []
        test_keywords = ['test', 'spec']
        exclude_dirs = {'node_modules', '.git', 'target', 'build', '.gradle', '.mvn'}
        
        for filepath in repo_path.rglob('*'):
            if not filepath.is_file():
                continue
            if any(excluded in filepath.parts for excluded in exclude_dirs):
                continue
            
            # Check if filename contains test keywords
            name_lower = filepath.name.lower()
            if any(kw in name_lower for kw in test_keywords):
                test_files.append(filepath)
        
        return sorted(test_files)
    
    def _detect_framework(self, test_files: List[Path]) -> tuple:
        """Basic framework detection."""
        # Generic detection - would need language-specific logic
        return 'unknown', 'low'
    
    def _extract_tests(self, test_files: List[Path], repo_path: Path, framework: str) -> tuple:
        """Extract tests using universal parser."""
        tests = []
        test_id_counter = 1
        
        for filepath in test_files:
            try:
                parsed = self.parser.parse_file(filepath)
                if parsed.get('error'):
                    logger.debug(f"Error parsing {filepath}: {parsed['error']}")
                    continue
                
                language = parsed.get('language', 'unknown')
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
                        'language': language,
                        'repository_path': str(repo_path),
                        'line_number': method_info.get('line_number'),
                        'framework': framework,
                        'parse_method': parsed.get('parse_method', 'unknown'),
                    })
            except Exception as e:
                logger.warning(f"Error extracting tests from {filepath}: {e}")
        
        return tests, test_id_counter
    
    def _get_test_type(self, filepath: Path) -> str:
        """Get test type from path."""
        path_str = str(filepath).lower()
        if 'integration' in path_str:
            return 'integration'
        elif 'e2e' in path_str:
            return 'e2e'
        return 'unit'
    
    def _extract_dependencies(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract dependencies using universal parser."""
        dependencies = []
        test_by_file = {t['file_path']: t for t in tests}
        
        for filepath in test_files:
            test = test_by_file.get(str(filepath))
            if not test:
                continue
            
            try:
                parsed = self.parser.parse_file(filepath)
                imports = parsed.get('imports', [])
                
                # Basic filtering - would need language-specific logic
                production_imports = [
                    imp for imp in imports
                    if not any(kw in imp.lower() for kw in ['test', 'spec', 'mock', 'junit'])
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
        
        return dependencies
    
    def _extract_function_calls(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract function calls (basic)."""
        # Minimal implementation - would need language-specific logic
        return []
    
    def _extract_metadata(
        self, tests: List[Dict], test_files: List[Path], repo_path: Path
    ) -> List[Dict]:
        """Extract metadata."""
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
                'pattern': 'unknown',
                'line_number': test.get('line_number'),
            })
        return metadata
    
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
        language: str
    ):
        """Write all 8 JSON output files."""
        now = datetime.now().isoformat()
        
        # Write all 8 files with minimal data
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
                        'language': language,
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
                'evidence': [],
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
                'total_classes': len(set(t.get('class_name') for t in tests if t.get('class_name'))),
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
                'average_mappings_per_test': 0,
                'test_function_mappings': function_calls,
            },
        })
        
        self._write_json(output_dir / '05_test_metadata.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(metadata),
                'tests_with_descriptions': 0,
                'tests_with_markers': 0,
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
            metadata, framework, confidence, language
        )
        self._write_json(output_dir / '08_summary_report.json', {
            'generated_at': now,
            'data': summary,
        })
    
    def _write_json(self, path: Path, data: Dict):
        """Write JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _count_lines(self, filepath: Path) -> int:
        """Count lines."""
        try:
            return len(filepath.read_text(encoding='utf-8', errors='replace').splitlines())
        except:
            return 0
    
    def _get_category(self, filepath: Path) -> str:
        """Get category."""
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
        metadata: List[Dict], framework: str, confidence: str, language: str
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
                'language': language,
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
                'total_test_classes': len(set(t.get('class_name') for t in tests if t.get('class_name'))),
                'total_test_methods': len(tests),
                'total_dependencies': total_deps,
                'total_production_classes': total_prod_classes,
                'tests_with_descriptions': 0,
                'framework': framework,
            },
        }
