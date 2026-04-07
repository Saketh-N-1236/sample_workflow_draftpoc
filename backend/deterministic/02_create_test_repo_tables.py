"""
Step 2: Create Test Repository Management Tables

This script creates tables for managing multiple test repositories:
- test_repositories: Main metadata for test repositories
- repository_test_bindings: Many-to-many binding between repos and test repos
- test_repo_schemas: Schema name mapping for each test repository

Run this script:
    python deterministic/02_create_test_repo_tables.py
"""

import sys
from pathlib import Path

_det = Path(__file__).resolve().parent
_backend = _det.parent
sys.path.insert(0, str(_backend))
sys.path.insert(0, str(_det))

from db_connection import get_connection, test_connection, get_db_config
from test_analysis.utils.output_formatter import print_header, print_section, print_item
import os
from dotenv import load_dotenv

# Load environment variables to get schema
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Get schema from environment (use planon1 for management tables)
SCHEMA = os.getenv('DB_SCHEMA', 'planon1')


def create_test_repositories_table(conn):
    """Create the test_repositories table."""
    with conn.cursor() as cursor:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.test_repositories (
                id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                zip_filename VARCHAR(255),
                extracted_path TEXT NOT NULL,
                hash VARCHAR(64) UNIQUE NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_analyzed_at TIMESTAMP,
                status VARCHAR(50) DEFAULT 'pending',
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_test_repositories_hash 
            ON {SCHEMA}.test_repositories(hash)
        """)
        
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_test_repositories_status 
            ON {SCHEMA}.test_repositories(status)
        """)
        
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_test_repositories_name 
            ON {SCHEMA}.test_repositories(name)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.test_repositories")
        print(f"  - Primary key: id (hash)")
        print(f"  - Indexes: hash, status, name")


def create_repository_test_bindings_table(conn):
    """Create the repository_test_bindings table (many-to-many)."""
    with conn.cursor() as cursor:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.repository_test_bindings (
                repository_id VARCHAR(50) NOT NULL,
                test_repository_id VARCHAR(64) NOT NULL,
                is_primary BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (repository_id, test_repository_id),
                FOREIGN KEY (repository_id) REFERENCES {SCHEMA}.repositories(id) ON DELETE CASCADE,
                FOREIGN KEY (test_repository_id) REFERENCES {SCHEMA}.test_repositories(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_bindings_repo_id 
            ON {SCHEMA}.repository_test_bindings(repository_id)
        """)
        
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_bindings_test_repo_id 
            ON {SCHEMA}.repository_test_bindings(test_repository_id)
        """)
        
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_bindings_primary 
            ON {SCHEMA}.repository_test_bindings(repository_id, is_primary) 
            WHERE is_primary = TRUE
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.repository_test_bindings")
        print(f"  - Primary key: (repository_id, test_repository_id)")
        print(f"  - Foreign keys: repositories, test_repositories")


def create_test_repo_schemas_table(conn):
    """Create the test_repo_schemas table."""
    with conn.cursor() as cursor:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.test_repo_schemas (
                test_repository_id VARCHAR(64) PRIMARY KEY,
                schema_name VARCHAR(63) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_repository_id) REFERENCES {SCHEMA}.test_repositories(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_test_repo_schemas_schema_name 
            ON {SCHEMA}.test_repo_schemas(schema_name)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.test_repo_schemas")
        print(f"  - Primary key: test_repository_id")
        print(f"  - Unique: schema_name")


def main():
    """Main function to create test repository management tables."""
    print_header("Create Test Repository Management Tables")
    print()
    
    # Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        print("Please ensure the database is set up and .env is configured.")
        return False
    print()
    
    try:
        with get_connection() as conn:
            # Create schema if it doesn't exist
            create_schema_if_not_exists(conn)
            print()
            
            # Create tables
            print_section("Creating test repository management tables...")
            create_test_repositories_table(conn)
            create_repository_test_bindings_table(conn)
            create_test_repo_schemas_table(conn)
            print()
            
            print_section("All tables created successfully!")
            print_item("Tables created", "3")
            print_item("Schema", SCHEMA)
            print()
            
            return True
            
    except Exception as e:
        print()
        print(f"ERROR: Failed to create tables: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_schema_if_not_exists(conn):
    """Create the schema if it doesn't exist."""
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        conn.commit()
        print(f"[OK] Schema '{SCHEMA}' ready")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
