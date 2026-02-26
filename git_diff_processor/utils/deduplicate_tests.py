"""
Utility to find and remove duplicate test entries from database.

This module helps identify and clean up duplicate tests that may have been
created due to path mismatches (e.g., same file indexed from different locations).
"""

from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
import sys

# Add parent directories to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
root_dir = parent_dir.parent

sys.path.insert(0, str(root_dir))

from deterministic.db_connection import get_connection, DB_SCHEMA


def _normalize_path_for_dedup(file_path: str) -> str:
    """
    Normalize file path for duplicate detection.
    
    Strategy:
    1. Extract relative path from test_repository (if present)
    2. Otherwise use filename + parent directory name
    3. This handles cases where same file is indexed from different absolute paths
    
    Examples:
    - C:/Users/.../Downloads/.../test_repository/unit/test_langgraph_nodes.py
      -> unit/test_langgraph_nodes.py
    - C:/Users/.../OneDrive/.../test_repository/unit/test_langgraph_nodes.py
      -> unit/test_langgraph_nodes.py
    """
    path = Path(file_path)
    
    # Try to extract relative path from test_repository
    path_str = str(path).replace('\\', '/')
    if 'test_repository' in path_str:
        # Extract everything after test_repository
        parts = path_str.split('test_repository', 1)
        if len(parts) > 1:
            relative = parts[1].lstrip('/\\')
            # Normalize separators
            normalized = relative.replace('\\', '/')
            return normalized
    
    # Fallback: use filename + parent directory
    # This handles cases where test_repository is not in path
    # but we can still identify by directory structure
    if path.parent.name in ['unit', 'integration', 'e2e', 'tests', 'test']:
        return f"{path.parent.name}/{path.name}"
    
    # Last resort: just filename (less reliable but better than nothing)
    return path.name


def find_duplicate_tests(conn=None) -> Dict[str, Any]:
    """
    Find duplicate test entries in the database.
    
    Duplicates are identified by:
    - Same normalized file path (relative to test_repository)
    - Same class_name (or both None)
    - Same method_name
    
    Args:
        conn: Optional database connection
    
    Returns:
        Dictionary with duplicate information
    """
    should_close = False
    if conn is None:
        conn = get_connection().__enter__()
        should_close = True
    
    try:
        with conn.cursor() as cursor:
            # Get all tests
            cursor.execute(f"""
                SELECT test_id, file_path, class_name, method_name, test_type
                FROM {DB_SCHEMA}.test_registry
                ORDER BY file_path, class_name, method_name
            """)
            all_tests = cursor.fetchall()
            
            # Group by normalized path + class + method
            test_groups = {}
            for row in all_tests:
                test_id, file_path, class_name, method_name, test_type = row
                # Normalize path using relative path strategy
                normalized_path = _normalize_path_for_dedup(file_path)
                
                key = (normalized_path, class_name or '', method_name)
                
                if key not in test_groups:
                    test_groups[key] = []
                test_groups[key].append({
                    'test_id': test_id,
                    'file_path': file_path,
                    'class_name': class_name,
                    'method_name': method_name,
                    'test_type': test_type
                })
            
            # Find duplicates (groups with more than 1 test)
            duplicates = {}
            total_duplicate_tests = 0
            
            for key, tests in test_groups.items():
                if len(tests) > 1:
                    normalized_path, class_name, method_name = key
                    duplicates[key] = tests
                    total_duplicate_tests += len(tests) - 1  # Keep 1, remove the rest
            
            return {
                'total_tests': len(all_tests),
                'unique_tests': len(test_groups),
                'duplicate_groups': len(duplicates),
                'duplicate_tests': total_duplicate_tests,
                'duplicates': duplicates
            }
    finally:
        if should_close:
            conn.__exit__(None, None, None)


def remove_duplicate_tests(conn=None, dry_run: bool = True) -> Dict[str, Any]:
    """
    Remove duplicate test entries, keeping the one with the lowest test_id.
    
    Args:
        conn: Optional database connection
        dry_run: If True, only report what would be removed without actually removing
    
    Returns:
        Dictionary with removal results
    """
    duplicates_info = find_duplicate_tests(conn)
    
    if duplicates_info['duplicate_groups'] == 0:
        return {
            'removed': 0,
            'kept': 0,
            'dry_run': dry_run
        }
    
    should_close = False
    if conn is None:
        conn = get_connection().__enter__()
        should_close = True
    
    try:
        test_ids_to_remove = []
        test_ids_to_keep = []
        
        for key, tests in duplicates_info['duplicates'].items():
            # Sort by test_id to keep the lowest (oldest)
            sorted_tests = sorted(tests, key=lambda x: x['test_id'])
            test_ids_to_keep.append(sorted_tests[0]['test_id'])
            # Mark others for removal
            for test in sorted_tests[1:]:
                test_ids_to_remove.append(test['test_id'])
        
        if not dry_run and test_ids_to_remove:
            # Also need to remove from related tables
            with conn.cursor() as cursor:
                # Remove from reverse_index
                placeholders = ','.join(['%s'] * len(test_ids_to_remove))
                cursor.execute(f"""
                    DELETE FROM {DB_SCHEMA}.reverse_index
                    WHERE test_id IN ({placeholders})
                """, test_ids_to_remove)
                
                # Remove from test_dependencies
                cursor.execute(f"""
                    DELETE FROM {DB_SCHEMA}.test_dependencies
                    WHERE test_id IN ({placeholders})
                """, test_ids_to_remove)
                
                # Remove from test_metadata
                cursor.execute(f"""
                    DELETE FROM {DB_SCHEMA}.test_metadata
                    WHERE test_id IN ({placeholders})
                """, test_ids_to_remove)
                
                # Finally remove from test_registry
                cursor.execute(f"""
                    DELETE FROM {DB_SCHEMA}.test_registry
                    WHERE test_id IN ({placeholders})
                """, test_ids_to_remove)
                
                conn.commit()
        
        return {
            'removed': len(test_ids_to_remove),
            'kept': len(test_ids_to_keep),
            'dry_run': dry_run,
            'test_ids_removed': test_ids_to_remove if dry_run else []
        }
    finally:
        if should_close:
            conn.__exit__(None, None, None)
