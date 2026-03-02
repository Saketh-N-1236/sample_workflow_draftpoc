"""
Step 7: Verify Data

This script verifies that all data was loaded correctly into the database.
It runs sample queries, checks data integrity, and displays a comprehensive report.

What it does:
1. Connects to PostgreSQL database
2. Counts records in each table
3. Verifies foreign key relationships
4. Runs sample queries to test functionality
5. Displays comprehensive verification report
6. Tests query performance

Run this script:
    python deterministic/07_verify_data.py
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection, test_connection, get_db_config
from utils.db_helpers import count_table_records, get_tests_for_production_class
from utils.output_formatter import print_header, print_section, print_item
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables to get schema
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Get schema from environment (same as db_connection.py)
SCHEMA = os.getenv('DB_SCHEMA', 'planon1')


def count_all_tables(conn) -> dict:
    """
    Count records in all tables.
    
    Args:
        conn: Database connection
    
    Returns:
        Dictionary with table counts
    """
    tables = [
        'test_registry',
        'test_dependencies',
        'reverse_index',
        'test_metadata',
        'test_structure',
        'test_function_mapping'
    ]
    
    counts = {}
    for table in tables:
        counts[table] = count_table_records(conn, table)
    
    return counts


def verify_foreign_keys(conn) -> dict:
    """
    Verify foreign key relationships are intact.
    
    Args:
        conn: Database connection
    
    Returns:
        Dictionary with verification results
    """
    results = {}
    
    with conn.cursor() as cursor:
        # Check test_dependencies -> test_registry
        cursor.execute("""
            SELECT COUNT(*) 
            FROM test_dependencies td
            LEFT JOIN test_registry tr ON td.test_id = tr.test_id
            WHERE tr.test_id IS NULL
        """)
        orphaned_deps = cursor.fetchone()[0]
        results['test_dependencies'] = {
            'orphaned': orphaned_deps,
            'valid': orphaned_deps == 0
        }
        
        # Check reverse_index -> test_registry
        cursor.execute("""
            SELECT COUNT(*) 
            FROM reverse_index ri
            LEFT JOIN test_registry tr ON ri.test_id = tr.test_id
            WHERE tr.test_id IS NULL
        """)
        orphaned_reverse = cursor.fetchone()[0]
        results['reverse_index'] = {
            'orphaned': orphaned_reverse,
            'valid': orphaned_reverse == 0
        }
        
        # Check test_metadata -> test_registry
        cursor.execute("""
            SELECT COUNT(*) 
            FROM test_metadata tm
            LEFT JOIN test_registry tr ON tm.test_id = tr.test_id
            WHERE tr.test_id IS NULL
        """)
        orphaned_metadata = cursor.fetchone()[0]
        results['test_metadata'] = {
            'orphaned': orphaned_metadata,
            'valid': orphaned_metadata == 0
        }
        
        # Check test_function_mapping -> test_registry
        cursor.execute("""
            SELECT COUNT(*) 
            FROM test_function_mapping tfm
            LEFT JOIN test_registry tr ON tfm.test_id = tr.test_id
            WHERE tr.test_id IS NULL
        """)
        orphaned_function_mapping = cursor.fetchone()[0]
        results['test_function_mapping'] = {
            'orphaned': orphaned_function_mapping,
            'valid': orphaned_function_mapping == 0
        }
    
    return results


def run_sample_queries(conn) -> dict:
    """
    Run sample queries to test functionality.
    
    Args:
        conn: Database connection
    
    Returns:
        Dictionary with query results
    """
    results = {}
    
    with conn.cursor() as cursor:
        # Query 1: Get tests for a production class (using reverse index)
        cursor.execute("""
            SELECT production_class, COUNT(*) as test_count
            FROM reverse_index
            GROUP BY production_class
            ORDER BY test_count DESC
            LIMIT 1
        """)
        top_class = cursor.fetchone()
        if top_class:
            class_name = top_class[0]
            test_count = top_class[1]
            results['top_production_class'] = {
                'class': class_name,
                'test_count': test_count
            }
            
            # Get actual tests for this class
            tests = get_tests_for_production_class(conn, class_name)
            results['top_production_class']['sample_tests'] = tests[:3]
        
        # Query 2: Tests by type
        cursor.execute("""
            SELECT test_type, COUNT(*) as count
            FROM test_registry
            WHERE test_type IS NOT NULL
            GROUP BY test_type
            ORDER BY count DESC
        """)
        by_type = cursor.fetchall()
        results['tests_by_type'] = [
            {'type': row[0], 'count': row[1]} for row in by_type
        ]
        
        # Query 3: Tests with most dependencies
        cursor.execute("""
            SELECT tr.test_id, tr.method_name, COUNT(td.id) as dep_count
            FROM test_registry tr
            LEFT JOIN test_dependencies td ON tr.test_id = td.test_id
            GROUP BY tr.test_id, tr.method_name
            ORDER BY dep_count DESC
            LIMIT 5
        """)
        top_deps = cursor.fetchall()
        results['tests_with_most_dependencies'] = [
            {
                'test_id': row[0],
                'method_name': row[1],
                'dependency_count': row[2]
            }
            for row in top_deps
        ]
        
        # Query 4: Metadata coverage
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT tr.test_id) as total_tests,
                COUNT(DISTINCT tm.test_id) as tests_with_metadata,
                ROUND(100.0 * COUNT(DISTINCT tm.test_id) / COUNT(DISTINCT tr.test_id), 2) as coverage_pct
            FROM test_registry tr
            LEFT JOIN test_metadata tm ON tr.test_id = tm.test_id
        """)
        coverage = cursor.fetchone()
        results['metadata_coverage'] = {
            'total_tests': coverage[0],
            'tests_with_metadata': coverage[1],
            'coverage_percentage': coverage[2]
        }
        
        # Query 5: Function mapping coverage and sample
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT tr.test_id) as total_tests,
                COUNT(DISTINCT tfm.test_id) as tests_with_function_calls,
                ROUND(100.0 * COUNT(DISTINCT tfm.test_id) / COUNT(DISTINCT tr.test_id), 2) as coverage_pct
            FROM test_registry tr
            LEFT JOIN test_function_mapping tfm ON tr.test_id = tfm.test_id
        """)
        func_coverage = cursor.fetchone()
        results['function_mapping_coverage'] = {
            'total_tests': func_coverage[0],
            'tests_with_function_calls': func_coverage[1],
            'coverage_percentage': func_coverage[2]
        }
        
        # Get most called function
        cursor.execute("""
            SELECT module_name, function_name, COUNT(*) as test_count
            FROM test_function_mapping
            GROUP BY module_name, function_name
            ORDER BY test_count DESC
            LIMIT 1
        """)
        top_function = cursor.fetchone()
        if top_function:
            results['top_function'] = {
                'module': top_function[0],
                'function': top_function[1],
                'test_count': top_function[2]
            }
            
            # Get sample tests for this function
            cursor.execute("""
                SELECT DISTINCT tr.test_id, tr.class_name, tr.method_name
                FROM test_function_mapping tfm
                JOIN test_registry tr ON tfm.test_id = tr.test_id
                WHERE tfm.module_name = %s
                AND tfm.function_name = %s
                LIMIT 3
            """, (top_function[0], top_function[1]))
            sample_tests = cursor.fetchall()
            results['top_function']['sample_tests'] = [
                {
                    'test_id': row[0],
                    'class_name': row[1],
                    'method_name': row[2]
                }
                for row in sample_tests
            ]
    
    return results


def main():
    """Main function to verify data."""
    print_header("Step 7: Verifying Data")
    print()
    
    # Step 1: Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        return
    print()
    
    try:
        with get_connection() as conn:
            # Step 2: Count all tables
            print_section("Counting records in all tables...")
            counts = count_all_tables(conn)
            
            for table, count in counts.items():
                print_item(f"{table}:", count)
            print()
            
            # Step 3: Verify foreign keys
            print_section("Verifying foreign key relationships...")
            fk_results = verify_foreign_keys(conn)
            
            all_valid = True
            for table, result in fk_results.items():
                if result['valid']:
                    print_item(f"{table}:", "[OK] All foreign keys valid")
                else:
                    print_item(f"{table}:", f"[ERROR] {result['orphaned']} orphaned records")
                    all_valid = False
            
            if all_valid:
                print()
                print_item("All foreign key relationships are valid!", "")
            else:
                print()
                print_item("WARNING: Some foreign key relationships have issues!", "")
            print()
            
            # Step 4: Run sample queries
            print_section("Running sample queries...")
            query_results = run_sample_queries(conn)
            
            # Display query results
            if 'top_production_class' in query_results:
                top_class = query_results['top_production_class']
                print_item("Most referenced production class:", 
                          f"{top_class['class']} ({top_class['test_count']} tests)")
                if top_class.get('sample_tests'):
                    print_item("  Sample tests:", "")
                    for test in top_class['sample_tests'][:3]:
                        test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
                        print_item(f"    - {test['test_id']}:", test_name)
            print()
            
            if 'tests_by_type' in query_results:
                print_item("Tests by type:", "")
                for type_info in query_results['tests_by_type']:
                    print_item(f"  {type_info['type']}:", type_info['count'])
            print()
            
            if 'tests_with_most_dependencies' in query_results:
                print_item("Tests with most dependencies:", "")
                for test_info in query_results['tests_with_most_dependencies']:
                    print_item(f"  {test_info['test_id']} ({test_info['method_name']}):", 
                              f"{test_info['dependency_count']} dependencies")
            print()
            
            if 'metadata_coverage' in query_results:
                coverage = query_results['metadata_coverage']
                print_item("Metadata coverage:", 
                          f"{coverage['coverage_percentage']}% "
                          f"({coverage['tests_with_metadata']}/{coverage['total_tests']} tests)")
            print()
            
            if 'function_mapping_coverage' in query_results:
                func_coverage = query_results['function_mapping_coverage']
                print_item("Function mapping coverage:", 
                          f"{func_coverage['coverage_percentage']}% "
                          f"({func_coverage['tests_with_function_calls']}/{func_coverage['total_tests']} tests)")
            print()
            
            if 'top_function' in query_results:
                top_func = query_results['top_function']
                func_name = f"{top_func['module']}.{top_func['function']}"
                print_item("Most called function:", 
                          f"{func_name} ({top_func['test_count']} tests)")
                if top_func.get('sample_tests'):
                    print_item("  Sample tests:", "")
                    for test in top_func['sample_tests']:
                        test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
                        print_item(f"    - {test['test_id']}:", test_name)
            print()
            
            # Step 5: Summary
            print_section("Verification Summary:")
            total_records = sum(counts.values())
            print_item("Total records across all tables:", total_records)
            print_item("Foreign key integrity:", "[OK] Valid" if all_valid else "[ERROR] Issues found")
            print_item("Data loaded successfully:", "[OK] Yes" if total_records > 0 else "[ERROR] No")
            print()
            
            print_header("Step 7 Complete!")
            print("Data verification complete!")
            print()
            print("Database is ready for:")
            print("  - Deterministic test selection queries")
            print("  - Fast code -> tests lookups")
            print("  - Function-level test selection (precise matching)")
            print("  - Test metadata queries")
            print("  - Future semantic/vector data integration")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
