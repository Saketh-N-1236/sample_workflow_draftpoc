"""
Verification script to check if test data has been stored successfully in:
1. PostgreSQL database
2. Pinecone vector database

Run this script after running analysis to verify data storage.
"""

import sys
import os
from pathlib import Path

# Add backend/ to path (this script lives in backend/scripts/)
current_file = Path(__file__).resolve()
backend_path = current_file.parent.parent  # backend/

if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from deterministic.db_connection import get_connection
from semantic_retrieval.backends import get_backend
from semantic_retrieval.config import VECTOR_BACKEND
import os as os_module


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_item(label, value, status="OK"):
    """Print a formatted item."""
    status_symbol = "[OK]" if status == "OK" else "[FAIL]" if status == "ERROR" else "[WARN]"
    if status == "INFO":
        status_symbol = "[INFO]"
    print(f"{status_symbol:<7} {label:.<40} {value}")


def verify_postgresql():
    """Verify test data in PostgreSQL database."""
    print_header("PostgreSQL Database Verification")
    
    try:
        # Use context manager for proper connection handling
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Check test_registry table
            cursor.execute("SELECT COUNT(*) FROM planon1.test_registry")
            test_count = cursor.fetchone()[0]
            print_item("Test Registry Count", str(test_count), "OK" if test_count > 0 else "ERROR")
            
            # Check test_metadata table
            cursor.execute("SELECT COUNT(*) FROM planon1.test_metadata")
            metadata_count = cursor.fetchone()[0]
            print_item("Test Metadata Count", str(metadata_count), "OK" if metadata_count > 0 else "ERROR")
            
            # Check test_dependencies table
            cursor.execute("SELECT COUNT(*) FROM planon1.test_dependencies")
            deps_count = cursor.fetchone()[0]
            print_item("Test Dependencies Count", str(deps_count), "OK" if deps_count > 0 else "WARNING")
            
            # Check reverse_index table
            cursor.execute("SELECT COUNT(*) FROM planon1.reverse_index")
            reverse_count = cursor.fetchone()[0]
            print_item("Reverse Index Count", str(reverse_count), "OK" if reverse_count > 0 else "WARNING")
            
            # Check test_structure table
            cursor.execute("SELECT COUNT(*) FROM planon1.test_structure")
            structure_count = cursor.fetchone()[0]
            print_item("Test Structure Count", str(structure_count), "OK" if structure_count > 0 else "WARNING")
            
            # Check if embeddings column exists and has data (for pgvector)
            try:
                # First check if column exists
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'planon1' 
                    AND table_name = 'test_metadata' 
                    AND column_name = 'embedding'
                """)
                column_exists = cursor.fetchone() is not None
                
                if column_exists:
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM planon1.test_metadata 
                        WHERE embedding IS NOT NULL
                    """)
                    embedding_count = cursor.fetchone()[0]
                    print_item("Embeddings in PostgreSQL", str(embedding_count), "OK" if embedding_count > 0 else "INFO")
                else:
                    print_item("Embeddings in PostgreSQL", "Column not found (using Pinecone)", "INFO")
            except Exception as e:
                # Rollback the transaction if it failed
                conn.rollback()
                print_item("Embeddings in PostgreSQL", f"Error checking: {str(e)[:50]}", "WARNING")
            
            # Show sample test
            try:
                cursor.execute("""
                    SELECT test_id, method_name, class_name, test_type 
                    FROM planon1.test_registry 
                    LIMIT 5
                """)
                samples = cursor.fetchall()
                if samples:
                    print("\nSample Tests:")
                    for test_id, method_name, class_name, test_type in samples:
                        test_desc = f"{class_name}.{method_name}" if class_name else method_name
                        print(f"   - {test_id}: {test_desc} ({test_type})")
            except Exception as e:
                conn.rollback()
                print(f"\n[WARN] Could not fetch sample tests: {e}")
            
            cursor.close()
        
        print("\n[OK] PostgreSQL verification complete")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] PostgreSQL verification: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_pinecone():
    """Verify test data in Pinecone vector database."""
    print_header("Pinecone Vector Database Verification")
    
    # Check if Pinecone is configured
    pinecone_key = os_module.getenv('PINECONE_API_KEY')
    if not pinecone_key:
        print_item("PINECONE_API_KEY", "NOT SET", "ERROR")
        print("\n[SKIP] Pinecone verification skipped - API key not configured")
        return False
    
    print_item("PINECONE_API_KEY", "SET", "OK")
    
    index_name = os_module.getenv('PINECONE_INDEX_NAME', 'test-embeddings')
    print_item("PINECONE_INDEX_NAME", index_name, "OK")
    
    environment = os_module.getenv('PINECONE_ENVIRONMENT', 'us-east-1')
    print_item("PINECONE_ENVIRONMENT", environment, "OK")
    
    vector_backend = os_module.getenv('VECTOR_BACKEND', 'pinecone')
    print_item("VECTOR_BACKEND", vector_backend, "OK" if vector_backend.lower() == 'pinecone' else "WARNING")
    
    try:
        # Get Pinecone backend
        backend = get_backend()
        
        if not backend or not backend.is_available():
            print("\n[FAIL] Pinecone backend is not available")
            return False
        
        print_item("Pinecone Backend", "Available", "OK")
        
        # Try to query the index to get stats
        # Note: Pinecone doesn't have a direct count method, so we'll query with a dummy vector
        try:
            # Create a dummy query vector (768 dimensions for nomic-embed-text)
            dummy_vector = [0.0] * 768
            
            # Query with top_k=1 to verify index is accessible
            results = backend.index.query(
                vector=dummy_vector,
                top_k=1,
                include_metadata=True
            )
            
            # Get index stats using describe_index_stats
            try:
                stats = backend.index.describe_index_stats()
                total_vectors = stats.get('total_vector_count', 0)
                print_item("Total Vectors in Pinecone", str(total_vectors), "OK" if total_vectors > 0 else "ERROR")
                
                if hasattr(stats, 'namespaces') and stats.namespaces:
                    print("\nNamespace Statistics:")
                    for namespace, ns_stats in stats.namespaces.items():
                        ns_count = ns_stats.get('vector_count', 0)
                        namespace_name = namespace if namespace else "(default)"
                        print(f"   - {namespace_name}: {ns_count} vectors")
                elif isinstance(stats, dict) and 'namespaces' in stats and stats['namespaces']:
                    print("\nNamespace Statistics:")
                    for namespace, ns_stats in stats['namespaces'].items():
                        ns_count = ns_stats.get('vector_count', 0)
                        namespace_name = namespace if namespace else "(default)"
                        print(f"   - {namespace_name}: {ns_count} vectors")
                
            except Exception as e:
                print_item("Index Stats", f"Could not retrieve: {e}", "WARNING")
            
            # Try to get a sample vector
            if results.matches:
                sample = results.matches[0]
                metadata = sample.metadata or {}
                print("\nSample Vector:")
                print(f"   - ID: {sample.id}")
                print(f"   - Similarity: {sample.score:.4f}")
                print(f"   - Metadata keys: {list(metadata.keys())}")
                if metadata:
                    print(f"   - Method: {metadata.get('method_name', 'N/A')}")
                    print(f"   - Class: {metadata.get('class_name', 'N/A')}")
                    print(f"   - Type: {metadata.get('test_type', 'N/A')}")
            
        except Exception as e:
            print(f"\n[WARN] Could not query Pinecone index: {e}")
            print("   Index may be empty or not yet created")
        
        print("\n[OK] Pinecone verification complete")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Pinecone verification: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification checks."""
    print_header("Storage Verification Script")
    print("\nThis script verifies that test data has been stored in:")
    print("  1. PostgreSQL database (planon1 schema)")
    print("  2. Pinecone vector database")
    
    pg_ok = verify_postgresql()
    pinecone_ok = verify_pinecone()
    
    print_header("Summary")
    print_item("PostgreSQL", "PASS" if pg_ok else "FAIL", "OK" if pg_ok else "ERROR")
    print_item("Pinecone", "PASS" if pinecone_ok else "FAIL", "OK" if pinecone_ok else "ERROR")
    
    if pg_ok and pinecone_ok:
        print("\n[OK] All verifications passed")
    elif pg_ok:
        print("\n[WARN] PostgreSQL passed. Pinecone verification failed or skipped")
    elif pinecone_ok:
        print("\n[WARN] Pinecone passed. PostgreSQL verification failed")
    else:
        print("\n[FAIL] Both verifications failed. Check your configuration.")


if __name__ == "__main__":
    main()
