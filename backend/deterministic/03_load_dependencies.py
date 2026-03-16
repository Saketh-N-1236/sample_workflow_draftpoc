"""
Step 3: Load Test Dependencies

This script loads test dependencies (test → production code mappings)
from the test analysis JSON output into the PostgreSQL database.

What it does:
1. Reads dependency data from test_analysis/outputs/04_static_dependencies.json
2. Connects to PostgreSQL database
3. Inserts test dependencies into test_dependencies table
4. Links dependencies to test_registry via test_id
5. Displays loading progress and statistics

Run this script:
    python deterministic/03_load_dependencies.py
"""

import sys
import json
import os
from pathlib import Path
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection, get_connection_with_schema, test_connection, DB_SCHEMA
import os
from utils.db_helpers import batch_insert_test_dependencies, count_table_records
from utils.output_formatter import print_header, print_section, print_item

# Path to dependencies JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs"
DEPENDENCIES_FILE = TEST_ANALYSIS_DIR / "04_static_dependencies.json"


def load_dependencies_json() -> dict:
    """
    Load test dependencies data from JSON file.
    
    Returns:
        Dictionary with dependency data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    if not DEPENDENCIES_FILE.exists():
        raise FileNotFoundError(
            f"Dependencies file not found: {DEPENDENCIES_FILE}\n"
            f"Please run test_analysis/04_extract_static_dependencies.py first."
        )
    
    with open(DEPENDENCIES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_dependency_data(dependencies_data: dict) -> list:
    """
    Prepare dependency data for database insertion.
    
    Args:
        dependencies_data: Dictionary from JSON file
    
    Returns:
        List of dependency dictionaries ready for database insertion
    """
    test_dependencies = dependencies_data.get('test_dependencies', [])
    
    # Flatten the dependencies: each test can have multiple referenced classes
    all_dependencies = []
    
    for test_dep in test_dependencies:
        test_id = test_dep['test_id']
        referenced_classes = test_dep.get('referenced_classes', [])
        
        # Create one dependency record per referenced class
        for ref_class in referenced_classes:
            dependency = {
                'test_id': test_id,
                'referenced_class': ref_class,
                'import_type': None  # Could be enhanced to detect import type
            }
            all_dependencies.append(dependency)
    
    return all_dependencies


def load_dependencies_to_database(conn, dependencies: list, schema: Optional[str] = None, batch_size: int = 100) -> dict:
    """
    Load dependencies into database in batches.
    
    Args:
        conn: Database connection
        dependencies: List of dependency dictionaries
        batch_size: Number of dependencies to insert per batch
    
    Returns:
        Dictionary with loading statistics
    """
    total_deps = len(dependencies)
    loaded_count = 0
    failed_count = 0
    
    print_section(f"Loading {total_deps} dependencies in batches of {batch_size}...")
    
    # Process in batches
    for i in range(0, total_deps, batch_size):
        batch = dependencies[i:i + batch_size]
        
        # Show progress
        current = min(i + batch_size, total_deps)
        percentage = (current / total_deps * 100) if total_deps > 0 else 0
        print(f"Processing: {current}/{total_deps} dependencies ({percentage:.1f}%)", end='\r')
        
        # Insert batch
        inserted = batch_insert_test_dependencies(conn, batch, schema=schema)
        
        if inserted == len(batch):
            loaded_count += inserted
        else:
            failed_count += (len(batch) - inserted)
            loaded_count += inserted
    
    print()  # New line after progress
    
    return {
        'total': total_deps,
        'loaded': loaded_count,
        'failed': failed_count
    }


def get_dependency_statistics(conn, schema: Optional[str] = None) -> dict:
    """
    Get statistics about loaded dependencies.
    
    Args:
        conn: Database connection
        schema: Optional schema name (defaults to DB_SCHEMA or search_path)
    
    Returns:
        Dictionary with statistics
    """
    target_schema = schema or DB_SCHEMA
    table_name = f"{target_schema}.test_dependencies" if schema else "test_dependencies"
    
    with conn.cursor() as cursor:
        # Total dependencies
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_deps = cursor.fetchone()[0]
        
        # Unique production classes referenced
        cursor.execute(f"SELECT COUNT(DISTINCT referenced_class) FROM {table_name}")
        unique_classes = cursor.fetchone()[0]
        
        # Tests with dependencies
        cursor.execute(f"SELECT COUNT(DISTINCT test_id) FROM {table_name}")
        tests_with_deps = cursor.fetchone()[0]
        
        # Most referenced classes
        cursor.execute(f"""
            SELECT referenced_class, COUNT(*) as count
            FROM {table_name}
            GROUP BY referenced_class
            ORDER BY count DESC
            LIMIT 10
        """)
        top_classes = cursor.fetchall()
        
        return {
            'total_dependencies': total_deps,
            'unique_classes': unique_classes,
            'tests_with_dependencies': tests_with_deps,
            'top_classes': [{'class': row[0], 'count': row[1]} for row in top_classes]
        }


def main():
    """Main function to load test dependencies."""
    print_header("Step 3: Loading Test Dependencies")
    print()
    
    # Get schema from environment (for multi-repo support)
    schema_name = os.getenv('TEST_REPO_SCHEMA', None)
    target_schema = schema_name or DB_SCHEMA
    if schema_name:
        print_section(f"Using schema: {target_schema}")
        print()
    
    # Step 1: Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        return
    print()
    
    # Step 2: Load JSON data
    print_section("Loading dependencies data from JSON...")
    try:
        dependencies_data = load_dependencies_json()
        print_item("JSON file loaded:", str(DEPENDENCIES_FILE))
        print_item("Total tests with dependencies:", 
                  dependencies_data.get('tests_with_dependencies', 0))
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    print()
    
    # Step 3: Prepare dependency data
    print_section("Preparing dependency data...")
    dependencies = prepare_dependency_data(dependencies_data)
    print_item("Dependencies prepared:", len(dependencies))
    print()
    
    # Step 4: Load into database
    try:
        # Use schema-specific connection if schema_name is provided
        schema_name = os.getenv('TEST_REPO_SCHEMA')
        if schema_name:
            conn_context = get_connection_with_schema(schema_name)
        else:
            conn_context = get_connection()
        
        with conn_context as conn:
            # Check current count
            initial_count = count_table_records(conn, "test_dependencies", schema=schema_name)
            print_item("Dependencies in database (before):", initial_count)
            print()
            
            # Load dependencies
            stats = load_dependencies_to_database(conn, dependencies, schema=schema_name)
            print()
            
            # Check final count
            final_count = count_table_records(conn, "test_dependencies", schema=schema_name)
            
            # Step 5: Get statistics
            dep_stats = get_dependency_statistics(conn, schema=schema_name)
            print()
            
            # Step 6: Display summary
            print_section("Loading Summary:")
            print_item("Total dependencies in JSON:", stats['total'])
            print_item("Successfully loaded:", stats['loaded'])
            if stats['failed'] > 0:
                print_item("Failed to load:", stats['failed'])
            print_item("Dependencies in database (after):", final_count)
            print()
            
            print_section("Dependency Statistics:")
            print_item("Unique production classes:", dep_stats['unique_classes'])
            print_item("Tests with dependencies:", dep_stats['tests_with_dependencies'])
            print()
            
            # Step 7: Display top referenced classes
            print_section("Most Referenced Production Classes (Top 10):")
            for i, class_info in enumerate(dep_stats['top_classes'], 1):
                print_item(f"{i}. {class_info['class']}:", f"{class_info['count']} references")
            print()
            
            print_header("Step 3 Complete!")
            print(f"Loaded {stats['loaded']} dependencies into database")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
