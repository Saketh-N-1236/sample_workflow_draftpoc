"""
Step 8: Load Java DI Fields

This script loads Java dependency injection fields from the analysis JSON output
into the PostgreSQL database.

What it does:
1. Reads DI fields from test_analysis/outputs/{schema}/10_java_di_fields.json
2. Connects to PostgreSQL database
3. Inserts DI field data into java_di_fields table
4. Displays loading progress and statistics

Run this script:
    python deterministic/08_load_java_di_fields.py
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

# Path to DI fields JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
# Resolve path relative to this script's location, not current working directory
_script_dir = Path(__file__).parent.resolve()
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs"


def load_di_fields_json() -> dict:
    """
    Load DI fields data from JSON file.
    
    Checks both main directory and _java subdirectory.
    
    Returns:
        Dictionary with DI fields data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    # Try main directory first, then _java subdirectory
    di_fields_file = TEST_ANALYSIS_DIR / "10_java_di_fields.json"
    if not di_fields_file.exists():
        di_fields_file = TEST_ANALYSIS_DIR / "_java" / "10_java_di_fields.json"
    
    if not di_fields_file.exists():
        raise FileNotFoundError(
            f"DI fields file not found. Checked:\n"
            f"  - {TEST_ANALYSIS_DIR / '10_java_di_fields.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_java' / '10_java_di_fields.json'}\n"
            f"This file is only generated for Java repositories."
        )
    
    with open(di_fields_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_di_fields_data(di_fields_data: dict) -> list:
    """
    Prepare DI fields data for database insertion.
    
    Args:
        di_fields_data: Dictionary from JSON file
    
    Returns:
        List of DI field dictionaries ready for database insertion
    """
    di_fields = di_fields_data.get('di_fields', [])
    
    prepared = []
    for field in di_fields:
        annotation_names = field.get('annotation_names', [])
        prepared.append({
            'test_id': field.get('test_id', ''),
            'field_name': field.get('field_name', ''),
            'field_type': field.get('field_type', ''),
            'injection_type': field.get('injection_type', 'field'),
            'annotation_names': annotation_names,
        })
    
    return prepared


def load_di_fields_to_db(conn, schema: str, di_fields: list):
    """
    Load DI fields into database.
    
    Args:
        conn: Database connection
        schema: Schema name
        di_fields: List of DI field dictionaries
    """
    if not di_fields:
        print("  No DI fields to load.")
        return
    
    with conn.cursor() as cursor:
        # Insert DI fields
        insert_query = f"""
            INSERT INTO {schema}.java_di_fields 
            (test_id, field_name, field_type, injection_type, annotation_names)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        values = [
            (
                field['test_id'],
                field['field_name'],
                field['field_type'],
                field['injection_type'],
                field['annotation_names'],
            )
            for field in di_fields
        ]
        
        execute_values(cursor, insert_query, values)
        conn.commit()
        
        print(f"  [OK] Loaded {len(di_fields)} DI fields")


def main():
    """Main function to load DI fields."""
    print_header("Step 8: Loading Java DI Fields")
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
        print_section("Loading DI fields from JSON...")
        try:
            di_fields_data = load_di_fields_json()
            di_fields = prepare_di_fields_data(di_fields_data)
            print(f"  [OK] Loaded {len(di_fields)} DI fields from JSON")
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")
            print("  Skipping DI fields loading (not a Java repository or file not found)")
            return
        except Exception as e:
            print(f"  [ERROR] Error loading JSON: {e}")
            return
        
        print()
        
        # Load to database
        print_section("Loading DI fields to database...")
        with get_connection_with_schema(target_schema) as conn:
            load_di_fields_to_db(conn, target_schema, di_fields)
            
            # Verify
            count = count_table_records(conn, 'java_di_fields', schema=target_schema)
            print(f"  [OK] Total DI fields in database: {count}")
        
        print()
        print_header("Step 8 Complete!")
        print("DI fields loaded successfully.")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
