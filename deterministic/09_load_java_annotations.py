"""
Step 9: Load Java Annotations

This script loads Java test annotations from the analysis JSON output
into the PostgreSQL database.

What it does:
1. Reads annotations from test_analysis/outputs/{schema}/11_java_annotations.json
2. Connects to PostgreSQL database
3. Inserts annotation data into java_annotations table
4. Displays loading progress and statistics

Run this script:
    python deterministic/09_load_java_annotations.py
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

# Path to annotations JSON file
# Use schema-specific output directory if TEST_REPO_SCHEMA is set
# Resolve path relative to this script's location, not current working directory
_script_dir = Path(__file__).parent.resolve()
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs" / schema_name
else:
    TEST_ANALYSIS_DIR = _script_dir.parent / "test_analysis" / "outputs"


def load_annotations_json() -> dict:
    """
    Load annotations data from JSON file.
    
    Checks both main directory and _java subdirectory.
    
    Returns:
        Dictionary with annotations data
    
    Raises:
        FileNotFoundError: If JSON file doesn't exist
    """
    # Try main directory first, then _java subdirectory
    annotations_file = TEST_ANALYSIS_DIR / "11_java_annotations.json"
    if not annotations_file.exists():
        annotations_file = TEST_ANALYSIS_DIR / "_java" / "11_java_annotations.json"
    
    if not annotations_file.exists():
        raise FileNotFoundError(
            f"Annotations file not found. Checked:\n"
            f"  - {TEST_ANALYSIS_DIR / '11_java_annotations.json'}\n"
            f"  - {TEST_ANALYSIS_DIR / '_java' / '11_java_annotations.json'}\n"
            f"This file is only generated for Java repositories."
        )
    
    with open(annotations_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('data', data)


def prepare_annotations_data(annotations_data: dict) -> list:
    """
    Prepare annotations data for database insertion.
    
    Args:
        annotations_data: Dictionary from JSON file
    
    Returns:
        List of annotation dictionaries ready for database insertion
    """
    annotations = annotations_data.get('annotations', [])
    
    prepared = []
    for ann in annotations:
        # Parse annotation attributes if it's a string
        attrs = ann.get('annotation_attributes', {})
        if isinstance(attrs, str):
            # Try to parse as JSON or keep as string
            try:
                attrs = json.loads(attrs) if attrs else {}
            except:
                attrs = {'value': attrs} if attrs else {}
        
        prepared.append({
            'test_id': ann.get('test_id', ''),
            'annotation_name': ann.get('annotation_name', ''),
            'annotation_attributes': attrs,
            'target_type': ann.get('target_type', 'method'),
        })
    
    return prepared


def load_annotations_to_db(conn, schema: str, annotations: list):
    """
    Load annotations into database.
    
    Args:
        conn: Database connection
        schema: Schema name
        annotations: List of annotation dictionaries
    """
    if not annotations:
        print("  No annotations to load.")
        return
    
    with conn.cursor() as cursor:
        # Insert annotations
        insert_query = f"""
            INSERT INTO {schema}.java_annotations 
            (test_id, annotation_name, annotation_attributes, target_type)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        values = [
            (
                ann['test_id'],
                ann['annotation_name'],
                json.dumps(ann['annotation_attributes']),
                ann['target_type'],
            )
            for ann in annotations
        ]
        
        execute_values(cursor, insert_query, values)
        conn.commit()
        
        print(f"  [OK] Loaded {len(annotations)} annotations")


def main():
    """Main function to load annotations."""
    print_header("Step 9: Loading Java Annotations")
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
        print_section("Loading annotations from JSON...")
        try:
            annotations_data = load_annotations_json()
            annotations = prepare_annotations_data(annotations_data)
            print(f"  [OK] Loaded {len(annotations)} annotations from JSON")
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")
            print("  Skipping annotations loading (not a Java repository or file not found)")
            return
        except Exception as e:
            print(f"  [ERROR] Error loading JSON: {e}")
            return
        
        print()
        
        # Load to database
        print_section("Loading annotations to database...")
        with get_connection_with_schema(target_schema) as conn:
            load_annotations_to_db(conn, target_schema, annotations)
            
            # Verify
            count = count_table_records(conn, 'java_annotations', schema=target_schema)
            print(f"  [OK] Total annotations in database: {count}")
        
        print()
        print_header("Step 9 Complete!")
        print("Annotations loaded successfully.")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
