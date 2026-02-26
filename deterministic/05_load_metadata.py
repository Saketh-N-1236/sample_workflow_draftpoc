"""
Step 5: Load Test Metadata

This script loads test metadata (descriptions, markers, patterns)
from the test analysis JSON output into the PostgreSQL database.

What it does:
1. Reads metadata from test_analysis/outputs/05_test_metadata.json
2. Connects to PostgreSQL database
3. Inserts test metadata into test_metadata table
4. Stores markers as JSONB for flexible querying
5. Links to test_registry via test_id
6. Displays loading progress and statistics

Run this script:
    python deterministic/05_load_metadata.py
"""

import sys
import json
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection, test_connection
from utils.db_helpers import count_table_records
from utils.output_formatter import print_header, print_section, print_item
from psycopg2.extras import execute_values

# Path to metadata JSON file
TEST_ANALYSIS_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs"
METADATA_FILE = TEST_ANALYSIS_DIR / "05_test_metadata.json"


def load_metadata_json() -> dict:
    """
    Load test metadata from JSON file.
    
    Returns:
        Dictionary with metadata data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    if not METADATA_FILE.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {METADATA_FILE}\n"
            f"Please run test_analysis/05_extract_test_metadata.py first."
        )
    
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_metadata_data(metadata_data: dict) -> list:
    """
    Prepare metadata data for database insertion.
    
    Args:
        metadata_data: Dictionary from JSON file
    
    Returns:
        List of metadata dictionaries ready for database insertion
    """
    test_metadata_list = metadata_data.get('test_metadata', [])
    
    prepared_metadata = []
    for meta in test_metadata_list:
        # Convert markers list to JSON string (will be stored as JSONB)
        markers_json = json.dumps(meta.get('markers', [])) if meta.get('markers') else None
        
        prepared_meta = {
            'test_id': meta['test_id'],
            'description': meta.get('description'),
            'markers': markers_json,  # JSON string, will be converted to JSONB
            'is_async': meta.get('is_async', False),
            'is_parameterized': meta.get('is_parameterized', False),
            'pattern': meta.get('pattern'),
            'line_number': meta.get('line_number')
        }
        prepared_metadata.append(prepared_meta)
    
    return prepared_metadata


def load_metadata_to_database(conn, metadata_list: list, batch_size: int = 50) -> dict:
    """
    Load metadata into database in batches.
    
    Args:
        conn: Database connection
        metadata_list: List of metadata dictionaries
        batch_size: Number of records to insert per batch
    
    Returns:
        Dictionary with loading statistics
    """
    total_metadata = len(metadata_list)
    loaded_count = 0
    failed_count = 0
    
    print_section(f"Loading {total_metadata} metadata records in batches of {batch_size}...")
    
    # Process in batches
    for i in range(0, total_metadata, batch_size):
        batch = metadata_list[i:i + batch_size]
        
        # Show progress
        current = min(i + batch_size, total_metadata)
        percentage = (current / total_metadata * 100) if total_metadata > 0 else 0
        print(f"Processing: {current}/{total_metadata} records ({percentage:.1f}%)", end='\r')
        
        try:
            with conn.cursor() as cursor:
                # Prepare values for batch insert
                values = [
                    (
                        m['test_id'],
                        m['description'],
                        m['markers'],  # Will be converted to JSONB
                        m['is_async'],
                        m['is_parameterized'],
                        m['pattern'],
                        m['line_number']
                    )
                    for m in batch
                ]
                
                # Use execute_values for efficient batch insert
                execute_values(
                    cursor,
                    """
                    INSERT INTO test_metadata 
                    (test_id, description, markers, is_async, is_parameterized, pattern, line_number)
                    VALUES %s
                    ON CONFLICT (test_id) DO UPDATE SET
                        description = EXCLUDED.description,
                        markers = EXCLUDED.markers,
                        is_async = EXCLUDED.is_async,
                        is_parameterized = EXCLUDED.is_parameterized,
                        pattern = EXCLUDED.pattern,
                        line_number = EXCLUDED.line_number
                    """,
                    values
                )
                conn.commit()
                loaded_count += len(batch)
        except Exception as e:
            conn.rollback()
            print(f"\nError in batch insert: {e}")
            failed_count += len(batch)
    
    print()  # New line after progress
    
    return {
        'total': total_metadata,
        'loaded': loaded_count,
        'failed': failed_count
    }


def get_metadata_statistics(conn) -> dict:
    """
    Get statistics about loaded metadata.
    
    Args:
        conn: Database connection
    
    Returns:
        Dictionary with statistics
    """
    with conn.cursor() as cursor:
        # Total metadata records
        cursor.execute("SELECT COUNT(*) FROM test_metadata")
        total_records = cursor.fetchone()[0]
        
        # Tests with descriptions
        cursor.execute("SELECT COUNT(*) FROM test_metadata WHERE description IS NOT NULL AND description != ''")
        with_descriptions = cursor.fetchone()[0]
        
        # Tests with markers
        cursor.execute("SELECT COUNT(*) FROM test_metadata WHERE markers IS NOT NULL AND markers != '[]'::jsonb")
        with_markers = cursor.fetchone()[0]
        
        # Async tests
        cursor.execute("SELECT COUNT(*) FROM test_metadata WHERE is_async = TRUE")
        async_tests = cursor.fetchone()[0]
        
        # Parameterized tests
        cursor.execute("SELECT COUNT(*) FROM test_metadata WHERE is_parameterized = TRUE")
        parameterized_tests = cursor.fetchone()[0]
        
        # Pattern distribution
        cursor.execute("""
            SELECT pattern, COUNT(*) as count
            FROM test_metadata
            WHERE pattern IS NOT NULL
            GROUP BY pattern
            ORDER BY count DESC
        """)
        patterns = cursor.fetchall()
        
        return {
            'total_records': total_records,
            'with_descriptions': with_descriptions,
            'with_markers': with_markers,
            'async_tests': async_tests,
            'parameterized_tests': parameterized_tests,
            'patterns': [{'pattern': row[0], 'count': row[1]} for row in patterns]
        }


def main():
    """Main function to load test metadata."""
    print_header("Step 5: Loading Test Metadata")
    print()
    
    # Step 1: Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        return
    print()
    
    # Step 2: Load JSON data
    print_section("Loading metadata data from JSON...")
    try:
        metadata_data = load_metadata_json()
        print_item("JSON file loaded:", str(METADATA_FILE))
        print_item("Total tests with metadata:", metadata_data.get('total_tests', 0))
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    print()
    
    # Step 3: Prepare metadata data
    print_section("Preparing metadata data...")
    metadata_list = prepare_metadata_data(metadata_data)
    print_item("Metadata records prepared:", len(metadata_list))
    print()
    
    # Step 4: Load into database
    try:
        with get_connection() as conn:
            # Check current count
            initial_count = count_table_records(conn, "test_metadata")
            print_item("Metadata records in database (before):", initial_count)
            print()
            
            # Load metadata
            stats = load_metadata_to_database(conn, metadata_list)
            print()
            
            # Check final count
            final_count = count_table_records(conn, "test_metadata")
            
            # Step 5: Get statistics
            meta_stats = get_metadata_statistics(conn)
            print()
            
            # Step 6: Display summary
            print_section("Loading Summary:")
            print_item("Total records in JSON:", stats['total'])
            print_item("Successfully loaded:", stats['loaded'])
            if stats['failed'] > 0:
                print_item("Failed to load:", stats['failed'])
            print_item("Records in database (after):", final_count)
            print()
            
            print_section("Metadata Statistics:")
            print_item("Tests with descriptions:", meta_stats['with_descriptions'])
            print_item("Tests with markers:", meta_stats['with_markers'])
            print_item("Async tests:", meta_stats['async_tests'])
            print_item("Parameterized tests:", meta_stats['parameterized_tests'])
            print()
            
            # Step 7: Display pattern distribution
            if meta_stats['patterns']:
                print_section("Test Naming Patterns:")
                for pattern_info in meta_stats['patterns']:
                    print_item(f"{pattern_info['pattern']}:", pattern_info['count'])
            print()
            
            print_header("Step 5 Complete!")
            print(f"Loaded {stats['loaded']} metadata records into database")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
