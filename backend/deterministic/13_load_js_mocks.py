"""
Step 13: Load JavaScript Mocks

This script loads JavaScript mock usage from the analysis JSON output
into the PostgreSQL database.

What it does:
1. Reads mocks from test_analysis/outputs/{schema}/09_js_mocks.json
2. Connects to PostgreSQL database
3. Inserts mock data into js_mocks table
4. Displays loading progress and statistics

Run this script:
    python deterministic/13_load_js_mocks.py
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

# Path to mocks JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
# Resolve path relative to this script's location, not current working directory
_script_dir = Path(__file__).parent.resolve()
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs"


def load_mocks_json() -> dict:
    """
    Load mocks data from JSON file.
    
    Checks both main directory and _javascript/_js subdirectories.
    """
    # Try main directory first, then _javascript or _js subdirectory
    mocks_file = TEST_ANALYSIS_DIR / "09_js_mocks.json"
    if not mocks_file.exists():
        mocks_file = TEST_ANALYSIS_DIR / "_javascript" / "09_js_mocks.json"
    if not mocks_file.exists():
        mocks_file = TEST_ANALYSIS_DIR / "_js" / "09_js_mocks.json"
    
    if not mocks_file.exists():
        raise FileNotFoundError(
            f"Mocks file not found. Checked:\n"
            f"  - {TEST_ANALYSIS_DIR / '09_js_mocks.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_javascript' / '09_js_mocks.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_js' / '09_js_mocks.json'}\n"
            f"This file is only generated for JavaScript repositories."
        )
    
    with open(mocks_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_mocks_data(mocks_data: dict) -> list:
    """Prepare mocks data for database insertion."""
    mocks = mocks_data.get('mocks', [])
    
    prepared = []
    for mock in mocks:
        prepared.append({
            'test_id': mock.get('test_id', ''),
            'mock_type': mock.get('mock_type', ''),
            'mock_target': mock.get('mock_target'),
            'mock_implementation': mock.get('mock_implementation'),
        })
    
    return prepared


def load_mocks_to_db(conn, schema: str, mocks: list):
    """Load mocks into database."""
    if not mocks:
        print("  No mocks to load.")
        return
    
    with conn.cursor() as cursor:
        insert_query = f"""
            INSERT INTO {schema}.js_mocks 
            (test_id, mock_type, mock_target, mock_implementation)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        values = [
            (
                mock['test_id'],
                mock['mock_type'],
                mock.get('mock_target'),
                mock.get('mock_implementation'),
            )
            for mock in mocks
        ]
        
        execute_values(cursor, insert_query, values)
        conn.commit()
        
        print(f"  [OK] Loaded {len(mocks)} mocks")


def main():
    """Main function to load mocks."""
    print_header("Step 13: Loading JavaScript Mocks")
    print()
    
    if not test_connection():
        print("ERROR: Cannot connect to database!")
        return
    
    print()
    
    schema_name = os.getenv('TEST_REPO_SCHEMA', None)
    target_schema = schema_name or DB_SCHEMA
    
    try:
        print_section("Loading mocks from JSON...")
        try:
            mocks_data = load_mocks_json()
            mocks = prepare_mocks_data(mocks_data)
            print(f"  [OK] Loaded {len(mocks)} mocks from JSON")
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")
            print("  Skipping mocks loading (not a JavaScript repository or file not found)")
            return
        except Exception as e:
            print(f"  [ERROR] Error loading JSON: {e}")
            return
        
        print()
        
        print_section("Loading mocks to database...")
        with get_connection_with_schema(target_schema) as conn:
            load_mocks_to_db(conn, target_schema, mocks)
            
            count = count_table_records(conn, 'js_mocks', schema=target_schema)
            print(f"  [OK] Total mocks in database: {count}")
        
        print()
        print_header("Step 13 Complete!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
