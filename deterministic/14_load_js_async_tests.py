"""
Step 14: Load JavaScript Async Tests

This script loads JavaScript async test information from the analysis JSON output
into the PostgreSQL database.

What it does:
1. Reads async tests from test_analysis/outputs/{schema}/10_js_async_tests.json
2. Connects to PostgreSQL database
3. Inserts async test data into js_async_tests table
4. Displays loading progress and statistics

Run this script:
    python deterministic/14_load_js_async_tests.py
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

# Path to async tests JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
# Resolve path relative to this script's location, not current working directory
_script_dir = Path(__file__).parent.resolve()
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs"


def load_async_tests_json() -> dict:
    """
    Load async tests data from JSON file.
    
    Checks both main directory and _javascript/_js subdirectories.
    """
    # Try main directory first, then _javascript or _js subdirectory
    async_tests_file = TEST_ANALYSIS_DIR / "10_js_async_tests.json"
    if not async_tests_file.exists():
        async_tests_file = TEST_ANALYSIS_DIR / "_javascript" / "10_js_async_tests.json"
    if not async_tests_file.exists():
        async_tests_file = TEST_ANALYSIS_DIR / "_js" / "10_js_async_tests.json"
    
    if not async_tests_file.exists():
        raise FileNotFoundError(
            f"Async tests file not found. Checked:\n"
            f"  - {TEST_ANALYSIS_DIR / '10_js_async_tests.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_javascript' / '10_js_async_tests.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_js' / '10_js_async_tests.json'}\n"
            f"This file is only generated for JavaScript repositories."
        )
    
    with open(async_tests_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_async_tests_data(async_tests_data: dict) -> list:
    """Prepare async tests data for database insertion."""
    async_tests = async_tests_data.get('async_tests', [])
    
    prepared = []
    for test in async_tests:
        prepared.append({
            'test_id': test.get('test_id', ''),
            'is_async': test.get('is_async', False),
            'async_pattern': test.get('async_pattern', 'async/await'),
        })
    
    return prepared


def load_async_tests_to_db(conn, schema: str, async_tests: list):
    """Load async tests into database."""
    if not async_tests:
        print("  No async tests to load.")
        return
    
    with conn.cursor() as cursor:
        insert_query = f"""
            INSERT INTO {schema}.js_async_tests 
            (test_id, is_async, async_pattern)
            VALUES %s
            ON CONFLICT (test_id) DO UPDATE SET
                is_async = EXCLUDED.is_async,
                async_pattern = EXCLUDED.async_pattern
        """
        
        values = [
            (
                test['test_id'],
                test['is_async'],
                test['async_pattern'],
            )
            for test in async_tests
        ]
        
        execute_values(cursor, insert_query, values)
        conn.commit()
        
        print(f"  [OK] Loaded {len(async_tests)} async tests")


def main():
    """Main function to load async tests."""
    print_header("Step 14: Loading JavaScript Async Tests")
    print()
    
    if not test_connection():
        print("ERROR: Cannot connect to database!")
        return
    
    print()
    
    schema_name = os.getenv('TEST_REPO_SCHEMA', None)
    target_schema = schema_name or DB_SCHEMA
    
    try:
        print_section("Loading async tests from JSON...")
        try:
            async_tests_data = load_async_tests_json()
            async_tests = prepare_async_tests_data(async_tests_data)
            print(f"  [OK] Loaded {len(async_tests)} async tests from JSON")
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")
            print("  Skipping async tests loading (not a JavaScript repository or file not found)")
            return
        except Exception as e:
            print(f"  [ERROR] Error loading JSON: {e}")
            return
        
        print()
        
        print_section("Loading async tests to database...")
        with get_connection_with_schema(target_schema) as conn:
            load_async_tests_to_db(conn, target_schema, async_tests)
            
            count = count_table_records(conn, 'js_async_tests', schema=target_schema)
            print(f"  [OK] Total async tests in database: {count}")
        
        print()
        print_header("Step 14 Complete!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
