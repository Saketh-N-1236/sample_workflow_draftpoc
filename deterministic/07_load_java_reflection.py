"""
Step 7: Load Java Reflection Calls

This script loads Java reflection API calls from the analysis JSON output
into the PostgreSQL database.

What it does:
1. Reads reflection calls from test_analysis/outputs/{schema}/09_java_reflection_calls.json
2. Connects to PostgreSQL database
3. Inserts reflection call data into java_reflection_calls table
4. Displays loading progress and statistics

Run this script:
    python deterministic/07_load_java_reflection.py
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

# Path to reflection calls JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
# Resolve path relative to this script's location, not current working directory
_script_dir = Path(__file__).parent.resolve()
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs"


def load_reflection_json() -> dict:
    """
    Load reflection calls data from JSON file.
    
    Checks both main directory and _java subdirectory.
    
    Returns:
        Dictionary with reflection calls data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    # Try main directory first, then _java subdirectory
    reflection_file = TEST_ANALYSIS_DIR / "09_java_reflection_calls.json"
    if not reflection_file.exists():
        reflection_file = TEST_ANALYSIS_DIR / "_java" / "09_java_reflection_calls.json"
    
    if not reflection_file.exists():
        raise FileNotFoundError(
            f"Reflection calls file not found. Checked:\n"
            f"  - {TEST_ANALYSIS_DIR / '09_java_reflection_calls.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_java' / '09_java_reflection_calls.json'}\n"
            f"This file is only generated for Java repositories."
        )
    
    with open(reflection_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_reflection_data(reflection_data: dict) -> list:
    """
    Prepare reflection calls data for database insertion.
    
    Args:
        reflection_data: Dictionary from JSON file
    
    Returns:
        List of reflection call dictionaries ready for database insertion
    """
    reflection_calls = reflection_data.get('reflection_calls', [])
    
    prepared = []
    for call in reflection_calls:
        prepared.append({
            'test_id': call.get('test_id', ''),
            'reflection_method': call.get('reflection_method', ''),
            'target_class': call.get('target_class'),
            'target_method': call.get('target_method'),
            'target_field': call.get('target_field'),
            'line_number': call.get('line_number'),
        })
    
    return prepared


def load_reflection_to_db(conn, schema: str, reflection_calls: list):
    """
    Load reflection calls into database.
    
    Args:
        conn: Database connection
        schema: Schema name
        reflection_calls: List of reflection call dictionaries
    """
    if not reflection_calls:
        print("  No reflection calls to load.")
        return
    
    with conn.cursor() as cursor:
        # Insert reflection calls
        insert_query = f"""
            INSERT INTO {schema}.java_reflection_calls 
            (test_id, reflection_method, target_class, target_method, target_field, line_number)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        values = [
            (
                call['test_id'],
                call['reflection_method'],
                call.get('target_class'),
                call.get('target_method'),
                call.get('target_field'),
                call.get('line_number'),
            )
            for call in reflection_calls
        ]
        
        execute_values(cursor, insert_query, values)
        conn.commit()
        
        print(f"  [OK] Loaded {len(reflection_calls)} reflection calls")


def main():
    """Main function to load reflection calls."""
    print_header("Step 7: Loading Java Reflection Calls")
    print()
    
    # Get schema from environment first
    schema_name = os.getenv('TEST_REPO_SCHEMA', None)
    target_schema = schema_name or DB_SCHEMA
    
    # Test connection first (pass schema to test)
    print_section("Testing database connection...")
    if not test_connection(schema_to_test=target_schema):
        print()
        print("ERROR: Cannot connect to database!")
        print("Please check your .env file and database configuration.")
        return
    
    print()
    
    try:
        # Load JSON data
        print_section("Loading reflection calls from JSON...")
        try:
            reflection_data = load_reflection_json()
            reflection_calls = prepare_reflection_data(reflection_data)
            print(f"  [OK] Loaded {len(reflection_calls)} reflection calls from JSON")
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")
            print("  Skipping reflection calls loading (not a Java repository or file not found)")
            return
        except Exception as e:
            print(f"  [ERROR] Error loading JSON: {e}")
            return
        
        print()
        
        # Load to database
        print_section("Loading reflection calls to database...")
        with get_connection_with_schema(target_schema) as conn:
            load_reflection_to_db(conn, target_schema, reflection_calls)
            
            # Verify
            count = count_table_records(conn, 'java_reflection_calls', schema=target_schema)
            print(f"  [OK] Total reflection calls in database: {count}")
        
        print()
        print_header("Step 7 Complete!")
        print("Reflection calls loaded successfully.")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
