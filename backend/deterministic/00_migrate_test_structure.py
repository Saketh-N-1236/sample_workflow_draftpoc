"""
Migration script to add test_count column to existing test_structure tables.

This script adds the test_count column to all test_structure tables in all schemas.
Run this once to update existing databases.
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection
import psycopg2


def migrate_all_schemas():
    """Add test_count column to test_structure tables in all schemas."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all schemas that start with 'test_repo_'
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name LIKE 'test_repo_%'
            """)
            schemas = [row[0] for row in cursor.fetchall()]
            
            print(f"Found {len(schemas)} test repository schemas to migrate")
            
            for schema in schemas:
                try:
                    # Check if test_structure table exists
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = %s 
                            AND table_name = 'test_structure'
                        )
                    """, (schema,))
                    
                    table_exists = cursor.fetchone()[0]
                    
                    if not table_exists:
                        print(f"  Schema {schema}: test_structure table does not exist, skipping")
                        continue
                    
                    # Check if test_count column already exists
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns 
                            WHERE table_schema = %s 
                            AND table_name = 'test_structure'
                            AND column_name = 'test_count'
                        )
                    """, (schema,))
                    
                    column_exists = cursor.fetchone()[0]
                    
                    if column_exists:
                        print(f"  Schema {schema}: test_count column already exists, skipping")
                        continue
                    
                    # Add test_count column
                    cursor.execute(f"""
                        ALTER TABLE {schema}.test_structure 
                        ADD COLUMN test_count INTEGER DEFAULT 0
                    """)
                    conn.commit()
                    print(f"  Schema {schema}: Added test_count column successfully")
                    
                except Exception as e:
                    print(f"  Schema {schema}: Error - {e}")
                    conn.rollback()
            
            print("\nMigration complete!")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("Migrating test_structure tables to add test_count column")
    print("=" * 60)
    print()
    migrate_all_schemas()
