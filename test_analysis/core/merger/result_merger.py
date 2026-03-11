"""
Result merger.

Merges JSON outputs from multiple language analyzers into unified 8 JSON files.
"""

from pathlib import Path
from typing import Dict, List
from collections import defaultdict
import json
import logging
from datetime import datetime

from ..analyzers.base_analyzer import AnalyzerResult

logger = logging.getLogger(__name__)


class ResultMerger:
    """Merges results from multiple analyzers."""
    
    def merge(self, analyzer_results: List[AnalyzerResult], output_dir: Path) -> Dict:
        """
        Merge results from multiple analyzers.
        
        Args:
            analyzer_results: List of AnalyzerResult from each analyzer
            output_dir: Directory to write merged JSON files
            
        Returns:
            Dictionary with merged summary
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load all JSON files from each analyzer
        all_test_files = []
        all_tests = []
        all_dependencies = []
        all_function_calls = []
        all_metadata = []
        all_reverse_index = defaultdict(list)
        all_structure = {}
        
        frameworks = []
        total_files = 0
        total_tests = 0
        
        for result in analyzer_results:
            analyzer_output_dir = Path(result.output_dir)
            
            # Load each JSON file
            try:
                # 01_test_files.json
                with open(analyzer_output_dir / '01_test_files.json', 'r', encoding='utf-8') as f:
                    data = json.load(f).get('data', {})
                    all_test_files.extend(data.get('files', []))
                    total_files += data.get('total_files', 0)
                
                # 03_test_registry.json
                with open(analyzer_output_dir / '03_test_registry.json', 'r', encoding='utf-8') as f:
                    data = json.load(f).get('data', {})
                    all_tests.extend(data.get('tests', []))
                    total_tests += data.get('total_tests', 0)
                
                # 04_static_dependencies.json
                with open(analyzer_output_dir / '04_static_dependencies.json', 'r', encoding='utf-8') as f:
                    data = json.load(f).get('data', {})
                    all_dependencies.extend(data.get('test_dependencies', []))
                
                # 04b_function_calls.json
                with open(analyzer_output_dir / '04b_function_calls.json', 'r', encoding='utf-8') as f:
                    data = json.load(f).get('data', {})
                    all_function_calls.extend(data.get('test_function_mappings', []))
                
                # 05_test_metadata.json
                with open(analyzer_output_dir / '05_test_metadata.json', 'r', encoding='utf-8') as f:
                    data = json.load(f).get('data', {})
                    all_metadata.extend(data.get('test_metadata', []))
                
                # 06_reverse_index.json
                with open(analyzer_output_dir / '06_reverse_index.json', 'r', encoding='utf-8') as f:
                    data = json.load(f).get('data', {})
                    rev_idx = data.get('reverse_index', {})
                    for cls, tests in rev_idx.items():
                        all_reverse_index[cls].extend(tests)
                
                # 02_framework_detection.json
                with open(analyzer_output_dir / '02_framework_detection.json', 'r', encoding='utf-8') as f:
                    data = json.load(f).get('data', {})
                    frameworks.append(data.get('framework', 'unknown'))
                
                # 07_test_structure.json
                try:
                    with open(analyzer_output_dir / '07_test_structure.json', 'r', encoding='utf-8') as f:
                        data = json.load(f).get('data', {})
                        # Merge structure data
                        if not all_structure:
                            all_structure = data.copy()
                        else:
                            # Merge directory structures
                            if 'directory_structure' in data:
                                if 'directory_structure' not in all_structure:
                                    all_structure['directory_structure'] = {}
                                # Merge directories
                                for cat, stats in data['directory_structure'].get('directories', {}).items():
                                    if cat in all_structure['directory_structure'].get('directories', {}):
                                        # Combine stats
                                        existing = all_structure['directory_structure']['directories'][cat]
                                        all_structure['directory_structure']['directories'][cat] = {
                                            'file_count': existing.get('file_count', 0) + stats.get('file_count', 0),
                                            'test_count': existing.get('test_count', 0) + stats.get('test_count', 0),
                                            'total_lines': existing.get('total_lines', 0) + stats.get('total_lines', 0),
                                        }
                                    else:
                                        if 'directories' not in all_structure['directory_structure']:
                                            all_structure['directory_structure']['directories'] = {}
                                        all_structure['directory_structure']['directories'][cat] = stats
                                
                                # Merge files_by_directory
                                if 'files_by_directory' in data['directory_structure']:
                                    if 'files_by_directory' not in all_structure['directory_structure']:
                                        all_structure['directory_structure']['files_by_directory'] = {}
                                    for cat, files in data['directory_structure']['files_by_directory'].items():
                                        if cat in all_structure['directory_structure']['files_by_directory']:
                                            all_structure['directory_structure']['files_by_directory'][cat].extend(files)
                                        else:
                                            all_structure['directory_structure']['files_by_directory'][cat] = files
                            
                            # Merge summaries
                            if 'summary' in data:
                                if 'summary' not in all_structure:
                                    all_structure['summary'] = {}
                                # Merge categories
                                existing_cats = set(all_structure['summary'].get('categories', []))
                                new_cats = set(data['summary'].get('categories', []))
                                all_structure['summary']['categories'] = sorted(list(existing_cats | new_cats))
                                
                                existing_test_cats = set(all_structure['summary'].get('test_categories', []))
                                new_test_cats = set(data['summary'].get('test_categories', []))
                                all_structure['summary']['test_categories'] = sorted(list(existing_test_cats | new_test_cats))
                                
                                # Update totals
                                all_structure['summary']['total_directories'] = len(all_structure['summary']['categories'])
                                all_structure['summary']['total_files'] = (
                                    all_structure['summary'].get('total_files', 0) + 
                                    data['summary'].get('total_files', 0)
                                )
                except FileNotFoundError:
                    # Test structure file might not exist for some analyzers
                    pass
                except Exception as e:
                    logger.warning(f"Error loading test_structure from {analyzer_output_dir}: {e}")
                
            except Exception as e:
                logger.warning(f"Error loading results from {analyzer_output_dir}: {e}")
        
        # Determine primary framework
        framework_votes = defaultdict(int)
        for fw in frameworks:
            framework_votes[fw] += 1
        primary_framework = max(framework_votes, key=framework_votes.get) if framework_votes else 'unknown'
        
        # Write merged JSON files
        now = datetime.now().isoformat()
        
        # 01_test_files.json
        self._write_json(output_dir / '01_test_files.json', {
            'generated_at': now,
            'data': {
                'scan_directory': str(output_dir),
                'total_files': len(all_test_files),
                'total_lines': sum(f.get('line_count', 0) for f in all_test_files),
                'total_size_bytes': sum(f.get('size_bytes', 0) for f in all_test_files),
                'categories': self._categorize_files(all_test_files),
                'files': all_test_files,
            },
        })
        
        # 02_framework_detection.json
        self._write_json(output_dir / '02_framework_detection.json', {
            'generated_at': now,
            'data': {
                'primary_framework': primary_framework,
                'framework': primary_framework,
                'confidence': 'high' if len(frameworks) == 1 else 'medium',
                'evidence': [f'{fw} detected' for fw in set(frameworks)],
            },
        })
        
        # 03_test_registry.json
        by_type = defaultdict(int)
        by_file = defaultdict(int)
        for test in all_tests:
            by_type[test.get('test_type', 'unit')] += 1
            by_file[test['file_path']] += 1
        
        self._write_json(output_dir / '03_test_registry.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(all_tests),
                'total_classes': len(set(t.get('class_name') for t in all_tests if t.get('class_name'))),
                'total_files': len(set(t['file_path'] for t in all_tests)),
                'tests_by_type': dict(by_type),
                'tests_by_file': dict(by_file),
                'tests': all_tests,
            },
        })
        
        # 04_static_dependencies.json
        total_refs = sum(d.get('import_count', 0) for d in all_dependencies)
        self._write_json(output_dir / '04_static_dependencies.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(all_dependencies),
                'tests_with_dependencies': sum(1 for d in all_dependencies if d.get('import_count', 0) > 0),
                'total_references': total_refs,
                'average_references_per_test': round(total_refs / len(all_dependencies), 2) if all_dependencies else 0,
                'test_dependencies': all_dependencies,
            },
        })
        
        # 04b_function_calls.json
        self._write_json(output_dir / '04b_function_calls.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(all_tests),
                'tests_with_function_calls': len(set(c['test_id'] for c in all_function_calls)),
                'total_mappings': len(all_function_calls),
                'average_mappings_per_test': round(len(all_function_calls) / len(all_tests), 2) if all_tests else 0,
                'test_function_mappings': all_function_calls,
            },
        })
        
        # 05_test_metadata.json
        self._write_json(output_dir / '05_test_metadata.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(all_metadata),
                'tests_with_descriptions': sum(1 for m in all_metadata if m.get('description')),
                'tests_with_markers': sum(1 for m in all_metadata if m.get('markers')),
                'async_tests': sum(1 for m in all_metadata if m.get('is_async')),
                'parameterized_tests': sum(1 for m in all_metadata if m.get('is_parameterized')),
                'disabled_tests': sum(1 for m in all_metadata if m.get('is_disabled')),
                'test_metadata': all_metadata,
            },
        })
        
        # 06_reverse_index.json
        total_mappings = sum(len(v) for v in all_reverse_index.values())
        self._write_json(output_dir / '06_reverse_index.json', {
            'generated_at': now,
            'data': {
                'total_production_classes': len(all_reverse_index),
                'total_mappings': total_mappings,
                'average_tests_per_class': round(total_mappings / len(all_reverse_index), 2) if all_reverse_index else 0,
                'reverse_index': {k: v for k, v in all_reverse_index.items()},
            },
        })
        
        # 07_test_structure.json
        # Ensure structure has required fields
        if not all_structure:
            all_structure = {
                'directory_structure': {
                    'root_path': str(output_dir),
                    'directories': {},
                    'files_by_directory': {}
                },
                'summary': {
                    'total_directories': 0,
                    'total_files': len(all_test_files),
                    'categories': [],
                    'test_categories': []
                }
            }
        else:
            # Ensure all required fields exist
            if 'directory_structure' not in all_structure:
                all_structure['directory_structure'] = {
                    'root_path': str(output_dir),
                    'directories': {},
                    'files_by_directory': {}
                }
            if 'summary' not in all_structure:
                all_structure['summary'] = {
                    'total_directories': len(all_structure.get('directory_structure', {}).get('directories', {})),
                    'total_files': len(all_test_files),
                    'categories': list(all_structure.get('directory_structure', {}).get('directories', {}).keys()),
                    'test_categories': list(all_structure.get('directory_structure', {}).get('directories', {}).keys())
                }
        
        self._write_json(output_dir / '07_test_structure.json', {
            'generated_at': now,
            'data': all_structure,
        })
        
        # 08_summary_report.json
        summary = {
            'test_repository_overview': {
                'total_test_files': len(all_test_files),
                'total_lines_of_code': sum(f.get('line_count', 0) for f in all_test_files),
                'test_framework': primary_framework,
                'framework_confidence': 'high' if len(frameworks) == 1 else 'medium',
            },
            'test_inventory': {
                'total_tests': len(all_tests),
                'total_test_classes': len(set(t.get('class_name') for t in all_tests if t.get('class_name'))),
                'tests_by_type': dict(by_type),
            },
            'summary_for_db': {
                'files_analyzed': len(all_test_files),
                'total_tests': len(all_tests),
                'framework': primary_framework,
            },
        }
        
        self._write_json(output_dir / '08_summary_report.json', {
            'generated_at': now,
            'data': summary,
        })
        
        return summary
    
    def _write_json(self, path: Path, data: Dict):
        """Write JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _categorize_files(self, files: List[Dict]) -> Dict[str, int]:
        """Categorize files by directory."""
        cats = defaultdict(int)
        for f in files:
            cats[f.get('directory', 'unit')] += 1
        return dict(cats)


def merge_analyzer_results(analyzer_results: List[AnalyzerResult], output_dir: Path) -> Dict:
    """
    Convenience function to merge analyzer results.
    
    Args:
        analyzer_results: List of AnalyzerResult
        output_dir: Output directory for merged files
        
    Returns:
        Merged summary dictionary
    """
    merger = ResultMerger()
    return merger.merge(analyzer_results, output_dir)
