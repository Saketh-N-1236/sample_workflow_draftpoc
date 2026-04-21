"""
Repository Database Service

This module provides database operations for repository management.
Stores repositories in the planon1 schema of the PostgreSQL database.

Key Features:
- CRUD operations for repositories
- Branch selection management
- Connection pooling support
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import uuid
import logging

# Add backend/ to path: backend/services/repository_db.py -> parent.parent = backend/
_backend_path = Path(__file__).parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

from deterministic.db_connection import get_connection, DB_SCHEMA

logger = logging.getLogger(__name__)


def create_repositories_table():
    """
    Create the repositories table in the database if it doesn't exist.
    
    This should be called once during setup/migration.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Create repositories table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.repositories (
                        id VARCHAR(50) PRIMARY KEY,
                        url TEXT NOT NULL,
                        provider VARCHAR(20),
                        local_path TEXT,
                        selected_branch VARCHAR(255),
                        default_branch VARCHAR(255),
                        last_commit VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_refreshed TIMESTAMP,
                        risk_threshold INTEGER DEFAULT 20,
                        UNIQUE(url)
                    )
                """)
                
                # Create indexes for fast lookups
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_repositories_url 
                    ON {DB_SCHEMA}.repositories(url)
                """)
                
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_repositories_provider 
                    ON {DB_SCHEMA}.repositories(provider)
                """)
                
                conn.commit()
                logger.info(f"Repositories table created/verified in schema {DB_SCHEMA}")
                
                # Add risk_threshold column if it doesn't exist (migration)
                try:
                    cursor.execute(f"""
                        ALTER TABLE {DB_SCHEMA}.repositories 
                        ADD COLUMN IF NOT EXISTS risk_threshold INTEGER DEFAULT 20
                    """)
                    conn.commit()
                    logger.info("Risk threshold column added/verified")
                except Exception as e:
                    logger.warning(f"Could not add risk_threshold column (may already exist): {e}")
                    conn.rollback()
                
                # Add semantic_config column if it doesn't exist (migration)
                try:
                    cursor.execute(f"""
                        ALTER TABLE {DB_SCHEMA}.repositories 
                        ADD COLUMN IF NOT EXISTS semantic_config JSONB
                    """)
                    conn.commit()
                    logger.info("Semantic config column added/verified")
                except Exception as e:
                    logger.warning(f"Could not add semantic_config column (may already exist): {e}")
                    conn.rollback()

                # Add encrypted_token column if it doesn't exist (migration)
                try:
                    cursor.execute(f"""
                        ALTER TABLE {DB_SCHEMA}.repositories
                        ADD COLUMN IF NOT EXISTS encrypted_token TEXT
                    """)
                    conn.commit()
                    logger.info("Encrypted token column added/verified")
                except Exception as e:
                    logger.warning(f"Could not add encrypted_token column (may already exist): {e}")
                    conn.rollback()

                return True
    except Exception as e:
        logger.error(f"Failed to create repositories table: {e}", exc_info=True)
        raise


def migrate_add_risk_threshold():
    """
    Migration function to add risk_threshold column to existing repositories table.
    
    This can be called to add the column to existing databases.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Check if column exists
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = %s 
                    AND table_name = 'repositories' 
                    AND column_name = 'risk_threshold'
                """, (DB_SCHEMA,))
                
                if cursor.fetchone():
                    logger.info("risk_threshold column already exists")
                    return True
                
                # Add column
                cursor.execute(f"""
                    ALTER TABLE {DB_SCHEMA}.repositories 
                    ADD COLUMN risk_threshold INTEGER DEFAULT 20
                """)
                conn.commit()
                logger.info("Successfully added risk_threshold column to repositories table")
                return True
    except Exception as e:
        logger.error(f"Failed to migrate risk_threshold column: {e}", exc_info=True)
        raise


def create_repository(
    url: str,
    provider: Optional[str] = None,
    local_path: Optional[str] = None,
    selected_branch: Optional[str] = None,
    default_branch: Optional[str] = None,
    risk_threshold: Optional[int] = None,
    access_token: Optional[str] = None,
) -> Dict:
    """
    Create a new repository record in the database.
    
    Args:
        url: Repository URL
        provider: Repository provider ('github' or 'gitlab')
        local_path: Local path (optional, for backward compatibility)
        selected_branch: Selected branch name
        default_branch: Default branch name
        risk_threshold: Risk threshold for test selection (default: 20)
        
    Returns:
        Dictionary with repository data including generated ID
    """
    repo_id = str(uuid.uuid4())
    now = datetime.now()
    
    # Default risk threshold if not provided
    if risk_threshold is None:
        risk_threshold = 20

    # Encrypt the PAT if provided
    encrypted_token: Optional[str] = None
    if access_token and access_token.strip():
        from services.token_encryption import encrypt_token
        encrypted_token = encrypt_token(access_token.strip())

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    INSERT INTO {DB_SCHEMA}.repositories
                    (id, url, provider, local_path, selected_branch, default_branch,
                     risk_threshold, encrypted_token, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        provider = EXCLUDED.provider,
                        selected_branch = COALESCE(EXCLUDED.selected_branch, repositories.selected_branch),
                        default_branch = COALESCE(EXCLUDED.default_branch, repositories.default_branch),
                        risk_threshold = COALESCE(EXCLUDED.risk_threshold, repositories.risk_threshold),
                        encrypted_token = COALESCE(EXCLUDED.encrypted_token, repositories.encrypted_token),
                        last_refreshed = CURRENT_TIMESTAMP
                    RETURNING id
                """, (repo_id, url, provider, local_path, selected_branch, default_branch,
                      risk_threshold, encrypted_token, now))
                
                # If conflict occurred, get the existing ID
                result = cursor.fetchone()
                if result:
                    repo_id = result[0]
                
                conn.commit()
                
                # Fetch the created/updated repository
                return get_repository_by_id(repo_id)
    except Exception as e:
        logger.error(f"Failed to create repository: {e}", exc_info=True)
        raise


def get_repository_by_id(repo_id: str) -> Optional[Dict]:
    """
    Get a repository by ID.
    
    Args:
        repo_id: Repository ID
        
    Returns:
        Dictionary with repository data or None if not found
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    SELECT id, url, provider, local_path, selected_branch,
                           default_branch, last_commit, created_at, last_refreshed,
                           risk_threshold, semantic_config, encrypted_token
                    FROM {DB_SCHEMA}.repositories
                    WHERE id = %s
                """, (repo_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                risk_threshold = None
                if len(row) > 9 and row[9] is not None:
                    risk_threshold = int(row[9])

                semantic_config = None
                if len(row) > 10 and row[10] is not None:
                    import json
                    semantic_config = row[10] if isinstance(row[10], dict) else json.loads(row[10])

                encrypted_token = row[11] if len(row) > 11 else None

                return {
                    "id": row[0],
                    "url": row[1],
                    "provider": row[2],
                    "local_path": row[3],
                    "selected_branch": row[4],
                    "default_branch": row[5],
                    "last_commit": row[6],
                    "createdAt": row[7],
                    "lastRefreshed": row[8],
                    "risk_threshold": risk_threshold,
                    "semantic_config": semantic_config,
                    "encrypted_token": encrypted_token,
                }
    except Exception as e:
        logger.error(f"Failed to get repository by ID: {e}", exc_info=True)
        raise


def get_repository_by_url(url: str) -> Optional[Dict]:
    """
    Get a repository by URL.
    
    Args:
        url: Repository URL
        
    Returns:
        Dictionary with repository data or None if not found
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    SELECT id, url, provider, local_path, selected_branch,
                           default_branch, last_commit, created_at, last_refreshed,
                           risk_threshold, semantic_config, encrypted_token
                    FROM {DB_SCHEMA}.repositories
                    WHERE url = %s
                """, (url,))

                row = cursor.fetchone()
                if not row:
                    return None

                risk_threshold = None
                if len(row) > 9 and row[9] is not None:
                    risk_threshold = int(row[9])

                semantic_config = None
                if len(row) > 10 and row[10] is not None:
                    import json
                    semantic_config = row[10] if isinstance(row[10], dict) else json.loads(row[10])

                encrypted_token = row[11] if len(row) > 11 else None

                return {
                    "id": row[0],
                    "url": row[1],
                    "provider": row[2],
                    "local_path": row[3],
                    "selected_branch": row[4],
                    "default_branch": row[5],
                    "last_commit": row[6],
                    "createdAt": row[7],
                    "lastRefreshed": row[8],
                    "risk_threshold": risk_threshold,
                    "semantic_config": semantic_config,
                    "encrypted_token": encrypted_token,
                }
    except Exception as e:
        logger.error(f"Failed to get repository by URL: {e}", exc_info=True)
        raise


def list_repositories() -> List[Dict]:
    """
    List all repositories.
    
    Returns:
        List of repository dictionaries
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    SELECT id, url, provider, local_path, selected_branch,
                           default_branch, last_commit, created_at, last_refreshed,
                           risk_threshold, semantic_config, encrypted_token
                    FROM {DB_SCHEMA}.repositories
                    ORDER BY created_at DESC
                """)

                rows = cursor.fetchall()
                result = []
                import json as _json
                for row in rows:
                    risk_threshold = None
                    if len(row) > 9 and row[9] is not None:
                        risk_threshold = int(row[9])

                    semantic_config = None
                    if len(row) > 10 and row[10] is not None:
                        semantic_config = row[10] if isinstance(row[10], dict) else _json.loads(row[10])

                    encrypted_token = row[11] if len(row) > 11 else None

                    result.append({
                        "id": row[0],
                        "url": row[1],
                        "provider": row[2],
                        "local_path": row[3],
                        "selected_branch": row[4],
                        "default_branch": row[5],
                        "last_commit": row[6],
                        "createdAt": row[7],
                        "lastRefreshed": row[8],
                        "risk_threshold": risk_threshold,
                        "semantic_config": semantic_config,
                        "encrypted_token": encrypted_token,
                    })
                return result
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}", exc_info=True)
        raise


def update_repository(
    repo_id: str,
    selected_branch: Optional[str] = None,
    default_branch: Optional[str] = None,
    last_commit: Optional[str] = None,
    last_refreshed: Optional[datetime] = None,
    risk_threshold: Optional[int] = None,
    _update_risk_threshold: bool = False,
    semantic_config: Optional[Dict] = None,
    access_token: Optional[str] = None,
) -> Optional[Dict]:
    """
    Update repository fields.
    
    Args:
        repo_id: Repository ID
        selected_branch: Selected branch name
        default_branch: Default branch name
        last_commit: Last commit SHA
        last_refreshed: Last refresh timestamp
        risk_threshold: Risk threshold for test selection
        
    Returns:
        Updated repository dictionary or None if not found
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Build update query dynamically based on provided fields
                updates = []
                params = []
                
                if selected_branch is not None:
                    updates.append("selected_branch = %s")
                    params.append(selected_branch)
                
                if default_branch is not None:
                    updates.append("default_branch = %s")
                    params.append(default_branch)
                
                if last_commit is not None:
                    updates.append("last_commit = %s")
                    params.append(last_commit)
                
                # Handle risk_threshold - allow None to disable risk analysis
                # Use the flag to determine if we should update (even if None)
                if _update_risk_threshold:
                    # Explicitly update threshold (can be None to set NULL in DB)
                    updates.append("risk_threshold = %s")
                    params.append(risk_threshold)  # This can be None, which will set to NULL in DB
                elif risk_threshold is not None:
                    # Backward compatibility: if flag not set but value provided, update it
                    updates.append("risk_threshold = %s")
                    params.append(risk_threshold)
                
                if semantic_config is not None:
                    import json
                    updates.append("semantic_config = %s::jsonb")
                    params.append(json.dumps(semantic_config))

                if access_token and access_token.strip():
                    from services.token_encryption import encrypt_token
                    updates.append("encrypted_token = %s")
                    params.append(encrypt_token(access_token.strip()))

                if last_refreshed is not None:
                    updates.append("last_refreshed = %s")
                    params.append(last_refreshed)
                elif not updates:  # If no other updates, at least update last_refreshed
                    updates.append("last_refreshed = CURRENT_TIMESTAMP")
                
                if not updates:
                    return get_repository_by_id(repo_id)
                
                params.append(repo_id)
                query = f"""
                    UPDATE {DB_SCHEMA}.repositories
                    SET {', '.join(updates)}
                    WHERE id = %s
                """
                
                cursor.execute(query, params)
                conn.commit()
                
                if cursor.rowcount == 0:
                    return None
                
                return get_repository_by_id(repo_id)
    except Exception as e:
        logger.error(f"Failed to update repository: {e}", exc_info=True)
        raise


def delete_repository(repo_id: str) -> bool:
    """
    Delete a repository by ID.
    
    Args:
        repo_id: Repository ID
        
    Returns:
        True if deleted, False if not found
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    DELETE FROM {DB_SCHEMA}.repositories
                    WHERE id = %s
                """, (repo_id,))
                
                conn.commit()
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete repository: {e}", exc_info=True)
        raise


def get_test_repository_bindings(repository_id: str) -> List[Dict]:
    """
    Get all test repositories bound to a repository.
    
    Args:
        repository_id: ID of the repository
        
    Returns:
        List of test repository dictionaries
    """
    try:
        from services.test_repo_service import get_bound_test_repositories
        return get_bound_test_repositories(repository_id)
    except Exception as e:
        logger.error(f"Failed to get test repository bindings: {e}")
        return []


def bind_test_repository(repository_id: str, test_repository_id: str, is_primary: bool = False) -> bool:
    """
    Bind a test repository to a repository.
    
    Args:
        repository_id: ID of the repository
        test_repository_id: ID of the test repository
        is_primary: Whether this is the primary test repository
        
    Returns:
        True if successful
    """
    try:
        from services.test_repo_service import bind_test_repository_to_repo
        return bind_test_repository_to_repo(repository_id, test_repository_id, is_primary)
    except Exception as e:
        logger.error(f"Failed to bind test repository: {e}")
        return False


def unbind_test_repository(repository_id: str, test_repository_id: str) -> bool:
    """
    Unbind a test repository from a repository.
    
    Args:
        repository_id: ID of the repository
        test_repository_id: ID of the test repository
        
    Returns:
        True if successful
    """
    try:
        from services.test_repo_service import unbind_test_repository_from_repo
        return unbind_test_repository_from_repo(repository_id, test_repository_id)
    except Exception as e:
        logger.error(f"Failed to unbind test repository: {e}")
        return False


def get_primary_test_repository(repository_id: str) -> Optional[Dict]:
    """
    Get the primary test repository for a repository.
    
    Args:
        repository_id: ID of the repository
        
    Returns:
        Test repository dictionary or None
    """
    try:
        from services.test_repo_service import get_primary_test_repository
        return get_primary_test_repository(repository_id)
    except Exception as e:
        logger.error(f"Failed to get primary test repository: {e}")
        return None
