"""
Database Connection Module

This module provides database connection utilities for PostgreSQL.
It handles connection management, environment variable loading, and provides
a context manager for safe database operations.

Key Features:
- Loads database credentials from .env file
- Creates database connections with proper error handling
- Sets schema search path to planon1
- Provides connection context manager for automatic cleanup
- Includes test connection function

Usage:
    from db_connection import get_connection, test_connection
    
    # Test connection
    if test_connection():
        print("Database connection successful!")
    
    # Use connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM planon1.test_registry")
        results = cursor.fetchall()
"""

import os
import psycopg2
from psycopg2 import pool
from psycopg2 import OperationalError
from contextlib import contextmanager
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
# Search: deterministic/ -> backend/ -> project_root/ (sample_workflow/)
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


# Database configuration from environment variables
# Schema is stored separately as it's not a connection parameter
DB_SCHEMA = os.getenv('DB_SCHEMA', 'planon1')

# Connection parameters (schema is NOT included - it's set via SQL after connection)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'planon'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}


# Connection pool (created on first use)
_connection_pool = None


def get_db_config():
    """
    Get database configuration dictionary.
    
    Returns:
        Dictionary with database connection parameters
    
    Example:
        >>> config = get_db_config()
        >>> print(config['database'])
        planon
    """
    return DB_CONFIG.copy()


def create_connection_pool(minconn=1, maxconn=5):
    """
    Create a connection pool for database connections.
    
    Args:
        minconn: Minimum number of connections in pool (default: 1)
        maxconn: Maximum number of connections in pool (default: 5)
    
    Returns:
        Connection pool object
    
    Note:
        Connection pooling allows reuse of database connections,
        which is more efficient than creating new connections each time.
    """
    global _connection_pool
    
    if _connection_pool is None:
        try:
            _connection_pool = pool.SimpleConnectionPool(
                minconn,
                maxconn,
                **DB_CONFIG
            )
            print(f"[OK] Connection pool created")
        except Exception as e:
            print(f"[ERROR] Failed to create connection pool: {e}")
            raise
    
    return _connection_pool


@contextmanager
def get_connection():
    """
    Get a database connection from the pool with automatic cleanup.
    
    This is a context manager that:
    1. Gets a connection from the pool
    2. Sets the schema search path to planon1
    3. Yields the connection for use
    4. Returns the connection to the pool when done
    
    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM planon1.test_registry")
            results = cursor.fetchall()
    
    Yields:
        psycopg2.connection: Database connection object
    
    Raises:
        Exception: If connection cannot be established
    """
    pool = create_connection_pool()
    conn = None
    
    try:
        # Get connection from pool
        conn = pool.getconn()
        
        if conn is None:
            raise Exception("Failed to get connection from pool")
        
        # Set schema search path to planon1
        # This allows us to use table names without schema prefix
        with conn.cursor() as cursor:
            cursor.execute(f"SET search_path TO {DB_SCHEMA}, public")
            conn.commit()
        
        # Yield connection for use
        yield conn
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] Database connection error: {e}")
        raise
    finally:
        # Return connection to pool
        if conn:
            pool.putconn(conn)


def create_schema_if_not_exists(schema_name: str):
    """
    Create a database schema if it doesn't exist.
    
    Args:
        schema_name: Name of the schema to create
        
    Returns:
        True if schema was created or already exists, False on error
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Validate schema name (PostgreSQL limit: 63 chars, alphanumeric + underscore)
                if len(schema_name) > 63:
                    raise ValueError(f"Schema name too long: {schema_name} (max 63 characters)")
                if not schema_name.replace('_', '').isalnum():
                    raise ValueError(f"Invalid schema name: {schema_name} (must be alphanumeric + underscore)")
                
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
                conn.commit()
                return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create schema {schema_name}: {e}")
        return False


def drop_schema_if_exists(schema_name: str, cascade: bool = True):
    """
    Drop a database schema if it exists.
    
    Args:
        schema_name: Name of the schema to drop
        cascade: If True, drop all objects in schema (CASCADE)
        
    Returns:
        True if schema was dropped or didn't exist, False on error
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cascade_clause = "CASCADE" if cascade else "RESTRICT"
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name} {cascade_clause}")
                conn.commit()
                return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to drop schema {schema_name}: {e}")
        return False


@contextmanager
def get_connection_with_schema(schema_name: str):
    """
    Get a database connection with a specific schema search path.
    
    This function:
    1. Creates a connection pool if it doesn't exist
    2. Sets the schema search path to the specified schema
    3. Returns a connection from the pool
    
    Args:
        schema_name: Name of the schema to use
        
    Yields:
        psycopg2.connection: Database connection object with schema set
    """
    pool = create_connection_pool()
    conn = None
    
    try:
        # Get connection from pool
        conn = pool.getconn()
        
        if conn is None:
            raise Exception("Failed to get connection from pool")
        
        # Set schema search path
        with conn.cursor() as cursor:
            cursor.execute(f"SET search_path TO {schema_name}, public")
            conn.commit()
        
        # Yield connection for use
        yield conn
        
    except Exception as e:
        if conn:
            conn.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        # Return connection to pool
        if conn:
            pool.putconn(conn)


def test_connection(schema_to_test=None):
    """
    Test database connection and schema access.
    
    This function:
    1. Attempts to connect to the database
    2. Verifies the schema exists
    3. Returns True if successful, False otherwise
    
    Args:
        schema_to_test: Optional schema name to test (defaults to DB_SCHEMA or TEST_REPO_SCHEMA)
    
    Returns:
        bool: True if connection successful, False otherwise
    
    Example:
        >>> if test_connection():
        ...     print("Database is ready!")
        ... else:
        ...     print("Database connection failed!")
    """
    try:
        # Use provided schema, or TEST_REPO_SCHEMA env var, or default DB_SCHEMA
        test_schema = schema_to_test or os.getenv('TEST_REPO_SCHEMA') or DB_SCHEMA
        
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Test basic query
                cursor.execute("SELECT current_database(), current_schema()")
                result = cursor.fetchone()
                db_name, schema_name = result
                
                # Verify schema exists
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, (test_schema,))
                
                schema_exists = cursor.fetchone() is not None
                
                if schema_exists:
                    print(f"[OK] Connected to database: {db_name}")
                    print(f"[OK] Using schema: {test_schema}")
                    print(f"[OK] Schema exists and is accessible")
                    return True
                else:
                    print(f"[ERROR] Schema '{test_schema}' does not exist!")
                    print(f"  Please create the schema in pgAdmin or using SQL:")
                    print(f"  CREATE SCHEMA IF NOT EXISTS {test_schema};")
                    return False
                    
    except OperationalError as e:
        print(f"[ERROR] Connection failed: {e}")
        print(f"  Please check:")
        print(f"  - Database '{DB_CONFIG['database']}' exists")
        print(f"  - Host: {DB_CONFIG['host']}, Port: {DB_CONFIG['port']}")
        print(f"  - Username and password are correct")
        print(f"  - .env file is configured properly")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False


def close_connection_pool():
    """
    Close all connections in the pool.
    
    Call this when you're done with all database operations
    to properly clean up resources.
    """
    global _connection_pool
    
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        print("[OK] Connection pool closed")


if __name__ == "__main__":
    """
    Test the database connection when run directly.
    
    Run this file to test your database connection:
        python deterministic/db_connection.py
    """
    print("=" * 50)
    print("  Database Connection Test")
    print("=" * 50)
    print(f"  Database : {DB_CONFIG['database']}")
    print(f"  Schema   : {DB_SCHEMA}")
    print(f"  Host     : {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"  User     : {DB_CONFIG['user']}")
    print("=" * 50)
    print()
    
    if test_connection():
        print("[OK] Connection test passed")
    else:
        print("[FAIL] Connection test failed")
        print("  Check your .env file configuration.")
