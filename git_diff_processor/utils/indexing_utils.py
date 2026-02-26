"""
Indexing utilities for verifying and re-indexing test files.

This module provides functions to:
- Verify indexing completeness
- Re-index missing test files
- Diagnose integration test issues
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
import sys

# Add parent directories to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
root_dir = parent_dir.parent

sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "test_analysis"))

from deterministic.db_connection import get_connection, DB_SCHEMA
from test_analysis.utils.file_scanner import scan_directory_comprehensive, get_file_metadata, _categorize_directory
from test_analysis.utils.ast_parser import parse_file, extract_test_classes, extract_test_methods


def extract_test_type_enhanced(filepath: Path) -> str:
    """Extract test type from file path."""
    category = _categorize_directory(filepath)
    if category == 'integration':
        return 'integration'
    elif category == 'e2e':
        return 'e2e'
    else:
        return 'unit'


def verify_indexing_completeness(test_repo_path: str, conn=None) -> Dict[str, Any]:
    """
    Verify that all test files in repository are indexed.
    
    FIXED: Now properly normalizes paths and filters out __init__.py and conftest.py.
    
    Args:
        test_repo_path: Path to test repository
        conn: Optional database connection (will create if not provided)
    
    Returns:
        Dictionary with verification results
    """
    test_repo = Path(test_repo_path)
    if not test_repo.exists():
        return {
            'error': f"Test repository path does not exist: {test_repo_path}",
            'total_on_disk': 0,
            'total_indexed': 0,
            'missing_files': [],
            'coverage_percent': 0
        }
    
    # Find all test files on disk (excluding __init__.py and conftest.py)
    test_files_on_disk = scan_directory_comprehensive(test_repo)
    # Filter out __init__.py and conftest.py
    test_files_on_disk = [f for f in test_files_on_disk if f.name not in ['__init__.py', 'conftest.py']]
    test_files_on_disk_str = [str(f.resolve()) for f in test_files_on_disk]
    
    # Get all test files in database
    should_close = False
    if conn is None:
        conn = get_connection().__enter__()
        should_close = True
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT DISTINCT file_path
                FROM {DB_SCHEMA}.test_registry
            """)
            indexed_files = [row[0] for row in cursor.fetchall()]
        
        # Normalize paths for comparison (handle both absolute and relative paths)
        indexed_paths_normalized = set()
        for p in indexed_files:
            try:
                # Try to resolve the path
                resolved = Path(p).resolve()
                indexed_paths_normalized.add(str(resolved))
            except:
                # If resolution fails, use as-is (might be relative)
                indexed_paths_normalized.add(str(Path(p)))
        
        disk_paths_normalized = {str(Path(p).resolve()) for p in test_files_on_disk_str}
        
        # Find missing files
        missing_files = []
        for disk_path in disk_paths_normalized:
            # Check if this file is indexed (by normalized path)
            if disk_path not in indexed_paths_normalized:
                missing_files.append(disk_path)
        
        coverage = (len(indexed_paths_normalized) / len(disk_paths_normalized) * 100) if disk_paths_normalized else 0
        
        return {
            'total_on_disk': len(test_files_on_disk),
            'total_indexed': len(indexed_paths_normalized),
            'missing_files': missing_files,
            'coverage_percent': coverage
        }
    finally:
        if should_close:
            conn.__exit__(None, None, None)


def reindex_missing_files(test_repo_path: str, conn=None) -> Dict[str, Any]:
    """
    Re-index only files that are missing from database.
    
    FIXED: Now checks for existing tests by (file_path, class_name, method_name)
    to avoid creating duplicates when the same file has different absolute paths.
    
    Args:
        test_repo_path: Path to test repository
        conn: Optional database connection
    
    Returns:
        Dictionary with re-indexing results
    """
    from deterministic.utils.db_helpers import batch_insert_test_registry
    
    verification = verify_indexing_completeness(test_repo_path, conn)
    missing_files = verification.get('missing_files', [])
    
    if not missing_files:
        return {'indexed': 0, 'skipped': 0, 'errors': [], 'duplicates_avoided': 0}
    
    should_close = False
    if conn is None:
        conn = get_connection().__enter__()
        should_close = True
    
    try:
        indexed_count = 0
        error_count = 0
        errors = []
        all_tests = []
        duplicates_avoided = 0
        
        # Get all existing tests to check for duplicates
        # Use normalized file paths for comparison
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT test_id, file_path, class_name, method_name
                FROM {DB_SCHEMA}.test_registry
            """)
            existing_tests = {}
            for row in cursor.fetchall():
                test_id, file_path, class_name, method_name = row
                # Create a key from normalized path + class + method
                normalized_path = str(Path(file_path).resolve())
                key = (normalized_path, class_name or '', method_name)
                existing_tests[key] = test_id
        
        # Get current max test_id to continue numbering (only for truly new tests)
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT test_id FROM {DB_SCHEMA}.test_registry
                ORDER BY test_id DESC LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                last_id = result[0]
                test_id_counter = int(last_id.split('_')[1]) + 1
            else:
                test_id_counter = 1
        
        # Process each missing file
        for file_path_str in missing_files:
            try:
                filepath = Path(file_path_str)
                normalized_filepath = str(filepath.resolve())
                
                # Skip __init__.py and conftest.py (not actual test files)
                if filepath.name in ['__init__.py', 'conftest.py']:
                    continue
                
                # Parse the file
                tree = parse_file(filepath)
                if not tree:
                    continue
                
                # Get test type
                test_type = extract_test_type_enhanced(filepath)
                
                # Extract test classes
                test_classes = extract_test_classes(tree)
                all_test_methods = extract_test_methods(tree)
                
                # Extract tests
                file_tests = []
                if test_classes:
                    for test_class in test_classes:
                        class_name = test_class['name']
                        for method_name in test_class['methods']:
                            if method_name.startswith('test_'):
                                # Check if this test already exists
                                key = (normalized_filepath, class_name, method_name)
                                if key in existing_tests:
                                    duplicates_avoided += 1
                                    continue
                                
                                test_id = f"test_{test_id_counter:04d}"
                                test_id_counter += 1
                                file_tests.append({
                                    'test_id': test_id,
                                    'file_path': str(filepath),  # Store as provided, but check normalized
                                    'class_name': class_name,
                                    'method_name': method_name,
                                    'test_type': test_type,
                                    'line_number': None
                                })
                                # Add to existing_tests to avoid duplicates in same batch
                                existing_tests[key] = test_id
                else:
                    for test_method in all_test_methods:
                        # Check if this test already exists
                        key = (normalized_filepath, '', test_method['name'])
                        if key in existing_tests:
                            duplicates_avoided += 1
                            continue
                        
                        test_id = f"test_{test_id_counter:04d}"
                        test_id_counter += 1
                        file_tests.append({
                            'test_id': test_id,
                            'file_path': str(filepath),
                            'class_name': None,
                            'method_name': test_method['name'],
                            'test_type': test_type,
                            'line_number': test_method.get('line_number')
                        })
                        # Add to existing_tests to avoid duplicates in same batch
                        existing_tests[key] = test_id
                
                if file_tests:
                    all_tests.extend(file_tests)
                    indexed_count += 1
                    
            except Exception as e:
                error_count += 1
                errors.append({'file': file_path_str, 'error': str(e)})
        
        # Batch insert all tests
        if all_tests:
            batch_insert_test_registry(conn, all_tests)
            conn.commit()
        
        return {
            'indexed': indexed_count,
            'tests_added': len(all_tests),
            'skipped': len(missing_files) - indexed_count,
            'duplicates_avoided': duplicates_avoided,
            'errors': errors
        }
    finally:
        if should_close:
            conn.__exit__(None, None, None)


def diagnose_integration_tests(conn=None) -> Dict[str, Any]:
    """
    Diagnose why integration/e2e tests aren't being found.
    
    Args:
        conn: Optional database connection
    
    Returns:
        Dictionary with diagnostic information
    """
    should_close = False
    if conn is None:
        conn = get_connection().__enter__()
        should_close = True
    
    try:
        with conn.cursor() as cursor:
            # Check what integration tests exist in database
            cursor.execute(f"""
                SELECT test_id, file_path, test_type, class_name, method_name
                FROM {DB_SCHEMA}.test_registry
                WHERE test_type IN ('integration', 'e2e')
                ORDER BY test_type, file_path
            """)
            integration_tests = [
                {
                    'test_id': row[0],
                    'file_path': row[1],
                    'test_type': row[2],
                    'class_name': row[3],
                    'method_name': row[4]
                }
                for row in cursor.fetchall()
            ]
            
            # Check what references they have
            cursor.execute(f"""
                SELECT DISTINCT tr.test_id, tr.file_path, tr.test_type,
                       ri.production_class, ri.reference_type
                FROM {DB_SCHEMA}.test_registry tr
                LEFT JOIN {DB_SCHEMA}.reverse_index ri ON tr.test_id = ri.test_id
                WHERE tr.test_type IN ('integration', 'e2e')
                ORDER BY tr.file_path, ri.production_class
            """)
            integration_with_refs = [
                {
                    'test_id': row[0],
                    'file_path': row[1],
                    'test_type': row[2],
                    'production_class': row[3],
                    'reference_type': row[4]
                }
                for row in cursor.fetchall()
            ]
            
            # Check for specific known integration test
            cursor.execute(f"""
                SELECT test_id, file_path, test_type, class_name, method_name
                FROM {DB_SCHEMA}.test_registry
                WHERE file_path LIKE '%agent_flow%'
                   OR file_path LIKE '%test_agent_flow%'
            """)
            agent_flow_tests = [
                {
                    'test_id': row[0],
                    'file_path': row[1],
                    'test_type': row[2],
                    'class_name': row[3],
                    'method_name': row[4]
                }
                for row in cursor.fetchall()
            ]
            
            suggestions = []
            if len(integration_tests) == 0:
                suggestions.append("No integration/e2e tests found in database")
                suggestions.append("Run test analysis steps to index integration tests")
            else:
                suggestions.append(f"Found {len(integration_tests)} integration/e2e tests")
                if len(agent_flow_tests) == 0:
                    suggestions.append("test_agent_flow.py not found - may need re-indexing")
            
            return {
                'total_integration_tests': len(integration_tests),
                'integration_tests': integration_tests,
                'integration_tests_with_refs': integration_with_refs,
                'agent_flow_tests': agent_flow_tests,
                'suggestions': suggestions
            }
    finally:
        if should_close:
            conn.__exit__(None, None, None)
