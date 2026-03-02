"""
Step 4b: Load Function Mappings

This script loads function-level mappings (test → module.function)
from the test analysis JSON output into the PostgreSQL database.

What it does:
1. Reads function mapping data from test_analysis/outputs/04b_function_calls.json
2. Connects to PostgreSQL database
3. Inserts function mappings into test_function_mapping table
4. Links to test_registry via test_id
5. Displays loading progress and statistics

The function mapping allows precise lookup: "Which tests call this specific function?"

Run this script:
    python deterministic/04b_load_function_mappings.py
"""

import sys
import json
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection, test_connection
from utils.db_helpers import batch_insert_test_function_mapping, count_table_records
from utils.output_formatter import print_header, print_section, print_item

# Path to function calls JSON file
TEST_ANALYSIS_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs"
FUNCTION_CALLS_FILE = TEST_ANALYSIS_DIR / "04b_function_calls.json"


def load_function_calls_json() -> dict:
    """
    Load function calls data from JSON file.
    
    Returns:
        Dictionary with function calls data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    if not FUNCTION_CALLS_FILE.exists():
        raise FileNotFoundError(
            f"Function calls file not found: {FUNCTION_CALLS_FILE}\n"
            f"Please run test_analysis/04b_extract_function_calls.py first."
        )
    
    with open(FUNCTION_CALLS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_function_mapping_data(function_calls_data: dict) -> list:
    """
    Prepare function mapping data for database insertion.
    
    Filters out mappings without module_name (can't query without module).
    
    Args:
        function_calls_data: Dictionary from JSON file
    
    Returns:
        List of function mapping dictionaries ready for database insertion
    """
    test_function_mappings = function_calls_data.get('test_function_mappings', [])
    
    # Filter to only include mappings with module_name (required for queries)
    valid_mappings = []
    
    for mapping in test_function_mappings:
        # Only include if we have both module_name and function_name
        if mapping.get('module_name') and mapping.get('function_name'):
            entry = {
                'test_id': mapping['test_id'],
                'module_name': mapping['module_name'],
                'function_name': mapping['function_name'],
                'call_type': mapping.get('call_type'),
                'source': mapping.get('source', 'method_call')
            }
            valid_mappings.append(entry)
    
    return valid_mappings


def load_function_mappings_to_database(conn, mappings: list, batch_size: int = 100) -> dict:
    """
    Load function mappings into database in batches.
    
    Args:
        conn: Database connection
        mappings: List of function mapping dictionaries
        batch_size: Number of mappings to insert per batch
    
    Returns:
        Dictionary with loading statistics
    """
    total_mappings = len(mappings)
    loaded_count = 0
    failed_count = 0
    
    print_section(f"Loading {total_mappings} function mappings in batches of {batch_size}...")
    
    # Process in batches
    for i in range(0, total_mappings, batch_size):
        batch = mappings[i:i + batch_size]
        
        # Show progress
        current = min(i + batch_size, total_mappings)
        percentage = (current / total_mappings * 100) if total_mappings > 0 else 0
        print(f"Processing: {current}/{total_mappings} mappings ({percentage:.1f}%)", end='\r')
        
        # Insert batch
        inserted = batch_insert_test_function_mapping(conn, batch)
        
        if inserted == len(batch):
            loaded_count += inserted
        else:
            failed_count += (len(batch) - inserted)
            loaded_count += inserted
    
    print()  # New line after progress
    
    return {
        'total': total_mappings,
        'loaded': loaded_count,
        'failed': failed_count
    }


def get_function_mapping_statistics(conn) -> dict:
    """
    Get statistics about loaded function mappings.
    
    Args:
        conn: Database connection
    
    Returns:
        Dictionary with statistics
    """
    with conn.cursor() as cursor:
        # Total mappings
        cursor.execute("SELECT COUNT(*) FROM test_function_mapping")
        total_mappings = cursor.fetchone()[0]
        
        # Unique tests
        cursor.execute("SELECT COUNT(DISTINCT test_id) FROM test_function_mapping")
        unique_tests = cursor.fetchone()[0]
        
        # Unique module.function combinations
        cursor.execute("""
            SELECT COUNT(DISTINCT module_name || '.' || function_name) 
            FROM test_function_mapping
        """)
        unique_functions = cursor.fetchone()[0]
        
        # Most called functions
        cursor.execute("""
            SELECT module_name, function_name, COUNT(*) as test_count
            FROM test_function_mapping
            GROUP BY module_name, function_name
            ORDER BY test_count DESC
            LIMIT 10
        """)
        top_functions = cursor.fetchall()
        
        # Count by source type
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM test_function_mapping
            GROUP BY source
        """)
        by_source = cursor.fetchall()
        
        return {
            'total_mappings': total_mappings,
            'unique_tests': unique_tests,
            'unique_functions': unique_functions,
            'top_functions': [
                {'module': row[0], 'function': row[1], 'test_count': row[2]} 
                for row in top_functions
            ],
            'by_source': {row[0]: row[1] for row in by_source}
        }


def main():
    """Main function to load function mappings."""
    print_header("Step 4b: Loading Function Mappings")
    print()
    
    # Step 1: Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        return
    print()
    
    # Step 2: Load JSON data
    print_section("Loading function calls data from JSON...")
    try:
        function_calls_data = load_function_calls_json()
        print_item("JSON file loaded:", str(FUNCTION_CALLS_FILE))
        print_item("Total mappings in file:", 
                  function_calls_data.get('total_mappings', 0))
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    print()
    
    # Step 3: Prepare function mapping data
    print_section("Preparing function mapping data...")
    mappings = prepare_function_mapping_data(function_calls_data)
    print_item("Valid function mappings prepared:", len(mappings))
    print_item("(Filtered out mappings without module_name)")
    print()
    
    # Step 4: Load into database
    try:
        with get_connection() as conn:
            # Check current count
            initial_count = count_table_records(conn, "test_function_mapping")
            print_item("Function mappings in database (before):", initial_count)
            print()
            
            # Load function mappings
            stats = load_function_mappings_to_database(conn, mappings)
            print()
            
            # Check final count
            final_count = count_table_records(conn, "test_function_mapping")
            
            # Step 5: Get statistics
            func_stats = get_function_mapping_statistics(conn)
            print()
            
            # Step 6: Display summary
            print_section("Loading Summary:")
            print_item("Total mappings in JSON:", stats['total'])
            print_item("Successfully loaded:", stats['loaded'])
            if stats['failed'] > 0:
                print_item("Failed to load:", stats['failed'])
            print_item("Mappings in database (after):", final_count)
            print()
            
            print_section("Function Mapping Statistics:")
            print_item("Unique tests with function calls:", func_stats['unique_tests'])
            print_item("Unique module.function combinations:", func_stats['unique_functions'])
            print_item("Average mappings per test:", 
                      round(func_stats['total_mappings'] / func_stats['unique_tests'], 2) 
                      if func_stats['unique_tests'] > 0 else 0)
            print()
            
            # Step 7: Display by source
            if func_stats['by_source']:
                print_section("Mappings by Source Type:")
                for source, count in sorted(func_stats['by_source'].items(), key=lambda x: x[1], reverse=True):
                    print_item(f"{source}:", count)
                print()
            
            # Step 8: Display top functions
            print_section("Most Called Functions (Top 10):")
            for i, func_info in enumerate(func_stats['top_functions'], 1):
                func_name = f"{func_info['module']}.{func_info['function']}"
                print_item(f"{i}. {func_name}:", f"{func_info['test_count']} tests")
            print()
            
            # Step 9: Test a sample query
            print_section("Testing Function Mapping Query:")
            if func_stats['top_functions']:
                sample_func = func_stats['top_functions'][0]
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT DISTINCT tr.test_id, tr.class_name, tr.method_name
                        FROM test_function_mapping tfm
                        JOIN test_registry tr ON tfm.test_id = tr.test_id
                        WHERE tfm.module_name = %s
                        AND tfm.function_name = %s
                        LIMIT 5
                    """, (sample_func['module'], sample_func['function']))
                    sample_tests = cursor.fetchall()
                    func_name = f"{sample_func['module']}.{sample_func['function']}"
                    print_item(f"Sample: Tests for '{func_name}':", len(sample_tests))
                    if sample_tests:
                        test_desc = f"{sample_tests[0][1]}.{sample_tests[0][2]}" if sample_tests[0][1] else sample_tests[0][2]
                        print_item("  First test:", test_desc)
            print()
            
            print_header("Step 4b Complete!")
            print(f"Loaded {stats['loaded']} function mappings into database")
            print("Function mappings are ready for precise function-level test selection!")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
