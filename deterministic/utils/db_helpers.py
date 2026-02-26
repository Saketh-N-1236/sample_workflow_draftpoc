"""
Database Helper Functions

This module provides reusable database helper functions for common operations
like inserting data, querying, and batch operations.

These functions make it easier to work with the database and reduce code duplication.
"""

from typing import List, Dict, Any, Optional
from psycopg2.extras import execute_batch, execute_values


def insert_test_registry(conn, test_data: Dict[str, Any]) -> bool:
    """
    Insert a single test into test_registry table.
    
    Args:
        conn: Database connection
        test_data: Dictionary with test data:
            - test_id: Unique test identifier
            - file_path: Path to test file
            - class_name: Test class name (optional)
            - method_name: Test method name
            - test_type: Type of test (unit, integration, e2e)
            - line_number: Line number (optional)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO test_registry 
                (test_id, file_path, class_name, method_name, test_type, line_number)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (test_id) DO UPDATE SET
                    file_path = EXCLUDED.file_path,
                    class_name = EXCLUDED.class_name,
                    method_name = EXCLUDED.method_name,
                    test_type = EXCLUDED.test_type,
                    line_number = EXCLUDED.line_number
            """, (
                test_data['test_id'],
                test_data['file_path'],
                test_data.get('class_name'),
                test_data['method_name'],
                test_data.get('test_type'),
                test_data.get('line_number')
            ))
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error inserting test {test_data.get('test_id')}: {e}")
        return False


def batch_insert_test_registry(conn, tests: List[Dict[str, Any]]) -> int:
    """
    Insert multiple tests in batch (more efficient than one-by-one).
    
    Args:
        conn: Database connection
        tests: List of test dictionaries
    
    Returns:
        Number of tests successfully inserted
    """
    if not tests:
        return 0
    
    try:
        with conn.cursor() as cursor:
            # Prepare data for batch insert
            values = [
                (
                    t['test_id'],
                    t['file_path'],
                    t.get('class_name'),
                    t['method_name'],
                    t.get('test_type'),
                    t.get('line_number')
                )
                for t in tests
            ]
            
            # Use execute_values for efficient batch insert
            execute_values(
                cursor,
                """
                INSERT INTO test_registry 
                (test_id, file_path, class_name, method_name, test_type, line_number)
                VALUES %s
                ON CONFLICT (test_id) DO UPDATE SET
                    file_path = EXCLUDED.file_path,
                    class_name = EXCLUDED.class_name,
                    method_name = EXCLUDED.method_name,
                    test_type = EXCLUDED.test_type,
                    line_number = EXCLUDED.line_number
                """,
                values
            )
            conn.commit()
            return len(tests)
    except Exception as e:
        conn.rollback()
        print(f"Error in batch insert: {e}")
        return 0


def insert_test_dependency(conn, test_id: str, referenced_class: str, 
                          import_type: Optional[str] = None) -> bool:
    """
    Insert a test dependency (test → production code mapping).
    
    Args:
        conn: Database connection
        test_id: Test identifier
        referenced_class: Production class/module name
        import_type: Type of import (optional)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO test_dependencies 
                (test_id, referenced_class, import_type)
                VALUES (%s, %s, %s)
            """, (test_id, referenced_class, import_type))
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error inserting dependency: {e}")
        return False


def batch_insert_test_dependencies(conn, dependencies: List[Dict[str, Any]]) -> int:
    """
    Insert multiple test dependencies in batch.
    
    Args:
        conn: Database connection
        dependencies: List of dependency dictionaries with:
            - test_id: Test identifier
            - referenced_class: Production class name
            - import_type: Type of import (optional)
    
    Returns:
        Number of dependencies inserted
    """
    if not dependencies:
        return 0
    
    try:
        with conn.cursor() as cursor:
            values = [
                (
                    d['test_id'],
                    d['referenced_class'],
                    d.get('import_type')
                )
                for d in dependencies
            ]
            
            execute_values(
                cursor,
                """
                INSERT INTO test_dependencies 
                (test_id, referenced_class, import_type)
                VALUES %s
                """,
                values
            )
            conn.commit()
            return len(dependencies)
    except Exception as e:
        conn.rollback()
        print(f"Error in batch insert dependencies: {e}")
        return 0


def insert_reverse_index(conn, production_class: str, test_id: str, 
                        test_file_path: Optional[str] = None,
                        reference_type: str = 'direct_import') -> bool:
    """
    Insert a reverse index entry (production code → test mapping).
    
    Args:
        conn: Database connection
        production_class: Production class/module name
        test_id: Test identifier
        test_file_path: Path to test file (optional, for performance)
        reference_type: Type of reference ('direct_import', 'string_ref', 'indirect')
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO reverse_index 
                (production_class, test_id, test_file_path, reference_type)
                VALUES (%s, %s, %s, %s)
            """, (production_class, test_id, test_file_path, reference_type))
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error inserting reverse index: {e}")
        return False


def batch_insert_reverse_index(conn, reverse_entries: List[Dict[str, Any]]) -> int:
    """
    Insert multiple reverse index entries in batch.
    
    Args:
        conn: Database connection
        reverse_entries: List of reverse index dictionaries
    
    Returns:
        Number of entries inserted
    """
    if not reverse_entries:
        return 0
    
    try:
        with conn.cursor() as cursor:
            values = [
                (
                    e['production_class'],
                    e['test_id'],
                    e.get('test_file_path'),
                    e.get('reference_type', 'direct_import')
                )
                for e in reverse_entries
            ]
            
            execute_values(
                cursor,
                """
                INSERT INTO reverse_index 
                (production_class, test_id, test_file_path, reference_type)
                VALUES %s
                """,
                values
            )
            conn.commit()
            return len(reverse_entries)
    except Exception as e:
        conn.rollback()
        print(f"Error in batch insert reverse index: {e}")
        return 0


def get_tests_for_production_class(conn, production_class: str, schema: str = 'planon1') -> List[Dict[str, Any]]:
    """
    Get all tests that reference a production class (using reverse index).
    
    This function matches both:
    - Exact matches: production_class = 'api.routes'
    - Sub-path matches: production_class LIKE 'api.routes.%'
    
    This is important because string references in patch() calls often use
    sub-paths like 'api.routes.get_agent' instead of just 'api.routes'.
    
    Args:
        conn: Database connection
        production_class: Production class/module name
        schema: Database schema name (default: planon1)
    
    Returns:
        List of test dictionaries with reference_type included
    """
    with conn.cursor() as cursor:
        # Get all matching tests, prioritizing exact matches and string references
        # Use a CTE to handle deduplication properly
        cursor.execute(f"""
            WITH ranked_tests AS (
                SELECT 
                    r.test_id, 
                    r.test_file_path, 
                    t.class_name, 
                    t.method_name, 
                    r.reference_type,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.test_id 
                        ORDER BY 
                            CASE WHEN r.production_class = %s THEN 1 ELSE 2 END,
                            CASE WHEN r.reference_type = 'string_ref' THEN 1 ELSE 2 END
                    ) as rn
                FROM {schema}.reverse_index r
                JOIN {schema}.test_registry t ON r.test_id = t.test_id
                WHERE r.production_class = %s
                   OR r.production_class LIKE %s
            )
            SELECT 
                test_id, 
                test_file_path, 
                class_name, 
                method_name, 
                reference_type
            FROM ranked_tests
            WHERE rn = 1
            ORDER BY 
                CASE WHEN reference_type = 'string_ref' THEN 1 ELSE 2 END,
                test_id
        """, (production_class, production_class, f"{production_class}.%"))
        
        results = cursor.fetchall()
        return [
            {
                'test_id': row[0],
                'test_file_path': row[1],
                'class_name': row[2],
                'method_name': row[3],
                'reference_type': row[4] or 'direct_import'
            }
            for row in results
        ]


def count_table_records(conn, table_name: str) -> int:
    """
    Count records in a table.
    
    Args:
        conn: Database connection
        table_name: Name of the table (without schema prefix)
    
    Returns:
        Number of records
    """
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]
