"""
Step 11: Load Python Decorators

This script loads Python test decorators from the analysis JSON output
into the PostgreSQL database.

What it does:
1. Reads decorators from test_analysis/outputs/{schema}/10_python_decorators.json
2. Connects to PostgreSQL database
3. Inserts decorator data into python_decorators table
4. Displays loading progress and statistics

Run this script:
    python deterministic/11_load_python_decorators.py
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

# Path to decorators JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
# Resolve path relative to this script's location, not current working directory
_script_dir = Path(__file__).parent.resolve()
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs"


def load_decorators_json() -> dict:
    """
    Load decorators data from JSON file.
    
    Checks both main directory and _python subdirectory.
    """
    # Try main directory first, then _python subdirectory
    decorators_file = TEST_ANALYSIS_DIR / "10_python_decorators.json"
    if not decorators_file.exists():
        decorators_file = TEST_ANALYSIS_DIR / "_python" / "10_python_decorators.json"
    
    if not decorators_file.exists():
        raise FileNotFoundError(
            f"Decorators file not found. Checked:\n"
            f"  - {TEST_ANALYSIS_DIR / '10_python_decorators.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_python' / '10_python_decorators.json'}\n"
            f"This file is only generated for Python repositories."
        )
    
    with open(decorators_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_decorators_data(decorators_data: dict) -> list:
    """Prepare decorators data for database insertion."""
    decorators = decorators_data.get('decorators', [])
    
    prepared = []
    for decorator in decorators:
        args = decorator.get('decorator_args', {})
        prepared.append({
            'test_id': decorator.get('test_id', ''),
            'decorator_name': decorator.get('decorator_name', ''),
            'decorator_args': args if isinstance(args, dict) else {},
        })
    
    return prepared


def load_decorators_to_db(conn, schema: str, decorators: list):
    """Load decorators into database."""
    if not decorators:
        print("  No decorators to load.")
        return
    
    with conn.cursor() as cursor:
        insert_query = f"""
            INSERT INTO {schema}.python_decorators 
            (test_id, decorator_name, decorator_args)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        values = [
            (
                decorator['test_id'],
                decorator['decorator_name'],
                json.dumps(decorator['decorator_args']),
            )
            for decorator in decorators
        ]
        
        execute_values(cursor, insert_query, values)
        conn.commit()
        
        print(f"  [OK] Loaded {len(decorators)} decorators")


def main():
    """Main function to load decorators."""
    print_header("Step 11: Loading Python Decorators")
    print()
    
    if not test_connection():
        print("ERROR: Cannot connect to database!")
        return
    
    print()
    
    schema_name = os.getenv('TEST_REPO_SCHEMA', None)
    target_schema = schema_name or DB_SCHEMA
    
    try:
        print_section("Loading decorators from JSON...")
        try:
            decorators_data = load_decorators_json()
            decorators = prepare_decorators_data(decorators_data)
            print(f"  [OK] Loaded {len(decorators)} decorators from JSON")
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")
            print("  Skipping decorators loading (not a Python repository or file not found)")
            return
        except Exception as e:
            print(f"  [ERROR] Error loading JSON: {e}")
            return
        
        print()
        
        print_section("Loading decorators to database...")
        with get_connection_with_schema(target_schema) as conn:
            load_decorators_to_db(conn, target_schema, decorators)
            
            count = count_table_records(conn, 'python_decorators', schema=target_schema)
            print(f"  [OK] Total decorators in database: {count}")
        
        print()
        print_header("Step 11 Complete!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
