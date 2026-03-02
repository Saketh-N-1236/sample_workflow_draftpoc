"""
Clear all embeddings from the vector database.

This script deletes all embeddings from either ChromaDB or pgvector,
allowing you to start fresh with new embeddings.

Usage:
    python semantic_retrieval/clear_embeddings.py
"""

import sys
from pathlib import Path

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from deterministic.db_connection import get_connection
from semantic_retrieval.backends import get_backend
from semantic_retrieval.config import VECTOR_BACKEND, CHROMADB_DATA_PATH
from test_analysis.utils.output_formatter import print_header, print_section, print_item


def clear_chromadb():
    """Clear ChromaDB collection."""
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    
    data_path = Path(CHROMADB_DATA_PATH)
    data_path.mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(
        path=str(data_path),
        settings=ChromaSettings(anonymized_telemetry=False)
    )
    
    try:
        collection = client.get_collection("test_embeddings")
        count_before = collection.count()
        
        # Delete all embeddings
        # ChromaDB doesn't have a direct "delete all" method, so we get all IDs and delete them
        if count_before > 0:
            all_ids = collection.get()['ids']
            if all_ids:
                collection.delete(ids=all_ids)
        
        count_after = collection.count()
        print_item(f"ChromaDB cleared", f"{count_before} embeddings deleted, {count_after} remaining")
        return True
    except Exception as e:
        print_item("ChromaDB collection not found or already empty", str(e))
        return False


def clear_pgvector(conn):
    """Clear pgvector embeddings from database."""
    from deterministic.db_connection import DB_SCHEMA
    
    try:
        with conn.cursor() as cursor:
            # Count before
            cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.test_metadata WHERE embedding IS NOT NULL")
            count_before = cursor.fetchone()[0]
            
            # Clear embeddings
            cursor.execute(f"UPDATE {DB_SCHEMA}.test_metadata SET embedding = NULL WHERE embedding IS NOT NULL")
            conn.commit()
            
            # Count after
            cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.test_metadata WHERE embedding IS NOT NULL")
            count_after = cursor.fetchone()[0]
            
            print_item(f"pgvector cleared", f"{count_before} embeddings deleted, {count_after} remaining")
            return True
    except Exception as e:
        print_item("pgvector clear failed", str(e))
        return False


def main():
    print_header("Clear Embeddings from Vector Database")
    print()
    
    print_section("Current Configuration:")
    print_item("Backend", VECTOR_BACKEND)
    if VECTOR_BACKEND == 'chromadb':
        print_item("Data path", CHROMADB_DATA_PATH)
    print()
    
    if VECTOR_BACKEND == 'chromadb':
        print_section("Clearing ChromaDB...")
        success = clear_chromadb()
    else:
        print_section("Clearing pgvector...")
        conn = get_connection()
        try:
            success = clear_pgvector(conn)
        finally:
            conn.close()
    
    print()
    if success:
        print_header("Clear Complete!")
        print("You can now regenerate embeddings with:")
        print("  python semantic_retrieval/embedding_generator.py")
    else:
        print_header("Clear Failed!")
        print("Check the error messages above.")


if __name__ == "__main__":
    main()
