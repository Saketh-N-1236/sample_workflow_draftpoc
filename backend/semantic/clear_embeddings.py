"""
Clear all embeddings from the Pinecone vector database.

Usage:
    python -m semantic.clear_embeddings

After clearing, regenerate with:
    python -m semantic.embedding_generation.embedding_generator
    (Set TEST_REPO_PATH to the extracted test repository directory.)
"""

import sys
from pathlib import Path

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from semantic.config import VECTOR_BACKEND, PINECONE_INDEX_NAME, PINECONE_API_KEY, PINECONE_ENVIRONMENT
from test_analysis.utils.output_formatter import print_header, print_section, print_item


def clear_pinecone():
    """Clear all embeddings from Pinecone index."""
    try:
        from pinecone import Pinecone, ServerlessSpec
        from semantic.config import EMBEDDING_DIMENSIONS
        
        if not PINECONE_API_KEY:
            print_item("Error", "PINECONE_API_KEY environment variable is required")
            return False
        
        print_item("Connecting to Pinecone", f"Index: {PINECONE_INDEX_NAME}")
        
        # Initialize Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # Check if index exists
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        if PINECONE_INDEX_NAME not in existing_indexes:
            print_item("Index not found", f"Index '{PINECONE_INDEX_NAME}' does not exist. Nothing to clear.")
            return True
        
        # Get index stats before deletion
        index = pc.Index(PINECONE_INDEX_NAME)
        stats = index.describe_index_stats()
        count_before = stats.get('total_vector_count', 0)
        
        print_item("Vectors found", count_before)
        
        if count_before == 0:
            print_item("Index is empty", "No vectors to delete")
            return True
        
        # Delete all vectors by deleting the entire index and recreating it
        print_item("Deleting index", f"Deleting '{PINECONE_INDEX_NAME}'...")
        pc.delete_index(PINECONE_INDEX_NAME)
        
        # Wait a moment for deletion to complete
        import time
        time.sleep(2)
        
        # Recreate the index
        print_item("Recreating index", f"Creating '{PINECONE_INDEX_NAME}'...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIMENSIONS,
            metric='cosine',
            spec=ServerlessSpec(
                cloud='aws',
                region=PINECONE_ENVIRONMENT
            )
        )
        
        # Wait for index to be ready
        time.sleep(2)
        
        # Verify deletion
        new_index = pc.Index(PINECONE_INDEX_NAME)
        new_stats = new_index.describe_index_stats()
        count_after = new_stats.get('total_vector_count', 0)
        
        print_item(f"Pinecone cleared", f"{count_before} embeddings deleted, {count_after} remaining")
        return True
        
    except Exception as e:
        print_item("Pinecone clear failed", str(e))
        import traceback
        traceback.print_exc()
        return False


def main():
    print_header("Clear Embeddings from Vector Database")
    print()
    
    print_section("Current Configuration:")
    print_item("Backend", VECTOR_BACKEND)
    if VECTOR_BACKEND == 'pinecone':
        print_item("Index name", PINECONE_INDEX_NAME)
        print_item("Environment", PINECONE_ENVIRONMENT)
    print()
    
    if VECTOR_BACKEND == 'pinecone':
        print_section("Clearing Pinecone...")
        success = clear_pinecone()
    else:
        print_section("Unsupported backend")
        print_item("Error", f"Only pinecone backend is supported. VECTOR_BACKEND={VECTOR_BACKEND}")
        success = False
    
    print()
    if success:
        print_header("Clear Complete!")
        print("You can now regenerate embeddings with:")
        print("  python -m semantic.embedding_generation.embedding_generator")
        print("  (Set TEST_REPO_PATH to the extracted test repository directory path.)")
    else:
        print_header("Clear Failed!")
        print("Check the error messages above.")


if __name__ == "__main__":
    main()
