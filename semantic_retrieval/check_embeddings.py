"""
Check if embeddings are stored in ChromaDB.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import chromadb
from chromadb.config import Settings as ChromaSettings
from semantic_retrieval.config import CHROMADB_DATA_PATH

data_path = Path(CHROMADB_DATA_PATH)
client = chromadb.PersistentClient(
    path=str(data_path),
    settings=ChromaSettings(anonymized_telemetry=False)
)

try:
    collection = client.get_collection("test_embeddings")
    count = collection.count()
    print(f"ChromaDB collection 'test_embeddings' has {count} embeddings")
    
    if count > 0:
        # Get a sample
        sample = collection.get(limit=3)
        print(f"\nSample IDs: {sample['ids'][:3]}")
        print(f"Sample metadata keys: {list(sample['metadatas'][0].keys()) if sample['metadatas'] else 'None'}")
        
        # Try a simple query
        print("\nTrying a simple query...")
        results = collection.query(
            query_embeddings=[sample['embeddings'][0] if sample['embeddings'] else None],
            n_results=3
        )
        print(f"Query returned {len(results['ids'][0]) if results['ids'] else 0} results")
except Exception as e:
    print(f"Error: {e}")
