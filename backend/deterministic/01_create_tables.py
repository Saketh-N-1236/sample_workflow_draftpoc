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

_det = Path(__file__).resolve().parent
_backend = _det.parent
sys.path.insert(0, str(_backend))
sys.path.insert(0, str(_det))

import logging

from db_connection import get_connection, test_connection, get_db_config, validate_schema_name

logger = logging.getLogger(__name__)
from test_analysis.utils.output_formatter import print_header, print_section, print_item
import os
from dotenv import load_dotenv
from pathlib import Path
from dataclasses import dataclass, field
from typing import List
import json

# Load environment variables to get schema
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Get schema from environment (same as db_connection.py)
SCHEMA = os.getenv('DB_SCHEMA', 'planon1')

# SchemaDefinition class for reading schema definition from environment
@dataclass
class SchemaDefinition:
    """Database schema definition."""
    core_tables: List[str] = field(default_factory=lambda: [
        'test_registry',
        'test_dependencies',
        'reverse_index',
        'test_metadata',
        'test_structure',
        'test_function_mapping',
    ])
    java_tables: List[str] = field(default_factory=list)
    python_tables: List[str] = field(default_factory=list)
    js_tables: List[str] = field(default_factory=list)

def get_schema_definition_from_env():
    """Get schema definition from environment variable."""
    schema_json = os.getenv('SCHEMA_DEFINITION')
    if not schema_json:
        return None
    try:
        schema_dict = json.loads(schema_json)
        return SchemaDefinition(
            core_tables=schema_dict.get('core_tables', []),
            java_tables=schema_dict.get('java_tables', []),
            python_tables=schema_dict.get('python_tables', []),
            js_tables=schema_dict.get('js_tables', [])
        )
    except Exception:
        return None


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


def create_test_registry_table(conn, schema: str = None):
    """
    Create the test_registry table.
    
    This table stores all test information:
    - test_id: Unique identifier for each test
    - file_path: Path to the test file
    - class_name: Test class name (if any)
    - method_name: Test method name
    - test_type: Type of test (unit, integration, e2e)
    - line_number: Line number in file (optional)
    
    Args:
        conn: Database connection
        schema: Schema name (defaults to SCHEMA constant)
    """
    target_schema = schema or SCHEMA
    with conn.cursor() as cursor:
        # Drop table if exists (for re-running)
        cursor.execute(f"DROP TABLE IF EXISTS {target_schema}.test_registry CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {target_schema}.test_registry (
                test_id VARCHAR(50) PRIMARY KEY,
                file_path TEXT NOT NULL,
                class_name VARCHAR(255),
                method_name VARCHAR(255) NOT NULL,
                test_type VARCHAR(50),
                line_number INTEGER,
                language VARCHAR(20) DEFAULT 'python',
                repository_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for fast lookups
        cursor.execute(f"""
            CREATE INDEX idx_test_registry_file 
            ON {target_schema}.test_registry(file_path)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_test_registry_class 
            ON {target_schema}.test_registry(class_name)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_test_registry_type 
            ON {target_schema}.test_registry(test_type)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_test_registry_language 
            ON {target_schema}.test_registry(language)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {target_schema}.test_registry")
        print(f"  - Primary key: test_id")
        print(f"  - Indexes: file_path, class_name, test_type, language")
        print(f"  - Columns: language (default: python), repository_path")


def create_test_dependencies_table(conn, schema: str = None):
    """
    Create the test_dependencies table.
    
    This table stores test-to-production-code mappings:
    - test_id: Foreign key to test_registry
    - referenced_class: Production class/module referenced by test
    - import_type: Type of import (direct, from_import, etc.)
    
    Args:
        conn: Database connection
        schema: Schema name (defaults to SCHEMA constant)
    """
    target_schema = schema or SCHEMA
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {target_schema}.test_dependencies CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {target_schema}.test_dependencies (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                referenced_class TEXT NOT NULL,
                import_type VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {target_schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX idx_dependencies_test 
            ON {target_schema}.test_dependencies(test_id)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_dependencies_class 
            ON {target_schema}.test_dependencies(referenced_class)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {target_schema}.test_dependencies")
        print(f"  - Foreign key: test_id -> test_registry")
        print(f"  - Indexes: test_id, referenced_class")


def create_reverse_index_table(conn, schema: str = None):
    """
    Create the reverse_index table.
    
    This table stores production-code-to-tests mappings for fast lookup:
    - production_class: Production class/module name
    - test_id: Foreign key to test_registry
    - test_file_path: Path to test file (denormalized for performance)
    
    Args:
        conn: Database connection
        schema: Schema name (defaults to SCHEMA constant)
    """
    target_schema = schema or SCHEMA
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {target_schema}.reverse_index CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {target_schema}.reverse_index (
                id SERIAL PRIMARY KEY,
                production_class TEXT NOT NULL,
                test_id VARCHAR(50) NOT NULL,
                test_file_path TEXT,
                reference_type VARCHAR(50) DEFAULT 'direct_import',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {target_schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for fast lookups
        cursor.execute(f"""
            CREATE INDEX idx_reverse_class 
            ON {target_schema}.reverse_index(production_class)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_reverse_test 
            ON {target_schema}.reverse_index(test_id)
        """)
        
        # Composite index for common query pattern
        cursor.execute(f"""
            CREATE INDEX idx_reverse_class_test 
            ON {target_schema}.reverse_index(production_class, test_id)
        """)
        
        # Index for reference_type to support filtering
        cursor.execute(f"""
            CREATE INDEX idx_reverse_reference_type 
            ON {target_schema}.reverse_index(reference_type)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {target_schema}.reverse_index")
        print(f"  - Foreign key: test_id -> test_registry")
        print(f"  - Columns: production_class, test_id, reference_type")
        print(f"  - Indexes: production_class, test_id, reference_type, (production_class, test_id)")


def create_test_metadata_table(conn, schema: str = None):
    """
    Create the test_metadata table.
    
    This table stores test metadata:
    - test_id: Foreign key to test_registry (unique)
    - description: Test description/docstring
    - markers: Pytest markers (stored as JSONB)
    - is_async: Whether test is async
    - is_parameterized: Whether test is parameterized
    - pattern: Test naming pattern
    
    Args:
        conn: Database connection
        schema: Schema name (defaults to SCHEMA constant)
    """
    target_schema = schema or SCHEMA
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {target_schema}.test_metadata CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {target_schema}.test_metadata (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) UNIQUE NOT NULL,
                description TEXT,
                markers JSONB,
                is_async BOOLEAN DEFAULT FALSE,
                is_parameterized BOOLEAN DEFAULT FALSE,
                pattern VARCHAR(50),
                line_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {target_schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX idx_metadata_test 
            ON {target_schema}.test_metadata(test_id)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_metadata_pattern 
            ON {target_schema}.test_metadata(pattern)
        """)
        
        # GIN index for JSONB markers (for fast JSON queries)
        cursor.execute(f"""
            CREATE INDEX idx_metadata_markers 
            ON {target_schema}.test_metadata USING GIN (markers)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {target_schema}.test_metadata")
        print(f"  - Foreign key: test_id -> test_registry (unique)")
        print(f"  - Indexes: test_id, pattern, markers (GIN)")


def create_test_structure_table(conn, schema: str = None):
    """
    Create the test_structure table.
    
    This table stores test repository structure information:
    - directory_path: Path to directory
    - category: Test category (unit, integration, e2e)
    - file_count: Number of files in directory
    - test_count: Number of tests in directory
    - total_lines: Total lines of code
    
    Args:
        conn: Database connection
        schema: Schema name (defaults to SCHEMA constant)
    """
    target_schema = schema or SCHEMA
    with conn.cursor() as cursor:
        # Check if table exists
        cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = %s 
                AND table_name = 'test_structure'
            )
        """, (target_schema,))
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            # Create table
            cursor.execute(f"""
                CREATE TABLE {target_schema}.test_structure (
                    id SERIAL PRIMARY KEY,
                    directory_path TEXT NOT NULL UNIQUE,
                    category VARCHAR(50),
                    file_count INTEGER,
                    test_count INTEGER DEFAULT 0,
                    total_lines INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # Table exists - check if test_count column exists and add if missing
            cursor.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = %s 
                    AND table_name = 'test_structure'
                    AND column_name = 'test_count'
                )
            """, (target_schema,))
            column_exists = cursor.fetchone()[0]
            
            if not column_exists:
                cursor.execute(f"""
                    ALTER TABLE {target_schema}.test_structure 
                    ADD COLUMN test_count INTEGER DEFAULT 0
                """)
                print(f"[OK] Added test_count column to existing table: {target_schema}.test_structure")
        
        # Drop and recreate indexes to ensure they exist
        try:
            cursor.execute(f"DROP INDEX IF EXISTS {target_schema}.idx_structure_category")
            cursor.execute(f"DROP INDEX IF EXISTS {target_schema}.idx_structure_path")
        except:
            pass
        
        # Create indexes
        cursor.execute(f"""
            CREATE INDEX idx_structure_category 
            ON {target_schema}.test_structure(category)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_structure_path 
            ON {target_schema}.test_structure(directory_path)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {target_schema}.test_structure")
        print(f"  - Indexes: category, directory_path")


def create_test_function_mapping_table(conn, schema: str = None):
    """
    Create the test_function_mapping table.
    
    This table stores function-level mappings:
    - test_id: Foreign key to test_registry
    - module_name: Production module name (e.g., agent.langgraph_agent)
    - function_name: Function name (e.g., initialize)
    - call_type: Type of call (direct_call, method_call, patch_ref)
    - source: Source of mapping (method_call, patch_ref)
    
    Args:
        conn: Database connection
        schema: Schema name (defaults to SCHEMA constant)
    """
    target_schema = schema or SCHEMA
    with conn.cursor() as cursor:
        # Drop table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {target_schema}.test_function_mapping CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {target_schema}.test_function_mapping (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                module_name TEXT NOT NULL,
                function_name VARCHAR(255) NOT NULL,
                call_type VARCHAR(50),
                source VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {target_schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        
        # Create composite index for fast lookups (module_name, function_name)
        cursor.execute(f"""
            CREATE INDEX idx_func_mapping_module_func 
            ON {target_schema}.test_function_mapping(module_name, function_name)
        """)
        
        # Create index on test_id for reverse lookups
        cursor.execute(f"""
            CREATE INDEX idx_func_mapping_test 
            ON {target_schema}.test_function_mapping(test_id)
        """)
        
        # Create index on function_name alone for broader searches
        cursor.execute(f"""
            CREATE INDEX idx_func_mapping_function 
            ON {target_schema}.test_function_mapping(function_name)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {target_schema}.test_function_mapping")
        print(f"  - Foreign key: test_id -> test_registry")
        print(f"  - Indexes: (module_name, function_name), test_id, function_name")


# pgvector support removed - using Pinecone only


def create_selection_audit_log_table(conn, schema: str = None):
    """
    Create the selection_audit_log table for tracking test selection runs.
    
    This table stores audit information about each test selection execution:
    - Repository ID
    - Timestamp
    - Changed files count
    - Selected tests count
    - Confidence score distribution
    - LLM usage flag
    - Execution time
    - Threshold exceeded flag
    
    Args:
        conn: Database connection
        schema: Schema name (defaults to SCHEMA constant)
    """
    target_schema = schema or SCHEMA
    with conn.cursor() as cursor:
        # Drop table if exists (for re-running)
        cursor.execute(f"DROP TABLE IF EXISTS {target_schema}.selection_audit_log CASCADE")
        
        # Create table
        cursor.execute(f"""
            CREATE TABLE {target_schema}.selection_audit_log (
                id SERIAL PRIMARY KEY,
                repository_id VARCHAR(255),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                changed_files_count INTEGER,
                selected_tests_count INTEGER,
                confidence_scores JSONB,
                llm_used BOOLEAN DEFAULT FALSE,
                execution_time_ms INTEGER,
                threshold_exceeded BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Create indexes for fast lookups
        cursor.execute(f"""
            CREATE INDEX idx_audit_log_repository 
            ON {target_schema}.selection_audit_log(repository_id)
        """)
        
        cursor.execute(f"""
            CREATE INDEX idx_audit_log_timestamp 
            ON {target_schema}.selection_audit_log(timestamp)
        """)
        
        conn.commit()
        print(f"[OK] Created table: {target_schema}.selection_audit_log")
        print(f"  - Primary key: id")
        print(f"  - Indexes: repository_id, timestamp")


def create_java_reflection_table(conn, schema: str):
    """Create java_reflection table for Java reflection usage tracking."""
    with conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.java_reflection CASCADE")
        cursor.execute(f"""
            CREATE TABLE {schema}.java_reflection (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                reflection_type VARCHAR(255),
                target_class TEXT,
                target_method TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        cursor.execute(f"CREATE INDEX idx_java_reflection_test ON {schema}.java_reflection(test_id)")
        cursor.execute(f"CREATE INDEX idx_java_reflection_target ON {schema}.java_reflection(target_class)")
        conn.commit()
        print(f"[OK] Created table: {schema}.java_reflection")


def create_java_di_fields_table(conn, schema: str):
    """Create java_di_fields table for Java dependency injection fields."""
    with conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.java_di_fields CASCADE")
        cursor.execute(f"""
            CREATE TABLE {schema}.java_di_fields (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                field_name VARCHAR(255),
                field_type TEXT,
                annotation VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        cursor.execute(f"CREATE INDEX idx_java_di_test ON {schema}.java_di_fields(test_id)")
        cursor.execute(f"CREATE INDEX idx_java_di_type ON {schema}.java_di_fields(field_type)")
        conn.commit()
        print(f"[OK] Created table: {schema}.java_di_fields")


def create_java_annotations_table(conn, schema: str):
    """Create java_annotations table for Java test annotations."""
    with conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.java_annotations CASCADE")
        cursor.execute(f"""
            CREATE TABLE {schema}.java_annotations (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                annotation_name VARCHAR(255),
                annotation_args TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {schema}.test_registry(test_id) ON DELETE CASCADE,
                UNIQUE(test_id, annotation_name)
            )
        """)
        cursor.execute(f"CREATE INDEX idx_java_ann_test ON {schema}.java_annotations(test_id)")
        cursor.execute(f"CREATE INDEX idx_java_ann_name ON {schema}.java_annotations(annotation_name)")
        conn.commit()
        print(f"[OK] Created table: {schema}.java_annotations")


def create_python_fixtures_table(conn, schema: str):
    """Create python_fixtures table for pytest fixtures."""
    with conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.python_fixtures CASCADE")
        cursor.execute(f"""
            CREATE TABLE {schema}.python_fixtures (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                fixture_name VARCHAR(255),
                fixture_scope VARCHAR(50),
                fixture_params TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        cursor.execute(f"CREATE INDEX idx_python_fixtures_test ON {schema}.python_fixtures(test_id)")
        cursor.execute(f"CREATE INDEX idx_python_fixtures_name ON {schema}.python_fixtures(fixture_name)")
        conn.commit()
        print(f"[OK] Created table: {schema}.python_fixtures")


def create_python_decorators_table(conn, schema: str):
    """Create python_decorators table for Python test decorators."""
    with conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.python_decorators CASCADE")
        cursor.execute(f"""
            CREATE TABLE {schema}.python_decorators (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                decorator_name VARCHAR(255),
                decorator_args JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        cursor.execute(f"CREATE INDEX idx_python_decorators_test ON {schema}.python_decorators(test_id)")
        cursor.execute(f"CREATE INDEX idx_python_decorators_name ON {schema}.python_decorators(decorator_name)")
        conn.commit()
        print(f"[OK] Created table: {schema}.python_decorators")


def create_python_async_tests_table(conn, schema: str):
    """Create python_async_tests table for async test detection."""
    with conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.python_async_tests CASCADE")
        cursor.execute(f"""
            CREATE TABLE {schema}.python_async_tests (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL UNIQUE,
                is_async BOOLEAN DEFAULT FALSE,
                async_pattern VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        cursor.execute(f"CREATE INDEX idx_python_async_test ON {schema}.python_async_tests(test_id)")
        cursor.execute(f"CREATE INDEX idx_python_async_flag ON {schema}.python_async_tests(is_async)")
        conn.commit()
        print(f"[OK] Created table: {schema}.python_async_tests")


def create_js_mocks_table(conn, schema: str):
    """Create js_mocks table for JavaScript mock usage."""
    with conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.js_mocks CASCADE")
        cursor.execute(f"""
            CREATE TABLE {schema}.js_mocks (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL,
                mock_type VARCHAR(50),
                mock_target TEXT,
                mock_implementation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        cursor.execute(f"CREATE INDEX idx_js_mocks_test ON {schema}.js_mocks(test_id)")
        cursor.execute(f"CREATE INDEX idx_js_mocks_type ON {schema}.js_mocks(mock_type)")
        conn.commit()
        print(f"[OK] Created table: {schema}.js_mocks")


def create_js_async_tests_table(conn, schema: str):
    """Create js_async_tests table for JavaScript async test detection."""
    with conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.js_async_tests CASCADE")
        cursor.execute(f"""
            CREATE TABLE {schema}.js_async_tests (
                id SERIAL PRIMARY KEY,
                test_id VARCHAR(50) NOT NULL UNIQUE,
                is_async BOOLEAN DEFAULT FALSE,
                async_pattern VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES {schema}.test_registry(test_id) ON DELETE CASCADE
            )
        """)
        cursor.execute(f"CREATE INDEX idx_js_async_test ON {schema}.js_async_tests(test_id)")
        cursor.execute(f"CREATE INDEX idx_js_async_flag ON {schema}.js_async_tests(is_async)")
        conn.commit()
        print(f"[OK] Created table: {schema}.js_async_tests")


def create_all_tables_in_schema(conn, schema: str, schema_definition=None):
    """
    Create all test analysis tables in a specific schema.
    
    Args:
        conn: Database connection
        schema: Schema name where tables should be created
        schema_definition: Optional SchemaDefinition object with language-specific tables
    """
    safe_schema = validate_schema_name(schema)
    print(f"Creating all tables in schema: {safe_schema}")
    logger.info("[DDL] Preparing schema %s (CREATE SCHEMA + lock_timeout)", safe_schema)

    # 1) Ensure the namespace exists — without this, CREATE TABLE schema.table fails with
    #    "schema does not exist" if bind/test-repo creation was skipped or failed.
    # 2) lock_timeout avoids hanging forever when another session holds a lock on these
    #    tables (pgAdmin, stuck API worker, previous crashed analysis).
    with conn.cursor() as cursor:
        cursor.execute("SET lock_timeout = '120s'")
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {safe_schema}")
    conn.commit()
    logger.info("[DDL] Schema ensured; dropping/recreating core tables...")

    # Always create core tables
    create_test_registry_table(conn, schema=safe_schema)
    create_test_dependencies_table(conn, schema=safe_schema)
    create_reverse_index_table(conn, schema=safe_schema)
    create_test_metadata_table(conn, schema=safe_schema)
    create_test_structure_table(conn, schema=safe_schema)
    create_test_function_mapping_table(conn, schema=safe_schema)
    logger.info("[DDL] Core tables done; language-specific tables next (if any).")

    # Create language-specific tables if schema definition is provided
    if schema_definition:
        # Java tables
        if schema_definition.java_tables:
            print(f"Creating {len(schema_definition.java_tables)} Java-specific tables...")
            if 'java_reflection' in schema_definition.java_tables:
                create_java_reflection_table(conn, safe_schema)
            if 'java_di_fields' in schema_definition.java_tables:
                create_java_di_fields_table(conn, safe_schema)
            if 'java_annotations' in schema_definition.java_tables:
                create_java_annotations_table(conn, safe_schema)
        
        # Python tables
        if schema_definition.python_tables:
            print(f"Creating {len(schema_definition.python_tables)} Python-specific tables...")
            if 'python_fixtures' in schema_definition.python_tables:
                create_python_fixtures_table(conn, safe_schema)
            if 'python_decorators' in schema_definition.python_tables:
                create_python_decorators_table(conn, safe_schema)
            if 'python_async_tests' in schema_definition.python_tables:
                create_python_async_tests_table(conn, safe_schema)
        
        # JavaScript tables
        if schema_definition.js_tables:
            print(f"Creating {len(schema_definition.js_tables)} JavaScript-specific tables...")
            if 'js_mocks' in schema_definition.js_tables:
                create_js_mocks_table(conn, safe_schema)
            if 'js_async_tests' in schema_definition.js_tables:
                create_js_async_tests_table(conn, safe_schema)
    
    # Note: Vector embeddings are stored in Pinecone, not PostgreSQL
    # No pgvector extension or embedding column needed
    
    total_tables = 6  # Core tables
    if schema_definition:
        total_tables += len(schema_definition.java_tables) + len(schema_definition.python_tables) + len(schema_definition.js_tables)
    
    print(f"[OK] All {total_tables} tables created in schema: {safe_schema}")
    logger.info("[DDL] Finished creating %s tables in schema %s", total_tables, safe_schema)


def verify_tables_created(conn, schema: str = None):
    """
    Verify all tables were created successfully.
    
    Args:
        conn: Database connection object
        schema: Schema name to verify (defaults to SCHEMA constant)
    
    Returns:
        Dictionary with table verification results
    """
    target_schema = schema or SCHEMA
    with conn.cursor() as cursor:
        # Query to get all tables in schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s
            ORDER BY table_name
        """, (target_schema,))
        
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'test_registry',
            'test_dependencies',
            'reverse_index',
            'test_metadata',
            'test_structure',
            'test_function_mapping',
            'selection_audit_log'
        ]
        
        result = {
            'tables_found': tables,
            'expected_tables': expected_tables,
            'all_present': all(table in tables for table in expected_tables),
            'missing_tables': [t for t in expected_tables if t not in tables]
        }
        
        # Check for embedding column
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name   = 'test_metadata'
                  AND column_name  = 'embedding'
            """, (target_schema,))
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

            # Note: Vector embeddings are stored in Pinecone, not PostgreSQL
            # No pgvector extension or embedding column needed
            print()
            
            # Create selection audit log table
            create_selection_audit_log_table(conn)
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
    # Check if called with schema argument (from API route or analysis service)
    import sys
    if len(sys.argv) > 1:
        schema_arg = sys.argv[1]
        # Get schema definition from environment
        schema_def = get_schema_definition_from_env()
        
        # Debug: Print schema definition if found
        if schema_def:
            print(f"[DEBUG] Schema definition found: {len(schema_def.java_tables)} Java tables, {len(schema_def.python_tables)} Python tables, {len(schema_def.js_tables)} JS tables")
        else:
            print(f"[DEBUG] No schema definition found in environment (SCHEMA_DEFINITION={os.getenv('SCHEMA_DEFINITION', 'NOT SET')[:100] if os.getenv('SCHEMA_DEFINITION') else 'NOT SET'})")
        
        with get_connection() as conn:
            # Create schema if it doesn't exist
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_arg}")
                conn.commit()
            
            # Create all tables with schema definition
            create_all_tables_in_schema(conn, schema_arg, schema_def)
    else:
        main()
