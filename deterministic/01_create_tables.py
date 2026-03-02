"""
Step 1: Create Database Tables

This script creates all necessary database tables in the planon1 schema.
It handles table creation, indexes, and foreign key constraints.

What it does:
1. Connects to PostgreSQL database (planon)
2. Creates schema if it doesn't exist
3. Creates all tables in planon1 schema:
   - test_registry (all tests)
   - test_dependencies (test -> production code)
   - reverse_index (production code -> tests)
   - test_metadata (test descriptions, markers)
   - test_structure (directory structure)
4. Creates indexes for fast queries
5. Sets up foreign key relationships
6. Displays creation progress
7. Verifies tables created successfully

Run this script:
    python deterministic/01_create_tables.py
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_connection import get_connection, test_connection, get_db_config
from utils.output_formatter import print_header, print_section, print_item
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables to get schema
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Get schema from environment (same as db_connection.py)
SCHEMA = os.getenv('DB_SCHEMA', 'planon1')


def create_schema_if_not_exists(conn):
    """
    Create the schema if it doesn't exist.
    
    Args:
        conn: Database connection object
    
    This ensures the schema exists before creating tables.
    """
    with conn.cursor() as cursor:
        # Create schema if it doesn't exist
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        conn.commit()
        print(f"[OK] Schema '{SCHEMA}' ready")


def create_test_registry_table(conn):
    """
    Create the test_registry table.
    
    This table stores all test information:
    - test_id: Unique identifier for each test
    - file_path: Path to the test file
    - class_name: Test class name (if any)
    - method_name: Test method name
    - test_type: Type of test (unit, integration, e2e)
    - line_number: Line number in file (optional)
    """
    with conn.cursor() as cursor:
        # Drop table if exists (for re-running)
        cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.test_registry CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {SCHEMA}.test_registry (
                test_id VARCHAR(50) PRIMARY KEY,
                file_path TEXT NOT NULL,
                class_name VARCHAR(255),
                method_name VARCHAR(255) NOT NULL,
                test_type VARCHAR(50),
                line_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for fast lookups
        cursor.execute(f"""
            CREATE INDEX idx_test_registry_file 
            ON {SCHEMA}.test_registry(file_path)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_test_registry_class 
            ON {SCHEMA}.test_registry(class_name)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_test_registry_type 
            ON {SCHEMA}.test_registry(test_type)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.test_registry")
        print(f"  - Primary key: test_id")
        print(f"  - Indexes: file_path, class_name, test_type")


def create_test_dependencies_table(conn):
    """
    Create the test_dependencies table.
    
    This table stores test-to-production-code mappings:
    - test_id: Foreign key to test_registry
    - referenced_class: Production class/module referenced by test
    - import_type: Type of import (direct, from_import, etc.)
    """
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.test_dependencies CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {SCHEMA}.test_dependencies (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                referenced_class TEXT NOT NULL,
                import_type VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {SCHEMA}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX idx_dependencies_test 
            ON {SCHEMA}.test_dependencies(test_id)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_dependencies_class 
            ON {SCHEMA}.test_dependencies(referenced_class)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.test_dependencies")
        print(f"  - Foreign key: test_id -> test_registry")
        print(f"  - Indexes: test_id, referenced_class")


def create_reverse_index_table(conn):
    """
    Create the reverse_index table.
    
    This table stores production-code-to-tests mappings for fast lookup:
    - production_class: Production class/module name
    - test_id: Foreign key to test_registry
    - test_file_path: Path to test file (denormalized for performance)
    """
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.reverse_index CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {SCHEMA}.reverse_index (
                id SERIAL PRIMARY KEY,
                production_class TEXT NOT NULL,
                test_id VARCHAR(50) NOT NULL,
                test_file_path TEXT,
                reference_type VARCHAR(20) DEFAULT 'direct_import',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {SCHEMA}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for fast lookups
        cursor.execute(f"""
            CREATE INDEX idx_reverse_class 
            ON {SCHEMA}.reverse_index(production_class)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_reverse_test 
            ON {SCHEMA}.reverse_index(test_id)
        """)
        
        # Composite index for common query pattern
        cursor.execute(f"""
            CREATE INDEX idx_reverse_class_test 
            ON {SCHEMA}.reverse_index(production_class, test_id)
        """)
        
        # Index for reference_type to support filtering
        cursor.execute(f"""
            CREATE INDEX idx_reverse_reference_type 
            ON {SCHEMA}.reverse_index(reference_type)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.reverse_index")
        print(f"  - Foreign key: test_id -> test_registry")
        print(f"  - Columns: production_class, test_id, reference_type")
        print(f"  - Indexes: production_class, test_id, reference_type, (production_class, test_id)")


def create_test_metadata_table(conn):
    """
    Create the test_metadata table.
    
    This table stores test metadata:
    - test_id: Foreign key to test_registry (unique)
    - description: Test description/docstring
    - markers: Pytest markers (stored as JSONB)
    - is_async: Whether test is async
    - is_parameterized: Whether test is parameterized
    - pattern: Test naming pattern
    """
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.test_metadata CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {SCHEMA}.test_metadata (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) UNIQUE NOT NULL,
                description TEXT,
                markers JSONB,
                is_async BOOLEAN DEFAULT FALSE,
                is_parameterized BOOLEAN DEFAULT FALSE,
                pattern VARCHAR(50),
                line_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {SCHEMA}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX idx_metadata_test 
            ON {SCHEMA}.test_metadata(test_id)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_metadata_pattern 
            ON {SCHEMA}.test_metadata(pattern)
        """)
        
        # GIN index for JSONB markers (for fast JSON queries)
        cursor.execute(f"""
            CREATE INDEX idx_metadata_markers 
            ON {SCHEMA}.test_metadata USING GIN (markers)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.test_metadata")
        print(f"  - Foreign key: test_id -> test_registry (unique)")
        print(f"  - Indexes: test_id, pattern, markers (GIN)")


def create_test_structure_table(conn):
    """
    Create the test_structure table.
    
    This table stores test repository structure information:
    - directory_path: Path to directory
    - category: Test category (unit, integration, e2e)
    - file_count: Number of files in directory
    - total_lines: Total lines of code
    """
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.test_structure CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {SCHEMA}.test_structure (
                id SERIAL PRIMARY KEY,
                directory_path TEXT NOT NULL,
                category VARCHAR(50),
                file_count INTEGER,
                total_lines INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX idx_structure_category 
            ON {SCHEMA}.test_structure(category)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_structure_path 
            ON {SCHEMA}.test_structure(directory_path)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.test_structure")
        print(f"  - Indexes: category, directory_path")


def create_test_function_mapping_table(conn):
    """
    Create the test_function_mapping table.
    
    This table stores function-level mappings:
    - test_id: Foreign key to test_registry
    - module_name: Production module name (e.g., agent.langgraph_agent)
    - function_name: Function name (e.g., initialize)
    - call_type: Type of call (direct_call, method_call, patch_ref)
    - source: Source of mapping (method_call, patch_ref)
    """
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.test_function_mapping CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {SCHEMA}.test_function_mapping (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                module_name TEXT NOT NULL,
                function_name VARCHAR(255) NOT NULL,
                call_type VARCHAR(50),
                source VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {SCHEMA}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        
        # Create composite index for fast lookups (module_name, function_name)
        cursor.execute(f"""
            CREATE INDEX idx_func_mapping_module_func 
            ON {SCHEMA}.test_function_mapping(module_name, function_name)
        """)
        
        # Create index on test_id for reverse lookups
        cursor.execute(f"""
            CREATE INDEX idx_func_mapping_test 
            ON {SCHEMA}.test_function_mapping(test_id)
        """)
        
        # Create index on function_name alone for broader searches
        cursor.execute(f"""
            CREATE INDEX idx_func_mapping_function 
            ON {SCHEMA}.test_function_mapping(function_name)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {SCHEMA}.test_function_mapping")
        print(f"  - Foreign key: test_id -> test_registry")
        print(f"  - Indexes: (module_name, function_name), test_id, function_name")


def enable_pgvector_and_embedding_column(conn):
    """
    Enable pgvector extension and add embedding column to test_metadata.

    Uses ADD COLUMN IF NOT EXISTS — safe to run multiple times.
    nomic-embed-text produces 768-dimensional vectors.
    Does NOT drop or recreate test_metadata — only adds a column.
    """
    with conn.cursor() as cursor:
        # Enable pgvector (once per DB, safe to repeat)
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Add 768-dim embedding column to existing test_metadata
        cursor.execute(f"""
            ALTER TABLE {SCHEMA}.test_metadata
            ADD COLUMN IF NOT EXISTS embedding vector(768)
        """)

        # ivfflat index — right for datasets under 1 million rows
        # lists=10 is appropriate for ~100-500 tests
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_metadata_embedding
            ON {SCHEMA}.test_metadata
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 10)
        """)

        conn.commit()
        print(f"[OK] pgvector extension enabled")
        print(f"[OK] embedding column (vector(768)) added to {SCHEMA}.test_metadata")
        print(f"[OK] ivfflat cosine index created on test_metadata.embedding")


def verify_tables_created(conn):
    """
    Verify all tables were created successfully.
    
    Args:
        conn: Database connection object
    
    Returns:
        Dictionary with table verification results
    """
    with conn.cursor() as cursor:
        # Query to get all tables in schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s
            ORDER BY table_name
        """, (SCHEMA,))
        
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'test_registry',
            'test_dependencies',
            'reverse_index',
            'test_metadata',
            'test_structure',
            'test_function_mapping'
        ]
        
        result = {
            'tables_found': tables,
            'expected_tables': expected_tables,
            'all_present': all(table in tables for table in expected_tables),
            'missing_tables': [t for t in expected_tables if t not in tables]
        }
        
        # ADD at end before return:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name   = 'test_metadata'
                  AND column_name  = 'embedding'
            """, (SCHEMA,))
            result['embedding_column_exists'] = cursor.fetchone() is not None
        
        return result


def main():
    """Main function to create all database tables."""
    print_header("Step 1: Creating Database Tables")
    print()
    
    # Test connection first
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        print("Please check your .env file and database configuration.")
        return
    
    print()
    
    try:
        with get_connection() as conn:
            # Step 1: Create schema if needed
            print_section("Creating schema if needed...")
            create_schema_if_not_exists(conn)
            print()
            
            # Step 2: Create all tables
            print_section("Creating tables...")
            print()
            
            create_test_registry_table(conn)
            print()
            
            create_test_dependencies_table(conn)
            print()
            
            create_reverse_index_table(conn)
            print()
            
            create_test_metadata_table(conn)
            print()
            
            create_test_structure_table(conn)
            print()
            
            create_test_function_mapping_table(conn)
            print()

            # NEW — add after function mapping table
            # pgvector is optional — don't fail if extension not installed
            print_section("Enabling pgvector and adding embedding column...")
            try:
                enable_pgvector_and_embedding_column(conn)
                print()
            except Exception as e:
                print(f"[WARN] pgvector setup skipped: {e}")
                print("  Note: You can use ChromaDB backend instead (set VECTOR_BACKEND=chromadb)")
            print()
            
            # Step 3: Verify tables
            print_section("Verifying tables...")
            verification = verify_tables_created(conn)
            
            if verification['all_present']:
                print("[OK] All tables created successfully!")
                print()
                print("Tables created:")
                for table in verification['tables_found']:
                    print(f"  - {SCHEMA}.{table}")
            else:
                print("[ERROR] Some tables are missing!")
                print(f"Missing: {verification['missing_tables']}")
                return
            
            print()
            print_header("Step 1 Complete!")
            print(f"All tables created in schema: {SCHEMA}")
            print("Ready to load data in next steps.")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
