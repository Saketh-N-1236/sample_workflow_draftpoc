"""
Step 6: Load Test Structure

This script loads test repository structure information
from the test analysis JSON output into the PostgreSQL database.

What it does:
1. Reads structure data from test_analysis/outputs/07_test_structure.json
2. Connects to PostgreSQL database
3. Inserts directory structure data into test_structure table
4. Stores category information and file counts
5. Displays loading progress and statistics

Run this script:
    python deterministic/06_load_structure.py
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

# Path to structure JSON file
TEST_ANALYSIS_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs"
STRUCTURE_FILE = TEST_ANALYSIS_DIR / "07_test_structure.json"


def load_structure_json() -> dict:
    """
    Load test structure data from JSON file.
    
    Returns:
        Dictionary with structure data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    if not STRUCTURE_FILE.exists():
        raise FileNotFoundError(
            f"Structure file not found: {STRUCTURE_FILE}\n"
            f"Please run test_analysis/07_map_test_structure.py first."
        )
    
    with open(STRUCTURE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_structure_data(structure_data: dict) -> list:
    """
    Prepare structure data for database insertion.
    
    Args:
        structure_data: Dictionary from JSON file
    
    Returns:
        List of structure dictionaries ready for database insertion
    """
    directory_structure = structure_data.get('directory_structure', {})
    directories = directory_structure.get('directories', {})
    files_by_directory = directory_structure.get('files_by_directory', {})
    
    structure_list = []
    
    # Process each directory category
    for category, stats in directories.items():
        # Get files for this category
        files = files_by_directory.get(category, [])
        
        # Create structure entry
        structure_entry = {
            'directory_path': category,  # Category name as directory path
            'category': category,
            'file_count': stats.get('file_count', len(files)),
            'total_lines': stats.get('total_lines', 0)
        }
        structure_list.append(structure_entry)
    
    # Also process package structure if available
    package_structure = directory_structure.get('package_structure', {})
    for package, info in package_structure.items():
        # Check if we already have this directory
        existing = [s for s in structure_list if s['directory_path'] == package]
        if not existing:
            structure_entry = {
                'directory_path': package,
                'category': None,  # Will be determined from files
                'file_count': len(info.get('files', [])),
                'total_lines': 0  # Could be calculated if needed
            }
            structure_list.append(structure_entry)
    
    return structure_list


def load_structure_to_database(conn, structure_list: list) -> dict:
    """
    Load structure data into database.
    
    Args:
        conn: Database connection
        structure_list: List of structure dictionaries
    
    Returns:
        Dictionary with loading statistics
    """
    total_records = len(structure_list)
    loaded_count = 0
    failed_count = 0
    
    print_section(f"Loading {total_records} structure records...")
    
    try:
        with conn.cursor() as cursor:
            # Prepare values for batch insert
            values = [
                (
                    s['directory_path'],
                    s['category'],
                    s['file_count'],
                    s['total_lines']
                )
                for s in structure_list
            ]
            
            # Use execute_values for efficient batch insert
            execute_values(
                cursor,
                """
                INSERT INTO test_structure 
                (directory_path, category, file_count, total_lines)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                values
            )
            conn.commit()
            loaded_count = total_records
            
    except Exception as e:
        conn.rollback()
        print(f"Error loading structure: {e}")
        failed_count = total_records
    
    return {
        'total': total_records,
        'loaded': loaded_count,
        'failed': failed_count
    }


def get_structure_statistics(conn) -> dict:
    """
    Get statistics about loaded structure data.
    
    Args:
        conn: Database connection
    
    Returns:
        Dictionary with statistics
    """
    with conn.cursor() as cursor:
        # Total structure records
        cursor.execute("SELECT COUNT(*) FROM test_structure")
        total_records = cursor.fetchone()[0]
        
        # Total files across all directories
        cursor.execute("SELECT SUM(file_count) FROM test_structure")
        total_files = cursor.fetchone()[0] or 0
        
        # Total lines across all directories
        cursor.execute("SELECT SUM(total_lines) FROM test_structure")
        total_lines = cursor.fetchone()[0] or 0
        
        # Structure by category
        cursor.execute("""
            SELECT category, COUNT(*) as dir_count, 
                   SUM(file_count) as total_files, 
                   SUM(total_lines) as total_lines
            FROM test_structure
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY category
        """)
        by_category = cursor.fetchall()
        
        return {
            'total_records': total_records,
            'total_files': total_files,
            'total_lines': total_lines,
            'by_category': [
                {
                    'category': row[0],
                    'directory_count': row[1],
                    'file_count': row[2],
                    'line_count': row[3]
                }
                for row in by_category
            ]
        }


def main():
    """Main function to load test structure."""
    print_header("Step 6: Loading Test Structure")
    print()
    
    # Step 1: Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        return
    print()
    
    # Step 2: Load JSON data
    print_section("Loading structure data from JSON...")
    try:
        structure_data = load_structure_json()
        print_item("JSON file loaded:", str(STRUCTURE_FILE))
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    print()
    
    # Step 3: Prepare structure data
    print_section("Preparing structure data...")
    structure_list = prepare_structure_data(structure_data)
    print_item("Structure records prepared:", len(structure_list))
    print()
    
    # Step 4: Load into database
    try:
        with get_connection() as conn:
            # Check current count
            initial_count = count_table_records(conn, "test_structure")
            print_item("Structure records in database (before):", initial_count)
            print()
            
            # Load structure
            stats = load_structure_to_database(conn, structure_list)
            print()
            
            # Check final count
            final_count = count_table_records(conn, "test_structure")
            
            # Step 5: Get statistics
            struct_stats = get_structure_statistics(conn)
            print()
            
            # Step 6: Display summary
            print_section("Loading Summary:")
            print_item("Total records in JSON:", stats['total'])
            print_item("Successfully loaded:", stats['loaded'])
            if stats['failed'] > 0:
                print_item("Failed to load:", stats['failed'])
            print_item("Records in database (after):", final_count)
            print()
            
            print_section("Structure Statistics:")
            print_item("Total directories:", struct_stats['total_records'])
            print_item("Total files:", struct_stats['total_files'])
            print_item("Total lines:", struct_stats['total_lines'])
            print()
            
            # Step 7: Display by category
            if struct_stats['by_category']:
                print_section("Structure by Category:")
                for cat_info in struct_stats['by_category']:
                    print_item(f"{cat_info['category']}:", 
                              f"{cat_info['file_count']} files, {cat_info['line_count']} lines")
            print()
            
            print_header("Step 6 Complete!")
            print(f"Loaded {stats['loaded']} structure records into database")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
