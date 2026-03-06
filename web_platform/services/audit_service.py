"""
Audit Service for Test Selection Logging

This service logs test selection runs to the audit log table for tracking and analysis.
"""

import sys
from pathlib import Path
from typing import Dict, Optional
import logging
import json

# Add deterministic directory to path for db_connection
project_root = Path(__file__).parent.parent.parent
deterministic_path = project_root / "deterministic"
sys.path.insert(0, str(deterministic_path))

from db_connection import get_connection, DB_SCHEMA

logger = logging.getLogger(__name__)

# Track if table has been verified/created
_table_verified = False


def ensure_audit_log_table_exists():
    """
    Ensure the selection_audit_log table exists in the database.
    Creates it if it doesn't exist (migration).
    """
    global _table_verified
    
    if _table_verified:
        return True
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Check if table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = %s 
                        AND table_name = 'selection_audit_log'
                    )
                """, (DB_SCHEMA,))
                
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    logger.info(f"Creating selection_audit_log table in schema {DB_SCHEMA}...")
                    
                    # Create the table
                    cursor.execute(f"""
                        CREATE TABLE {DB_SCHEMA}.selection_audit_log (
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
                    
                    # Create indexes
                    cursor.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_audit_log_repository 
                        ON {DB_SCHEMA}.selection_audit_log(repository_id)
                    """)
                    
                    cursor.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp 
                        ON {DB_SCHEMA}.selection_audit_log(timestamp)
                    """)
                    
                    conn.commit()
                    logger.info(f"Successfully created selection_audit_log table in schema {DB_SCHEMA}")
                else:
                    logger.debug(f"selection_audit_log table already exists in schema {DB_SCHEMA}")
                
                _table_verified = True
                return True
                
    except Exception as e:
        logger.error(f"Failed to ensure audit log table exists: {e}", exc_info=True)
        return False


def log_selection_run(
    repository_id: str,
    changed_files_count: int,
    selected_tests_count: int,
    confidence_scores: Dict,
    llm_used: bool,
    execution_time_ms: int,
    threshold_exceeded: bool = False
) -> bool:
    """
    Log a test selection run to the audit log table.
    
    Args:
        repository_id: Repository ID
        changed_files_count: Number of changed files
        selected_tests_count: Number of selected tests
        confidence_scores: Dictionary with confidence distribution {high: int, medium: int, low: int}
        llm_used: Whether LLM reasoning was used
        execution_time_ms: Execution time in milliseconds
        threshold_exceeded: Whether risk threshold was exceeded
        
    Returns:
        True if logged successfully, False otherwise
    """
    # Ensure table exists before trying to insert
    if not ensure_audit_log_table_exists():
        logger.warning("Cannot log audit entry - table creation failed")
        return False
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    INSERT INTO {DB_SCHEMA}.selection_audit_log 
                    (repository_id, changed_files_count, selected_tests_count, 
                     confidence_scores, llm_used, execution_time_ms, threshold_exceeded)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    repository_id,
                    changed_files_count,
                    selected_tests_count,
                    json.dumps(confidence_scores),
                    llm_used,
                    execution_time_ms,
                    threshold_exceeded
                ))
                
                conn.commit()
                logger.info(f"Audit log entry created for repository {repository_id}")
                return True
    except Exception as e:
        logger.error(f"Failed to log selection run: {e}", exc_info=True)
        return False
