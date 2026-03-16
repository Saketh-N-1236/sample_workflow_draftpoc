"""
Show sample metadata stored with embeddings.
"""

import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import chromadb
from chromadb.config import Settings as ChromaSettings
from semantic_retrieval.config import CHROMADB_DATA_PATH
from semantic_retrieval.embedding_generator import load_test_data, build_embedding_text

# Load test data to see what goes into embeddings
print("=" * 80)
print("SAMPLE METADATA STORED WITH EMBEDDINGS")
print("=" * 80)
print()

# Load test data
tests = load_test_data()
if tests:
    sample_test = tests[0]  # Get first test
    print("1. TEST DATA (from registry + metadata + function mappings):")
    print("-" * 80)
    print(json.dumps(sample_test, indent=2, default=str))
    print()

# Show embedding text
if tests:
    print("2. EMBEDDING TEXT (what gets converted to vector):")
    print("-" * 80)
    embedding_text = build_embedding_text(sample_test)
    print(embedding_text)
    print()

# Show what metadata is stored in ChromaDB
print("3. CHROMADB METADATA (what's stored in vector DB):")
print("-" * 80)
data_path = Path(CHROMADB_DATA_PATH)
client = chromadb.PersistentClient(
    path=str(data_path),
    settings=ChromaSettings(anonymized_telemetry=False)
)

try:
    collection = client.get_collection("test_embeddings")
    count = collection.count()
    print(f"Total embeddings: {count}")
    print()
    
    # Get a sample
    sample = collection.get(ids=[tests[0]['test_id']] if tests else ['test_0001'], limit=1)
    if sample['ids']:
        test_id = sample['ids'][0]
        metadata = sample['metadatas'][0] if sample['metadatas'] else {}
        
        print(f"Sample test_id: {test_id}")
        print("Metadata stored:")
        print(json.dumps(metadata, indent=2))
        print()
        
        # Show a few more examples
        print("4. ADDITIONAL SAMPLES (different tests):")
        print("-" * 80)
        more_samples = collection.get(limit=5)
        for i, (test_id, meta) in enumerate(zip(more_samples['ids'], more_samples['metadatas']), 1):
            print(f"\nSample {i}: {test_id}")
            print(f"  Method: {meta.get('method_name', 'N/A')}")
            print(f"  Class: {meta.get('class_name', 'N/A')}")
            print(f"  Type: {meta.get('test_type', 'N/A')}")
            print(f"  File: {Path(meta.get('test_file_path', '')).name}")
            
except Exception as e:
    print(f"Error: {e}")

print()
print("=" * 80)
print("METADATA STRUCTURE SUMMARY")
print("=" * 80)
print("""
ChromaDB stores:
  - test_id: Unique identifier (e.g., 'test_0001')
  - method_name: Test method name (e.g., 'test_agent_initialization')
  - class_name: Test class name (e.g., 'TestLangGraphAgent')
  - test_file_path: Full path to test file
  - test_type: Type of test (e.g., 'unit', 'integration')

The embedding vector (768 dimensions) is generated from:
  - Test name (human-readable)
  - Component/class name
  - Description (if available)
  - Module under test
  - Functions tested (from function mappings)
  - Test type
  - Markers
  - Async flag
""")
