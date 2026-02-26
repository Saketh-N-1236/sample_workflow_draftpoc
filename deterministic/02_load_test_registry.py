"""
Step 2: Load Test Registry

This script loads test registry data from the test analysis JSON output
into the PostgreSQL database.

What it does:
1. Reads test registry data from test_analysis/outputs/03_test_registry.json
2. Connects to PostgreSQL database
3. Inserts all tests into test_registry table
4. Handles duplicates (updates if test_id already exists)
5. Displays loading progress
6. Shows summary statistics

Run this script:
    python deterministic/02_load_test_registry.py
"""

import sys
import json
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection, test_connection
from utils.db_helpers import batch_insert_test_registry, count_table_records
from utils.output_formatter import print_header, print_section, print_item

# Path to test registry JSON file
TEST_ANALYSIS_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs"
TEST_REGISTRY_FILE = TEST_ANALYSIS_DIR / "03_test_registry.json"


def load_test_registry_json() -> dict:
    """
    Load test registry data from JSON file.
    
    Returns:
        Dictionary with test registry data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    if not TEST_REGISTRY_FILE.exists():
        raise FileNotFoundError(
            f"Test registry file not found: {TEST_REGISTRY_FILE}\n"
            f"Please run test_analysis/03_build_test_registry.py first."
        )
    
    with open(TEST_REGISTRY_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Extract data from the nested structure
        return data.get('data', data)


def prepare_test_data(registry_data: dict) -> list:
    """
    Prepare test data for database insertion.
    
    Args:
        registry_data: Dictionary from JSON file
    
    Returns:
        List of test dictionaries ready for database insertion
    """
    tests = registry_data.get('tests', [])
    
    # Ensure all required fields are present
    prepared_tests = []
    for test in tests:
        prepared_test = {
            'test_id': test['test_id'],
            'file_path': test['file_path'],
            'class_name': test.get('class_name'),
            'method_name': test['method_name'],
            'test_type': test.get('test_type'),
            'line_number': test.get('line_number')
        }
        prepared_tests.append(prepared_test)
    
    return prepared_tests


def load_tests_to_database(conn, tests: list, batch_size: int = 50) -> dict:
    """
    Load tests into database in batches.
    
    Args:
        conn: Database connection
        tests: List of test dictionaries
        batch_size: Number of tests to insert per batch (default: 50)
    
    Returns:
        Dictionary with loading statistics
    """
    total_tests = len(tests)
    loaded_count = 0
    failed_count = 0
    
    print_section(f"Loading {total_tests} tests in batches of {batch_size}...")
    print()
    
    # Process in batches
    for i in range(0, total_tests, batch_size):
        batch = tests[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_tests + batch_size - 1) // batch_size
        
        print_progress(i + len(batch), total_tests, "tests")
        
        # Insert batch
        inserted = batch_insert_test_registry(conn, batch)
        
        if inserted == len(batch):
            loaded_count += inserted
        else:
            failed_count += (len(batch) - inserted)
            loaded_count += inserted
    
    print()  # New line after progress
    
    return {
        'total': total_tests,
        'loaded': loaded_count,
        'failed': failed_count
    }


def print_progress(current: int, total: int, item_name: str = "items") -> None:
    """
    Print a progress indicator.
    
    Args:
        current: Current item number
        total: Total number of items
        item_name: Name of the items being processed
    """
    percentage = (current / total * 100) if total > 0 else 0
    print(f"Processing: {current}/{total} {item_name} ({percentage:.1f}%)", end='\r')
    
    # Print newline when complete
    if current == total:
        print()  # Move to next line


def main():
    """Main function to load test registry."""
    print_header("Step 2: Loading Test Registry")
    print()
    
    # Step 1: Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        return
    print()
    
    # Step 2: Load JSON data
    print_section("Loading test registry data from JSON...")
    try:
        registry_data = load_test_registry_json()
        print_item("JSON file loaded:", str(TEST_REGISTRY_FILE))
        print_item("Total tests in file:", registry_data.get('total_tests', 0))
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON file: {e}")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    print()
    
    # Step 3: Prepare test data
    print_section("Preparing test data...")
    tests = prepare_test_data(registry_data)
    print_item("Tests prepared:", len(tests))
    print()
    
    # Step 4: Load into database
    try:
        with get_connection() as conn:
            # Check current count
            initial_count = count_table_records(conn, "test_registry")
            print_item("Tests in database (before):", initial_count)
            print()
            
            # Load tests
            stats = load_tests_to_database(conn, tests)
            
            # Check final count
            final_count = count_table_records(conn, "test_registry")
            print()
            
            # Step 5: Display summary
            print_section("Loading Summary:")
            print_item("Total tests in JSON:", stats['total'])
            print_item("Successfully loaded:", stats['loaded'])
            if stats['failed'] > 0:
                print_item("Failed to load:", stats['failed'])
            print_item("Tests in database (after):", final_count)
            print()
            
            # Step 6: Display sample tests
            print_section("Sample Tests (first 5):")
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT test_id, class_name, method_name, test_type
                    FROM test_registry
                    ORDER BY test_id
                    LIMIT 5
                """)
                for row in cursor.fetchall():
                    test_id, class_name, method_name, test_type = row
                    test_desc = f"{class_name}.{method_name}" if class_name else method_name
                    print_item(f"{test_id}:", f"{test_desc} ({test_type})")
            print()
            
            print_header("Step 2 Complete!")
            print(f"Loaded {stats['loaded']} tests into database")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
