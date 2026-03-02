"""
Diagnostic script to test semantic search and see similarity scores.

This helps debug why semantic search isn't finding tests.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest
from semantic_retrieval.backends import get_backend
from semantic_retrieval.config import CHROMADB_DATA_PATH


async def test_similarity():
    """Test semantic search with a sample query and show top results."""
    
    # Sample query - similar to what git_diff_processor would generate
    sample_functions = [
        {'module': 'llm.factory', 'function': 'create_provider'},
        {'module': 'agent.mcp_client', 'function': 'call_tool'}
    ]
    
    functions_str = ', '.join(
        f"{cf['function']}() in {cf['module']}"
        for cf in sample_functions
    )
    change_description = (
        f"Changed functions: {functions_str}. "
        f"Module: {sample_functions[0]['module']}."
    )
    
    print("Query:", change_description)
    print()
    
    # Get query embedding
    settings = get_settings()
    llm = LLMFactory.create_embedding_provider(settings)
    response = await llm.get_embeddings(EmbeddingRequest(texts=[change_description]))
    query_embedding = response.embeddings[0]
    
    # Get backend
    backend = get_backend(None)
    
    # Check if backend is available
    if not backend.is_available():
        print("ERROR: Backend is not available!")
        return
    
    # Search with very low threshold to see all results
    print("Searching with threshold 0.0 (showing all results)...")
    print(f"Query embedding dimensions: {len(query_embedding)}")
    print(f"Query embedding sample (first 5): {query_embedding[:5]}")
    print()
    
    # Direct ChromaDB query for debugging
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from semantic_retrieval.config import CHROMADB_DATA_PATH
    
    data_path = Path(CHROMADB_DATA_PATH)
    client = chromadb.PersistentClient(
        path=str(data_path),
        settings=ChromaSettings(anonymized_telemetry=False)
    )
    collection = client.get_collection("test_embeddings")
    
    print("Direct ChromaDB query...")
    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5,
        include=['metadatas', 'distances']
    )
    print(f"Raw results keys: {raw_results.keys()}")
    print(f"IDs: {raw_results.get('ids', [])}")
    print(f"Distances: {raw_results.get('distances', [])}")
    print()
    
    try:
        results = await backend.search_similar(
            query_embedding,
            similarity_threshold=0.0,  # No threshold - show all
            max_results=20
        )
    except Exception as e:
        print(f"ERROR during search: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print(f"\nFound {len(results)} results:")
    print("-" * 80)
    for i, result in enumerate(results, 1):
        similarity = result.get('similarity', 0)
        test_id = result.get('test_id', '')
        method = result.get('method_name', '')
        class_name = result.get('class_name', '')
        print(f"{i:2d}. [{similarity:.3f}] {test_id}: {class_name}.{method}")
    
    print()
    print("-" * 80)
    print("Threshold analysis:")
    thresholds = [0.9, 0.8, 0.75, 0.7, 0.6, 0.5, 0.4, 0.3]
    for thresh in thresholds:
        count = sum(1 for r in results if r.get('similarity', 0) >= thresh)
        print(f"  Threshold {thresh:.2f}: {count} results")


if __name__ == "__main__":
    asyncio.run(test_similarity())
