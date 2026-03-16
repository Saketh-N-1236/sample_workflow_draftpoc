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
import os
from pathlib import Path
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection, get_connection_with_schema, test_connection, DB_SCHEMA
from utils.db_helpers import count_table_records
from utils.output_formatter import print_header, print_section, print_item
from psycopg2.extras import execute_values

# Path to structure JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
# Resolve path relative to this script's location, not current working directory
_script_dir = Path(__file__).parent.resolve()
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs"


def load_structure_json() -> dict:
    """
    Load test structure data from JSON file.
    
    Checks both main directory and language-specific subdirectories.
    
    Returns:
        Dictionary with structure data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    # Try main directory first, then _java, _python, _javascript subdirectories
    structure_file = TEST_ANALYSIS_DIR / "07_test_structure.json"
    if not structure_file.exists():
        # Try language-specific subdirectories
        for lang_dir in ['_java', '_python', '_javascript', '_js']:
            candidate = TEST_ANALYSIS_DIR / lang_dir / "07_test_structure.json"
            if candidate.exists():
                structure_file = candidate
                break
    
    if not structure_file.exists():
        raise FileNotFoundError(
            f"Structure file not found. Checked:\n"
            f"  - {TEST_ANALYSIS_DIR / '07_test_structure.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_java' / '07_test_structure.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_python' / '07_test_structure.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_javascript' / '07_test_structure.json'}\n"
            f"Please run test analysis first."
        )
    
    with open(structure_file, 'r', encoding='utf-8') as f:
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
    # First, try to use structure_rows if available (new format with test_count)
    structure_rows = structure_data.get('structure_rows', [])
    if structure_rows:
        return structure_rows
    
    # Fallback to old format
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
            'test_count': stats.get('test_count', 0),
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
                'test_count': 0,  # Could be calculated from test registry if needed
                'total_lines': 0  # Could be calculated if needed
            }
            structure_list.append(structure_entry)
    
    return structure_list


def load_structure_to_database(conn, structure_list: list, schema: Optional[str] = None) -> dict:
    """
    Load structure data into database.
    
    Args:
        conn: Database connection
        structure_list: List of structure dictionaries
        schema: Optional schema name (defaults to DB_SCHEMA or search_path)
    
    Returns:
        Dictionary with loading statistics
    """
    total_records = len(structure_list)
    loaded_count = 0
    failed_count = 0
    
    target_schema = schema or DB_SCHEMA
    table_name = f"{target_schema}.test_structure" if schema else "test_structure"
    
    print_section(f"Loading {total_records} structure records...")
    
    try:
        with conn.cursor() as cursor:
            # Check if unique constraint exists on directory_path
            cursor.execute(f"""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_schema = %s 
                AND table_name = 'test_structure' 
                AND constraint_type = 'UNIQUE'
                AND constraint_name IN (
                    SELECT constraint_name 
                    FROM information_schema.constraint_column_usage 
                    WHERE table_schema = %s 
                    AND table_name = 'test_structure' 
                    AND column_name = 'directory_path'
                )
            """, (target_schema, target_schema))
            has_unique = cursor.fetchone() is not None
            
            # Prepare values for batch insert
            values = [
                (
                    s['directory_path'],
                    s['category'],
                    s['file_count'],
                    s.get('test_count', 0),
                    s['total_lines']
                )
                for s in structure_list
            ]
            
            # Use execute_values for efficient batch insert
            if has_unique:
                # Use ON CONFLICT if unique constraint exists
                execute_values(
                    cursor,
                    f"""
                    INSERT INTO {table_name} 
                    (directory_path, category, file_count, test_count, total_lines)
                    VALUES %s
                    ON CONFLICT (directory_path) DO UPDATE SET
                        category = EXCLUDED.category,
                        file_count = EXCLUDED.file_count,
                        test_count = EXCLUDED.test_count,
                        total_lines = EXCLUDED.total_lines
                    """,
                    values
                )
            else:
                # Delete existing records first, then insert
                for value in values:
                    cursor.execute(
                        f"DELETE FROM {table_name} WHERE directory_path = %s",
                        (value[0],)
                    )
                execute_values(
                    cursor,
                    f"""
                    INSERT INTO {table_name} 
                    (directory_path, category, file_count, test_count, total_lines)
                    VALUES %s
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


def get_structure_statistics(conn, schema: Optional[str] = None) -> dict:
    """
    Get statistics about loaded structure data.
    
    Args:
        conn: Database connection
        schema: Optional schema name (defaults to DB_SCHEMA or search_path)
    
    Returns:
        Dictionary with statistics
    """
    target_schema = schema or DB_SCHEMA
    table_name = f"{target_schema}.test_structure" if schema else "test_structure"
    
    with conn.cursor() as cursor:
        # Total structure records
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_records = cursor.fetchone()[0]
        
        # Total files across all directories
        cursor.execute(f"SELECT SUM(file_count) FROM {table_name}")
        total_files = cursor.fetchone()[0] or 0
        
        # Total lines across all directories
        cursor.execute(f"SELECT SUM(total_lines) FROM {table_name}")
        total_lines = cursor.fetchone()[0] or 0
        
        # Structure by category
        cursor.execute(f"""
            SELECT category, COUNT(*) as dir_count, 
                   SUM(file_count) as total_files, 
                   SUM(total_lines) as total_lines
            FROM {table_name}
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
    
    # Get schema from environment (for multi-repo support)
    schema_name = os.getenv('TEST_REPO_SCHEMA', None)
    target_schema = schema_name or DB_SCHEMA
    if schema_name:
        print_section(f"Using schema: {target_schema}")
        print()
    
    # Step 1: Test database connection (pass schema to test)
    print_section("Testing database connection...")
    if not test_connection(schema_to_test=target_schema):
        print()
        print("ERROR: Cannot connect to database!")
        return
    print()
    
    # Step 2: Load JSON data
    print_section("Loading structure data from JSON...")
    try:
        structure_data = load_structure_json()
        # Get the actual file path that was found
        structure_file = TEST_ANALYSIS_DIR / "07_test_structure.json"
        if not structure_file.exists():
            for lang_dir in ['_java', '_python', '_javascript', '_js']:
                candidate = TEST_ANALYSIS_DIR / lang_dir / "07_test_structure.json"
                if candidate.exists():
                    structure_file = candidate
                    break
        print_item("JSON file loaded:", str(structure_file))
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
        # Use schema-specific connection if schema_name is provided
        if schema_name:
            conn_context = get_connection_with_schema(schema_name)
        else:
            conn_context = get_connection()
        
        with conn_context as conn:
            # Check current count
            initial_count = count_table_records(conn, "test_structure", schema=schema_name)
            print_item("Structure records in database (before):", initial_count)
            print()
            
            # Load structure
            stats = load_structure_to_database(conn, structure_list, schema=schema_name)
            print()
            
            # Check final count
            final_count = count_table_records(conn, "test_structure", schema=schema_name)
            
            # Step 5: Get statistics
            struct_stats = get_structure_statistics(conn, schema=schema_name)
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
