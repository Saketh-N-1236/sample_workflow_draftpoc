"""
Test Repository Service

This service handles:
- Uploading and extracting zip files
- Generating hash (SHA-256)
- Creating/dropping schemas
- Managing bindings between repositories and test repositories
"""

import sys
import hashlib
import zipfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add deterministic directory to path for db_connection
deterministic_path = project_root / "deterministic"
sys.path.insert(0, str(deterministic_path))

from deterministic.db_connection import (
    get_connection, 
    DB_SCHEMA, 
    create_schema_if_not_exists, 
    drop_schema_if_exists,
    get_connection_with_schema
)

logger = logging.getLogger(__name__)

# Base directory for extracted test repositories
TEST_REPO_DATA_DIR = project_root / "project_structure" / "test_repo_data"


def create_test_repo_tables():
    """
    Create the test repository management tables if they don't exist.
    
    This should be called on startup to ensure tables exist.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Create test_repositories table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.test_repositories (
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
                
                # Create indexes for test_repositories
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_test_repositories_hash 
                    ON {DB_SCHEMA}.test_repositories(hash)
                """)
                
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_test_repositories_status 
                    ON {DB_SCHEMA}.test_repositories(status)
                """)
                
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_test_repositories_name 
                    ON {DB_SCHEMA}.test_repositories(name)
                """)
                
                # Create repository_test_bindings table
                # Note: Foreign key to repositories table - ensure it exists first
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.repository_test_bindings (
                        repository_id VARCHAR(50) NOT NULL,
                        test_repository_id VARCHAR(64) NOT NULL,
                        is_primary BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (repository_id, test_repository_id)
                    )
                """)
                
                # Add foreign keys separately (check if tables exist first)
                # Foreign key to repositories table
                try:
                    cursor.execute(f"""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = %s AND table_name = 'repositories'
                        )
                    """, (DB_SCHEMA,))
                    repos_table_exists = cursor.fetchone()[0]
                    
                    if repos_table_exists:
                        cursor.execute(f"""
                            DO $$
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM pg_constraint c
                                    JOIN pg_namespace n ON n.oid = c.connamespace
                                    WHERE n.nspname = %s 
                                    AND c.conname = 'repository_test_bindings_repository_id_fkey'
                                ) THEN
                                    ALTER TABLE {DB_SCHEMA}.repository_test_bindings
                                    ADD CONSTRAINT repository_test_bindings_repository_id_fkey
                                    FOREIGN KEY (repository_id) 
                                    REFERENCES {DB_SCHEMA}.repositories(id) ON DELETE CASCADE;
                                END IF;
                            END $$;
                        """, (DB_SCHEMA,))
                        conn.commit()
                except Exception as e:
                    logger.warning(f"Could not add foreign key to repositories: {e}")
                    conn.rollback()
                
                # Foreign key to test_repositories table (should exist since we just created it)
                try:
                    cursor.execute(f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_constraint c
                                JOIN pg_namespace n ON n.oid = c.connamespace
                                WHERE n.nspname = %s 
                                AND c.conname = 'repository_test_bindings_test_repository_id_fkey'
                            ) THEN
                                ALTER TABLE {DB_SCHEMA}.repository_test_bindings
                                ADD CONSTRAINT repository_test_bindings_test_repository_id_fkey
                                FOREIGN KEY (test_repository_id) 
                                REFERENCES {DB_SCHEMA}.test_repositories(id) ON DELETE CASCADE;
                            END IF;
                        END $$;
                    """, (DB_SCHEMA,))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Could not add foreign key to test_repositories: {e}")
                    conn.rollback()
                
                # Create indexes for repository_test_bindings
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_bindings_repo_id 
                    ON {DB_SCHEMA}.repository_test_bindings(repository_id)
                """)
                
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_bindings_test_repo_id 
                    ON {DB_SCHEMA}.repository_test_bindings(test_repository_id)
                """)
                
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_bindings_primary 
                    ON {DB_SCHEMA}.repository_test_bindings(repository_id, is_primary) 
                    WHERE is_primary = TRUE
                """)
                
                # Create test_repo_schemas table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.test_repo_schemas (
                        test_repository_id VARCHAR(64) PRIMARY KEY,
                        schema_name VARCHAR(63) NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Add foreign key separately (test_repositories should exist since we just created it)
                try:
                    cursor.execute(f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_constraint c
                                JOIN pg_namespace n ON n.oid = c.connamespace
                                WHERE n.nspname = %s 
                                AND c.conname = 'test_repo_schemas_test_repository_id_fkey'
                            ) THEN
                                ALTER TABLE {DB_SCHEMA}.test_repo_schemas
                                ADD CONSTRAINT test_repo_schemas_test_repository_id_fkey
                                FOREIGN KEY (test_repository_id) 
                                REFERENCES {DB_SCHEMA}.test_repositories(id) ON DELETE CASCADE;
                            END IF;
                        END $$;
                    """, (DB_SCHEMA,))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Could not add foreign key to test_repositories: {e}")
                    conn.rollback()
                
                # Create index for test_repo_schemas
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_test_repo_schemas_schema_name 
                    ON {DB_SCHEMA}.test_repo_schemas(schema_name)
                """)
                
                conn.commit()
                logger.info(f"Test repository tables created/verified in schema {DB_SCHEMA}")
                return True
    except Exception as e:
        logger.error(f"Failed to create test repository tables: {e}", exc_info=True)
        return False


def ensure_test_repo_data_dir():
    """Ensure the test_repo_data directory exists."""
    TEST_REPO_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TEST_REPO_DATA_DIR


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def extract_zip_file(zip_path: Path, extract_to: Path) -> Path:
    """
    Extract a zip file to a directory.
    
    Args:
        zip_path: Path to the zip file
        extract_to: Directory to extract to
        
    Returns:
        Path to the extracted directory (first level directory in zip)
    """
    extract_to.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Get list of files
        file_list = zip_ref.namelist()
        
        # Extract all files
        zip_ref.extractall(extract_to)
        
        # Find the root directory (first directory in the zip)
        root_dirs = [f for f in file_list if f.endswith('/') and f.count('/') == 1]
        if root_dirs:
            root_dir_name = root_dirs[0].rstrip('/')
            extracted_root = extract_to / root_dir_name
        else:
            # No single root directory, use extract_to directly
            extracted_root = extract_to
        
        return extracted_root


def generate_schema_name(hash_value: str) -> str:
    """
    Generate a schema name from hash.
    
    Uses first 8 characters of hash: test_repo_{hash[:8]}
    PostgreSQL schema name limit: 63 characters
    
    Args:
        hash_value: SHA-256 hash string
        
    Returns:
        Schema name
    """
    schema_name = f"test_repo_{hash_value[:8]}"
    # Ensure it's valid (alphanumeric + underscore, max 63 chars)
    if len(schema_name) > 63:
        schema_name = schema_name[:63]
    return schema_name


def create_test_repository(
    name: str,
    zip_file_path: Path,
    zip_filename: Optional[str] = None
) -> Tuple[str, str, Path]:
    """
    Create a new test repository from a zip file.
    
    Args:
        name: Name for the test repository
        zip_file_path: Path to the uploaded zip file
        zip_filename: Original filename of the zip file
        
    Returns:
        Tuple of (test_repo_id, schema_name, extracted_path)
    """
    ensure_test_repo_data_dir()
    
    # Calculate hash of zip file
    hash_value = calculate_file_hash(zip_file_path)
    test_repo_id = hash_value  # Use hash as ID
    
    # Check if test repository already exists
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT id, schema_name 
                FROM {DB_SCHEMA}.test_repositories tr
                LEFT JOIN {DB_SCHEMA}.test_repo_schemas trs ON tr.id = trs.test_repository_id
                WHERE tr.hash = %s
            """, (hash_value,))
            existing = cursor.fetchone()
            
            if existing:
                logger.info(f"Test repository with hash {hash_value[:8]} already exists")
                return existing[0], existing[1] or generate_schema_name(hash_value), None
    
    # Extract zip file
    extract_dir = TEST_REPO_DATA_DIR / hash_value[:8]
    extracted_path = extract_zip_file(zip_file_path, extract_dir)
    
    # Generate schema name
    schema_name = generate_schema_name(hash_value)
    
    # Create schema
    if not create_schema_if_not_exists(schema_name):
        raise Exception(f"Failed to create schema: {schema_name}")
    
    # Store metadata in database
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Insert test repository
            cursor.execute(f"""
                INSERT INTO {DB_SCHEMA}.test_repositories 
                (id, name, zip_filename, extracted_path, hash, status, uploaded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                test_repo_id,
                name,
                zip_filename or zip_file_path.name,
                str(extracted_path),
                hash_value,
                'pending',
                datetime.now()
            ))
            
            # Insert schema mapping
            cursor.execute(f"""
                INSERT INTO {DB_SCHEMA}.test_repo_schemas 
                (test_repository_id, schema_name)
                VALUES (%s, %s)
                ON CONFLICT (test_repository_id) DO NOTHING
            """, (test_repo_id, schema_name))
            
            conn.commit()
    
    logger.info(f"Created test repository: {test_repo_id} with schema: {schema_name}")
    return test_repo_id, schema_name, extracted_path


def get_test_repository(test_repo_id: str) -> Optional[Dict]:
    """Get test repository by ID."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    tr.id,
                    tr.name,
                    tr.zip_filename,
                    tr.extracted_path,
                    tr.hash,
                    tr.uploaded_at,
                    tr.last_analyzed_at,
                    tr.status,
                    tr.metadata,
                    trs.schema_name
                FROM {DB_SCHEMA}.test_repositories tr
                LEFT JOIN {DB_SCHEMA}.test_repo_schemas trs ON tr.id = trs.test_repository_id
                WHERE tr.id = %s
            """, (test_repo_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'name': row[1],
                'zip_filename': row[2],
                'extracted_path': row[3],
                'hash': row[4],
                'uploaded_at': row[5],
                'last_analyzed_at': row[6],
                'status': row[7],
                'metadata': row[8],
                'schema_name': row[9]
            }


def list_test_repositories() -> List[Dict]:
    """List all test repositories."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    tr.id,
                    tr.name,
                    tr.zip_filename,
                    tr.extracted_path,
                    tr.hash,
                    tr.uploaded_at,
                    tr.last_analyzed_at,
                    tr.status,
                    tr.metadata,
                    trs.schema_name
                FROM {DB_SCHEMA}.test_repositories tr
                LEFT JOIN {DB_SCHEMA}.test_repo_schemas trs ON tr.id = trs.test_repository_id
                ORDER BY tr.uploaded_at DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'name': row[1],
                    'zip_filename': row[2],
                    'extracted_path': row[3],
                    'hash': row[4],
                    'uploaded_at': row[5],
                    'last_analyzed_at': row[6],
                    'status': row[7],
                    'metadata': row[8],
                    'schema_name': row[9]
                })
            
            return results


def delete_test_repository(test_repo_id: str) -> bool:
    """
    Delete a test repository.
    
    This will:
    1. Delete the schema (CASCADE)
    2. Delete bindings
    3. Delete test repository record
    4. Optionally delete extracted files
    
    Args:
        test_repo_id: ID of the test repository to delete
        
    Returns:
        True if successful, False otherwise
    """
    # Get schema name before deletion
    test_repo = get_test_repository(test_repo_id)
    if not test_repo:
        return False
    
    schema_name = test_repo.get('schema_name')
    extracted_path = test_repo.get('extracted_path')
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Delete bindings first (foreign key constraint)
            cursor.execute(f"""
                DELETE FROM {DB_SCHEMA}.repository_test_bindings
                WHERE test_repository_id = %s
            """, (test_repo_id,))
            
            # Delete schema mapping
            cursor.execute(f"""
                DELETE FROM {DB_SCHEMA}.test_repo_schemas
                WHERE test_repository_id = %s
            """, (test_repo_id,))
            
            # Delete test repository
            cursor.execute(f"""
                DELETE FROM {DB_SCHEMA}.test_repositories
                WHERE id = %s
            """, (test_repo_id,))
            
            conn.commit()
    
    # Drop schema (CASCADE will drop all tables)
    if schema_name:
        drop_schema_if_exists(schema_name, cascade=True)
    
    # Optionally delete extracted files
    if extracted_path:
        try:
            extract_path_obj = Path(extracted_path)
            if extract_path_obj.exists() and extract_path_obj.is_dir():
                shutil.rmtree(extract_path_obj)
                logger.info(f"Deleted extracted files: {extracted_path}")
        except Exception as e:
            logger.warning(f"Failed to delete extracted files: {e}")
    
    return True


def bind_test_repository_to_repo(
    repository_id: str,
    test_repository_id: str,
    is_primary: bool = False
) -> bool:
    """
    Bind a test repository to a code repository.
    
    Args:
        repository_id: ID of the code repository
        test_repository_id: ID of the test repository
        is_primary: Whether this is the primary test repository
        
    Returns:
        True if successful
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # If setting as primary, unset other primaries for this repository
            if is_primary:
                cursor.execute(f"""
                    UPDATE {DB_SCHEMA}.repository_test_bindings
                    SET is_primary = FALSE
                    WHERE repository_id = %s
                """, (repository_id,))
            
            # Insert or update binding
            cursor.execute(f"""
                INSERT INTO {DB_SCHEMA}.repository_test_bindings
                (repository_id, test_repository_id, is_primary)
                VALUES (%s, %s, %s)
                ON CONFLICT (repository_id, test_repository_id)
                DO UPDATE SET is_primary = EXCLUDED.is_primary
            """, (repository_id, test_repository_id, is_primary))
            
            conn.commit()
    
    return True


def unbind_test_repository_from_repo(
    repository_id: str,
    test_repository_id: str
) -> bool:
    """Unbind a test repository from a code repository."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                DELETE FROM {DB_SCHEMA}.repository_test_bindings
                WHERE repository_id = %s AND test_repository_id = %s
            """, (repository_id, test_repository_id))
            conn.commit()
    
    return True


def get_bound_test_repositories(repository_id: str) -> List[Dict]:
    """Get all test repositories bound to a code repository."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    tr.id,
                    tr.name,
                    tr.zip_filename,
                    tr.extracted_path,
                    tr.hash,
                    tr.uploaded_at,
                    tr.last_analyzed_at,
                    tr.status,
                    tr.metadata,
                    trs.schema_name,
                    rtb.is_primary
                FROM {DB_SCHEMA}.repository_test_bindings rtb
                JOIN {DB_SCHEMA}.test_repositories tr ON rtb.test_repository_id = tr.id
                LEFT JOIN {DB_SCHEMA}.test_repo_schemas trs ON tr.id = trs.test_repository_id
                WHERE rtb.repository_id = %s
                ORDER BY rtb.is_primary DESC, tr.uploaded_at DESC
            """, (repository_id,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'name': row[1],
                    'zip_filename': row[2],
                    'extracted_path': row[3],
                    'hash': row[4],
                    'uploaded_at': row[5],
                    'last_analyzed_at': row[6],
                    'status': row[7],
                    'metadata': row[8],
                    'schema_name': row[9],
                    'is_primary': row[10]
                })
            
            return results


def get_primary_test_repository(repository_id: str) -> Optional[Dict]:
    """Get the primary test repository for a code repository."""
    bound_repos = get_bound_test_repositories(repository_id)
    for repo in bound_repos:
        if repo.get('is_primary'):
            return repo
    return None


def update_test_repository_status(test_repo_id: str, status: str) -> bool:
    """Update the status of a test repository."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                UPDATE {DB_SCHEMA}.test_repositories
                SET status = %s, last_analyzed_at = %s
                WHERE id = %s
            """, (status, datetime.now() if status == 'ready' else None, test_repo_id))
            conn.commit()
    
    return True
