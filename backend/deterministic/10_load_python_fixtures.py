"""
Step 10: Load Python Fixtures

This script loads pytest fixtures from the analysis JSON output
into the PostgreSQL database.

What it does:
1. Reads fixtures from test_analysis/outputs/{schema}/09_python_fixtures.json
2. Connects to PostgreSQL database
3. Inserts fixture data into python_fixtures table
4. Displays loading progress and statistics

Run this script:
    python deterministic/10_load_python_fixtures.py
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

# Path to fixtures JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
# Resolve path relative to this script's location, not current working directory
_script_dir = Path(__file__).parent.resolve()
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs"


def load_fixtures_json() -> dict:
    """
    Load fixtures data from JSON file.
    
    Checks both main directory and _python subdirectory.
    """
    # Try main directory first, then _python subdirectory
    fixtures_file = TEST_ANALYSIS_DIR / "09_python_fixtures.json"
    if not fixtures_file.exists():
        fixtures_file = TEST_ANALYSIS_DIR / "_python" / "09_python_fixtures.json"
    
    if not fixtures_file.exists():
        raise FileNotFoundError(
            f"Fixtures file not found. Checked:\n"
            f"  - {TEST_ANALYSIS_DIR / '09_python_fixtures.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_python' / '09_python_fixtures.json'}\n"
            f"This file is only generated for Python repositories."
        )
    
    with open(fixtures_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_fixtures_data(fixtures_data: dict) -> list:
    """Prepare fixtures data for database insertion."""
    fixtures = fixtures_data.get('fixtures', [])
    
    prepared = []
    for fixture in fixtures:
        prepared.append({
            'test_id': fixture.get('test_id', ''),
            'fixture_name': fixture.get('fixture_name', ''),
            'fixture_scope': fixture.get('fixture_scope', 'function'),
            'fixture_type': fixture.get('fixture_type', 'sync'),
        })
    
    return prepared


def load_fixtures_to_db(conn, schema: str, fixtures: list):
    """Load fixtures into database."""
    if not fixtures:
        print("  No fixtures to load.")
        return
    
    with conn.cursor() as cursor:
        insert_query = f"""
            INSERT INTO {schema}.python_fixtures 
            (test_id, fixture_name, fixture_scope, fixture_type)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        values = [
            (
                fixture['test_id'],
                fixture['fixture_name'],
                fixture['fixture_scope'],
                fixture['fixture_type'],
            )
            for fixture in fixtures
        ]
        
        execute_values(cursor, insert_query, values)
        conn.commit()
        
        print(f"  [OK] Loaded {len(fixtures)} fixtures")


def main():
    """Main function to load fixtures."""
    print_header("Step 10: Loading Python Fixtures")
    print()
    
    if not test_connection():
        print("ERROR: Cannot connect to database!")
        return
    
    print()
    
    schema_name = os.getenv('TEST_REPO_SCHEMA', None)
    target_schema = schema_name or DB_SCHEMA
    
    try:
        print_section("Loading fixtures from JSON...")
        try:
            fixtures_data = load_fixtures_json()
            fixtures = prepare_fixtures_data(fixtures_data)
            print(f"  [OK] Loaded {len(fixtures)} fixtures from JSON")
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")
            print("  Skipping fixtures loading (not a Python repository or file not found)")
            return
        except Exception as e:
            print(f"  [ERROR] Error loading JSON: {e}")
            return
        
        print()
        
        print_section("Loading fixtures to database...")
        with get_connection_with_schema(target_schema) as conn:
            load_fixtures_to_db(conn, target_schema, fixtures)
            
            count = count_table_records(conn, 'python_fixtures', schema=target_schema)
            print(f"  [OK] Total fixtures in database: {count}")
        
        print()
        print_header("Step 10 Complete!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
