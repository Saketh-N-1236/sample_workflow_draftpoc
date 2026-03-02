"""
Test script to verify pgvector installation and functionality.

Run: python test_pgvector.py
"""

import sys
from pathlib import Path

# Add deterministic to path
sys.path.insert(0, str(Path(__file__).parent / "deterministic"))

from deterministic.db_connection import get_connection, DB_SCHEMA

def test_pgvector():
    """Test pgvector extension availability and functionality."""
    print("=" * 70)
    print("PGVECTOR INSTALLATION TEST")
    print("=" * 70)
    print()
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Step 1: Check if extension exists in available extensions
            print("Step 1: Checking if pgvector extension is available...")
            try:
                cursor.execute("""
                    SELECT name, default_version 
                    FROM pg_available_extensions 
                    WHERE name = 'vector'
                """)
                result = cursor.fetchone()
                
                if result:
                    print(f"✅ pgvector extension found!")
                    print(f"   Version: {result[1]}")
                else:
                    print("❌ pgvector extension NOT found in available extensions")
                    print()
                    print("   This means pgvector is not installed on your PostgreSQL server.")
                    print("   Installation needed - see troubleshooting guide below.")
                    return False
            except Exception as e:
                print(f"❌ Error checking available extensions: {e}")
                return False
            
            print()
            
            # Step 2: Try to create the extension
            print("Step 2: Attempting to create pgvector extension...")
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                conn.commit()
                print("✅ Extension created successfully!")
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Failed to create extension: {error_msg}")
                print()
                if "permission denied" in error_msg.lower():
                    print("   Issue: Permission denied")
                    print("   Solution: Connect as superuser (postgres user)")
                elif "extension" in error_msg.lower() and "not available" in error_msg.lower():
                    print("   Issue: Extension files not found")
                    print("   Solution: pgvector must be installed on PostgreSQL server")
                return False
            
            print()
            
            # Step 3: Verify extension is installed
            print("Step 3: Verifying extension is installed...")
            try:
                cursor.execute("""
                    SELECT extname, extversion 
                    FROM pg_extension 
                    WHERE extname = 'vector'
                """)
                result = cursor.fetchone()
                
                if result:
                    print(f"✅ Extension is installed!")
                    print(f"   Name: {result[0]}")
                    print(f"   Version: {result[1]}")
                else:
                    print("❌ Extension not found in installed extensions")
                    return False
            except Exception as e:
                print(f"❌ Error verifying extension: {e}")
                return False
            
            print()
            
            # Step 4: Test vector operations
            print("Step 4: Testing vector operations...")
            try:
                cursor.execute("SELECT '[1,2,3]'::vector")
                result = cursor.fetchone()
                print(f"✅ Vector type works! Sample: {result[0]}")
                
                cursor.execute("""
                    SELECT '[1,2,3]'::vector <=> '[4,5,6]'::vector AS distance
                """)
                result = cursor.fetchone()
                print(f"✅ Cosine distance operator works! Distance: {result[0]:.4f}")
                
            except Exception as e:
                print(f"❌ Vector operations failed: {e}")
                return False
            
            print()
            print("=" * 70)
            print("✅ ALL TESTS PASSED! pgvector is working correctly.")
            print("=" * 70)
            return True
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

if __name__ == "__main__":
    success = test_pgvector()
    sys.exit(0 if success else 1)