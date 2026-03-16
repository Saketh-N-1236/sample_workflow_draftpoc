"""
Create Repositories Table Script

This script creates the repositories table in the planon1 schema.
Run this once to set up the database schema for repository storage.

Usage:
    python backend/scripts/create_repositories_table.py
"""

import sys
from pathlib import Path

# Add backend/ to path (this script lives in backend/scripts/)
backend_path = Path(__file__).parent.parent  # backend/
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.repository_db import create_repositories_table
from deterministic.db_connection import test_connection, DB_SCHEMA


def main():
    """Main function to create repositories table."""
    print("=" * 60)
    print("Creating Repositories Table")
    print("=" * 60)
    print()
    print(f"Database Schema: {DB_SCHEMA}")
    print()
    
    # Test database connection first
    print("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        print("Please check your .env file and database configuration.")
        return False
    
    print()
    print("Creating repositories table...")
    try:
        create_repositories_table()
        print()
        print("[OK] Repositories table created successfully!")
        print()
        print("=" * 60)
        print("Setup Complete!")
        print("=" * 60)
        return True
    except Exception as e:
        print()
        print(f"[ERROR] Failed to create table: {e}")
        print()
        print("=" * 60)
        print("Setup Failed!")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
