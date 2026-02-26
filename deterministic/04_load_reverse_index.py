"""
Step 4: Load Reverse Index

This script loads the reverse index (production code → tests mapping)
from the test analysis JSON output into the PostgreSQL database.

What it does:
1. Reads reverse index data from test_analysis/outputs/06_reverse_index.json
2. Connects to PostgreSQL database
3. Inserts reverse index entries into reverse_index table
4. Links to test_registry via test_id
5. Creates indexes for fast queries
6. Displays loading progress and statistics

The reverse index allows fast lookup: "Which tests reference this production class?"

Run this script:
    python deterministic/04_load_reverse_index.py
"""

import sys
import json
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection, test_connection
from utils.db_helpers import batch_insert_reverse_index, count_table_records
from utils.output_formatter import print_header, print_section, print_item

# Path to reverse index JSON file
TEST_ANALYSIS_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs"
REVERSE_INDEX_FILE = TEST_ANALYSIS_DIR / "06_reverse_index.json"


def load_reverse_index_json() -> dict:
    """
    Load reverse index data from JSON file.
    
    Returns:
        Dictionary with reverse index data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    if not REVERSE_INDEX_FILE.exists():
        raise FileNotFoundError(
            f"Reverse index file not found: {REVERSE_INDEX_FILE}\n"
            f"Please run test_analysis/06_build_reverse_index.py first."
        )
    
    with open(REVERSE_INDEX_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_reverse_index_data(reverse_index_data: dict) -> list:
    """
    Prepare reverse index data for database insertion.
    
    Args:
        reverse_index_data: Dictionary from JSON file
    
    Returns:
        List of reverse index dictionaries ready for database insertion
    """
    reverse_index = reverse_index_data.get('reverse_index', {})
    
    # Flatten the reverse index: each production class maps to multiple tests
    all_entries = []
    
    for production_class, tests in reverse_index.items():
        # Each test in the list
        for test_info in tests:
            entry = {
                'production_class': production_class,
                'test_id': test_info['test_id'],
                'test_file_path': test_info.get('file_path'),  # Denormalized for performance
                'reference_type': test_info.get('reference_type', 'direct_import')  # NEW: Include reference type
            }
            all_entries.append(entry)
    
    return all_entries


def load_reverse_index_to_database(conn, entries: list, batch_size: int = 100) -> dict:
    """
    Load reverse index entries into database in batches.
    
    Args:
        conn: Database connection
        entries: List of reverse index dictionaries
        batch_size: Number of entries to insert per batch
    
    Returns:
        Dictionary with loading statistics
    """
    total_entries = len(entries)
    loaded_count = 0
    failed_count = 0
    
    print_section(f"Loading {total_entries} reverse index entries in batches of {batch_size}...")
    
    # Process in batches
    for i in range(0, total_entries, batch_size):
        batch = entries[i:i + batch_size]
        
        # Show progress
        current = min(i + batch_size, total_entries)
        percentage = (current / total_entries * 100) if total_entries > 0 else 0
        print(f"Processing: {current}/{total_entries} entries ({percentage:.1f}%)", end='\r')
        
        # Insert batch
        inserted = batch_insert_reverse_index(conn, batch)
        
        if inserted == len(batch):
            loaded_count += inserted
        else:
            failed_count += (len(batch) - inserted)
            loaded_count += inserted
    
    print()  # New line after progress
    
    return {
        'total': total_entries,
        'loaded': loaded_count,
        'failed': failed_count
    }


def get_reverse_index_statistics(conn) -> dict:
    """
    Get statistics about loaded reverse index.
    
    Args:
        conn: Database connection
    
    Returns:
        Dictionary with statistics
    """
    with conn.cursor() as cursor:
        # Total entries
        cursor.execute("SELECT COUNT(*) FROM reverse_index")
        total_entries = cursor.fetchone()[0]
        
        # Unique production classes
        cursor.execute("SELECT COUNT(DISTINCT production_class) FROM reverse_index")
        unique_classes = cursor.fetchone()[0]
        
        # Unique tests
        cursor.execute("SELECT COUNT(DISTINCT test_id) FROM reverse_index")
        unique_tests = cursor.fetchone()[0]
        
        # Most referenced classes (classes with most tests)
        cursor.execute("""
            SELECT production_class, COUNT(*) as test_count
            FROM reverse_index
            GROUP BY production_class
            ORDER BY test_count DESC
            LIMIT 10
        """)
        top_classes = cursor.fetchall()
        
        return {
            'total_entries': total_entries,
            'unique_production_classes': unique_classes,
            'unique_tests': unique_tests,
            'top_classes': [{'class': row[0], 'test_count': row[1]} for row in top_classes]
        }


def main():
    """Main function to load reverse index."""
    print_header("Step 4: Loading Reverse Index")
    print()
    
    # Step 1: Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        return
    print()
    
    # Step 2: Load JSON data
    print_section("Loading reverse index data from JSON...")
    try:
        reverse_index_data = load_reverse_index_json()
        print_item("JSON file loaded:", str(REVERSE_INDEX_FILE))
        print_item("Total production classes:", 
                  reverse_index_data.get('total_production_classes', 0))
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    print()
    
    # Step 3: Prepare reverse index data
    print_section("Preparing reverse index data...")
    entries = prepare_reverse_index_data(reverse_index_data)
    print_item("Reverse index entries prepared:", len(entries))
    print()
    
    # Step 4: Load into database
    try:
        with get_connection() as conn:
            # Check current count
            initial_count = count_table_records(conn, "reverse_index")
            print_item("Reverse index entries in database (before):", initial_count)
            print()
            
            # Load reverse index
            stats = load_reverse_index_to_database(conn, entries)
            print()
            
            # Check final count
            final_count = count_table_records(conn, "reverse_index")
            
            # Step 5: Get statistics
            rev_stats = get_reverse_index_statistics(conn)
            print()
            
            # Step 6: Display summary
            print_section("Loading Summary:")
            print_item("Total entries in JSON:", stats['total'])
            print_item("Successfully loaded:", stats['loaded'])
            if stats['failed'] > 0:
                print_item("Failed to load:", stats['failed'])
            print_item("Entries in database (after):", final_count)
            print()
            
            print_section("Reverse Index Statistics:")
            print_item("Unique production classes:", rev_stats['unique_production_classes'])
            print_item("Unique tests:", rev_stats['unique_tests'])
            print_item("Average tests per class:", 
                      round(rev_stats['total_entries'] / rev_stats['unique_production_classes'], 2) 
                      if rev_stats['unique_production_classes'] > 0 else 0)
            print()
            
            # Step 7: Display top classes
            print_section("Most Referenced Production Classes (Top 10):")
            for i, class_info in enumerate(rev_stats['top_classes'], 1):
                print_item(f"{i}. {class_info['class']}:", 
                          f"{class_info['test_count']} tests")
            print()
            
            # Step 8: Test a sample query
            print_section("Testing Reverse Index Query:")
            if rev_stats['top_classes']:
                sample_class = rev_stats['top_classes'][0]['class']
                from utils.db_helpers import get_tests_for_production_class
                sample_tests = get_tests_for_production_class(conn, sample_class)
                print_item(f"Sample: Tests for '{sample_class}':", len(sample_tests))
                if sample_tests:
                    print_item("  First test:", 
                              f"{sample_tests[0]['class_name']}.{sample_tests[0]['method_name']}" 
                              if sample_tests[0]['class_name'] 
                              else sample_tests[0]['method_name'])
            print()
            
            print_header("Step 4 Complete!")
            print(f"Loaded {stats['loaded']} reverse index entries into database")
            print("Reverse index is ready for fast code → tests lookups!")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
