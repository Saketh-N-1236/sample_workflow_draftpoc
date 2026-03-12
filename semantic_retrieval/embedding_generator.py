"""
Step 9: Generate Embeddings for Semantic Search

Reads:
  - test_analysis/outputs/03_test_registry.json
  - test_analysis/outputs/05_test_metadata.json

For each test, builds a rich text description, generates a 768-dim
embedding using Ollama nomic-embed-text, stores in Pinecone.

Run ONCE after the full 8-step pipeline:
    python semantic_retrieval/embedding_generator.py

Re-run only when new tests are added.

Pre-requisite:
    ollama pull nomic-embed-text
    # ollama must be running on localhost:11434

.env must have:
    EMBEDDING_PROVIDER=ollama
    OLLAMA_BASE_URL=http://localhost:11434
    OLLAMA_EMBEDDING_MODEL=nomic-embed-text
    VECTOR_BACKEND=pinecone
    PINECONE_API_KEY=your_api_key
    PINECONE_INDEX_NAME=test-embeddings
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Same path setup pattern as other pipeline scripts
# Add parent directory FIRST to ensure config/llm packages are found before semantic_retrieval/config.py
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# Add current directory AFTER parent to allow semantic_retrieval imports
sys.path.insert(1, str(Path(__file__).parent))

# Import config.settings BEFORE semantic_retrieval.config to avoid shadowing
try:
    from config.settings import get_settings
    from llm.factory import LLMFactory
    from llm.models import EmbeddingRequest
except ImportError as e:
    print(f"ERROR: Could not import config/llm packages. Make sure they exist at the project root.")
    print(f"Import error: {e}")
    print(f"Project root: {project_root}")
    print(f"Python path: {sys.path[:3]}")
    sys.exit(1)
from deterministic.db_connection import get_connection
from semantic_retrieval.backends import get_backend
from semantic_retrieval.config import BATCH_SIZE, VECTOR_BACKEND
from test_analysis.utils.output_formatter import print_header, print_section, print_item
from test_analysis.utils.config import get_output_dir

# Use schema-specific output directory if TEST_REPO_SCHEMA is set
schema_name = os.getenv('TEST_REPO_SCHEMA')
if schema_name:
    OUTPUT_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs" / schema_name
else:
    OUTPUT_DIR = Path(__file__).parent.parent / "test_analysis" / "outputs"
REGISTRY_JSON = OUTPUT_DIR / "03_test_registry.json"
METADATA_JSON = OUTPUT_DIR / "05_test_metadata.json"
FUNCTION_MAPPINGS_JSON = OUTPUT_DIR / "04b_function_calls.json"


def load_test_data() -> list:
    """
    Load and merge test registry + metadata + function mappings into one list.

    Each item has:
      test_id, method_name, class_name, test_type, file_path,
      module, description, markers, is_async, functions_tested
    """
    with open(REGISTRY_JSON, 'r', encoding='utf-8') as f:
        registry = json.load(f)['data']['tests']

    with open(METADATA_JSON, 'r', encoding='utf-8') as f:
        raw_meta = json.load(f)['data']['test_metadata']
        meta_map = {m['test_id']: m for m in raw_meta}

    # Load function mappings if available
    function_map = {}
    if FUNCTION_MAPPINGS_JSON.exists():
        try:
            with open(FUNCTION_MAPPINGS_JSON, 'r', encoding='utf-8') as f:
                func_data = json.load(f)
                # Build map: test_id -> list of (module, function) tuples
                # The JSON structure is: data.test_function_mappings[]
                mappings = func_data.get('data', {}).get('test_function_mappings', [])
                for mapping in mappings:
                    test_id = mapping.get('test_id')
                    module_name = mapping.get('module_name')
                    function_name = mapping.get('function_name')
                    
                    # Only include production function mappings where module_name is not null
                    # module_name null means it's a test framework function or unresolved call
                    if test_id and module_name and function_name and module_name.strip():
                        # Filter out test framework functions
                        test_framework_funcs = {'assert', 'patch', 'Mock', 'MagicMock', 'AsyncMock', 
                                               'assert_called_once', 'assert_called', 'assertEqual'}
                        if function_name not in test_framework_funcs:
                            if test_id not in function_map:
                                function_map[test_id] = []
                            function_map[test_id].append({
                                'module': module_name,
                                'function': function_name,
                                'source': mapping.get('source', '')
                            })
        except Exception as e:
            print(f"Warning: Could not load function mappings: {e}")

    merged = []
    for test in registry:
        test_id   = test['test_id']
        meta      = meta_map.get(test_id, {})
        file_path = test.get('file_path', '')

        # Derive module from file_path
        # e.g. ".../test_repository/agent/test_langgraph_agent.py"
        #       -> "agent.test_langgraph_agent"
        path_parts = Path(file_path).parts
        try:
            repo_idx     = next(
                i for i, p in enumerate(path_parts) if p == 'test_repository'
            )
            module_parts = path_parts[repo_idx + 1:]
            module       = '.'.join(p.replace('.py', '') for p in module_parts)
        except StopIteration:
            module = Path(file_path).stem

        # markers from JSONB — may be list, string, or None
        markers = meta.get('markers') or []
        if isinstance(markers, str):
            try:
                markers = json.loads(markers)
            except Exception:
                markers = []

        merged.append({
            'test_id':     test_id,
            'method_name': test.get('method_name', ''),
            'class_name':  test.get('class_name', ''),
            'test_type':   test.get('test_type', 'unit'),
            'file_path':   file_path,
            'module':      module,
            'description': meta.get('description', ''),
            'markers':     markers,
            'is_async':    meta.get('is_async', False),
            'functions_tested': function_map.get(test_id, []),  # NEW: Function mappings
            'line_number': test.get('line_number'),  # Include line number from registry
            'language':    test.get('language', 'python'),  # Include language from registry
        })

    return merged


def build_embedding_text(test: dict) -> str:
    """
    Build rich plain-text description of a test.
    Enhanced with function-level context for better semantic matching.
    """
    parts = []

    if test['method_name']:
        readable = test['method_name'].replace('test_', '').replace('_', ' ')
        parts.append(f"Test: {readable}")

    if test['class_name']:
        readable_class = test['class_name'].replace('Test', '').replace('_', ' ')
        parts.append(f"Component: {readable_class}")

    if test.get('description'):
        parts.append(f"Purpose: {test['description']}")

    if test.get('module'):
        parts.append(f"Module under test: {test['module']}")

    # NEW: Add function-level context (most important for semantic matching)
    functions_tested = test.get('functions_tested', [])
    if functions_tested:
        func_list = []
        for func_info in functions_tested[:10]:  # Limit to first 10 to avoid too long text
            module = func_info.get('module', '')
            func = func_info.get('function', '')
            if module and func:
                func_list.append(f"{module}.{func}")
            elif func:
                func_list.append(func)
        
        if func_list:
            parts.append(f"Tests functions: {', '.join(func_list)}")

    if test.get('test_type'):
        parts.append(f"Test type: {test['test_type']}")

    if test.get('markers') and isinstance(test['markers'], list):
        parts.append(f"Markers: {', '.join(str(m) for m in test['markers'])}")

    if test.get('is_async'):
        parts.append("Async test")

    return '\n'.join(parts).strip()


async def store_embeddings(tests: list, conn=None) -> tuple:
    """
    Generate and store embeddings for all tests in batches of 10.
    Uses LLMFactory.create_embedding_provider(settings) → OllamaClient.
    Stores embeddings in Pinecone.
    """
    settings = get_settings()
    llm      = LLMFactory.create_embedding_provider(settings)
    # llm is OllamaClient when EMBEDDING_PROVIDER=ollama

    # Get actual embedding dimensions from the provider
    embedding_dimensions = llm.get_embedding_dimensions()
    if embedding_dimensions is None:
        # Fallback to default if provider doesn't specify
        embedding_dimensions = 768
        print(f"Warning: Embedding provider did not specify dimensions, defaulting to {embedding_dimensions}")

    # Get test_repo_id from environment if available
    test_repo_id = os.getenv('TEST_REPO_ID', None)
    if test_repo_id:
        # Add test_repo_id to all test objects for Pinecone metadata
        for test in tests:
            test['test_repo_id'] = test_repo_id

    # Get the appropriate backend
    # Note: Backend initialization will use default EMBEDDING_DIMENSIONS (768)
    # We'll check and recreate with correct dimension below if needed
    backend = get_backend(conn)

    # Get provider name and model name dynamically
    provider_name = llm.provider_name
    embedding_model = llm.embedding_model if hasattr(llm, 'embedding_model') else "unknown"

    # Check Pinecone index dimension if using Pinecone and recreate if needed
    if VECTOR_BACKEND.lower() == "pinecone" and hasattr(backend, 'index'):
        try:
            index_stats = backend.index.describe_index_stats()
            index_dimension = index_stats.get('dimension')
            if index_dimension is not None and index_dimension != embedding_dimensions:
                print()
                print("=" * 80)
                print("DIMENSION MISMATCH DETECTED - Auto-Fixing...")
                print("=" * 80)
                print(f"  Pinecone Index Dimension: {index_dimension}")
                print(f"  Embedding Provider Dimension: {embedding_dimensions}")
                print()
                print(f"  The Pinecone index was created with dimension {index_dimension}, but")
                print(f"  the current embedding provider ({provider_name}) produces {embedding_dimensions}-dimensional vectors.")
                print()
                print("  Automatically recreating index with correct dimension...")
                print("  WARNING: This will delete all existing vectors in the index!")
                print("=" * 80)
                print()
                
                # Recreate the index with the correct dimension
                try:
                    backend._recreate_index_with_dimension(embedding_dimensions)
                    # Reinitialize the index connection
                    backend.index = backend.pc.Index(backend.index_name)
                    print()
                    print("=" * 80)
                    print("SUCCESS: Index recreated with correct dimension!")
                    print("=" * 80)
                    print(f"  New index dimension: {embedding_dimensions}")
                    print("  You can now proceed with embedding generation.")
                    print("=" * 80)
                    print()
                except Exception as recreate_error:
                    print()
                    print("=" * 80)
                    print("ERROR: Failed to recreate index!")
                    print("=" * 80)
                    print(f"  Error: {recreate_error}")
                    print()
                    print("  Manual steps required:")
                    print(f"  1. Delete the Pinecone index '{backend.index_name}' manually")
                    print(f"  2. Or recreate it with dimension {embedding_dimensions}")
                    print("=" * 80)
                    print()
                    raise
        except Exception as e:
            print(f"Warning: Could not check Pinecone index dimension: {e}")

    print_section(f"Generating embeddings for {len(tests)} tests...")
    print_item("Provider",   provider_name)
    print_item("Model",      embedding_model)
    print_item("Dimensions", str(embedding_dimensions))
    print_item("Batch size", str(BATCH_SIZE))
    print_item("Backend",    VECTOR_BACKEND)
    print()

    # Generate all embeddings first
    embeddings_list = []
    failed_generation = 0

    for i in range(0, len(tests), BATCH_SIZE):
        batch = tests[i: i + BATCH_SIZE]
        current = min(i + BATCH_SIZE, len(tests))
        pct     = round(current / len(tests) * 100, 1)
        print(f"  Generating embeddings: {current}/{len(tests)} ({pct}%)", end='\r')

        for test in batch:
            try:
                text     = build_embedding_text(test)
                request  = EmbeddingRequest(texts=[text])
                response = await llm.get_embeddings(request)

                # response.embeddings[0] is a Python list of 768 floats
                embedding = response.embeddings[0]
                embeddings_list.append(embedding)
            except asyncio.CancelledError:
                # Handle cancellation gracefully
                print(f"\n  [WARN] Embedding generation cancelled for {test['test_id']}")
                embeddings_list.append(None)
                failed_generation += 1
                # Re-raise to allow proper cleanup
                raise
            except KeyboardInterrupt:
                # Handle keyboard interrupt gracefully
                print(f"\n  [WARN] Embedding generation interrupted")
                embeddings_list.append(None)
                failed_generation += 1
                raise
            except Exception as e:
                print(f"\n  [WARN] Failed to generate embedding for {test['test_id']}: {e}")
                embeddings_list.append(None)  # Placeholder for failed embedding
                failed_generation += 1

    print()
    
    # Filter out tests with failed embeddings
    valid_tests = []
    valid_embeddings = []
    for test, embedding in zip(tests, embeddings_list):
        if embedding is not None:
            valid_tests.append(test)
            valid_embeddings.append(embedding)
    
    # Store embeddings using backend
    print(f"  Storing {len(valid_embeddings)} embeddings via {VECTOR_BACKEND} backend...")
    try:
        # When regenerating embeddings, delete existing ones for this repository first
        # This ensures we don't have stale embeddings if tests were removed
        delete_existing = bool(test_repo_id)  # Only delete if we have a test_repo_id
        stored, failed_storage = await backend.store_embeddings(valid_tests, valid_embeddings, delete_existing=delete_existing)
        
        total_failed = failed_generation + failed_storage
        
        if stored == 0 and len(valid_embeddings) > 0:
            print()
            print("=" * 80)
            print("WARNING: No embeddings were stored!")
            print("=" * 80)
            print(f"  Generated: {len(valid_embeddings)} embeddings")
            print(f"  Stored: {stored}")
            print(f"  Failed: {failed_storage}")
            print()
            print("  Possible causes:")
            print("  1. Dimension mismatch between embedding provider and Pinecone index")
            print(f"     - Embedding dimension: {embedding_dimensions}")
            print("     - Check Pinecone index dimension in console logs above")
            print("  2. Pinecone API errors (check logs for details)")
            print("  3. Network connectivity issues")
            print()
            print("  Solutions:")
            print(f"  1. Recreate Pinecone index with dimension {embedding_dimensions}")
            print(f"  2. Or switch to embedding provider that matches index dimension")
            print("=" * 80)
            print()
        
        print()
        return stored, total_failed
    except Exception as e:
        print()
        print("=" * 80)
        print("ERROR: Failed to store embeddings!")
        print("=" * 80)
        print(f"  Error: {e}")
        print()
        print("  This is likely due to a dimension mismatch.")
        print(f"  Embedding dimension: {embedding_dimensions}")
        print("  Check Pinecone index dimension in the error message above.")
        print("=" * 80)
        print()
        raise


async def main():
    print_header("Step 9: Generating Embeddings for Semantic Search")
    print()

    if not REGISTRY_JSON.exists():
        print("Error: 03_test_registry.json not found. Run Step 3 first.")
        return
    if not METADATA_JSON.exists():
        print("Error: 05_test_metadata.json not found. Run Step 5 first.")
        return
    
    # Function mappings are optional but recommended for better semantic matching
    if not FUNCTION_MAPPINGS_JSON.exists():
        print("Warning: 04b_function_calls.json not found. Function-level context will not be included.")
        print("  For better semantic matching, run: python test_analysis/04b_extract_function_calls.py")
        print()

    print_section("Loading test data...")
    tests = load_test_data()
    print_item("Tests loaded", len(tests))
    print()

    # Pinecone doesn't require a database connection
    stored, failed = await store_embeddings(tests, conn=None)

    print()
    print_header("Step 9 Complete!")
    print(f"Embeddings stored: {stored} | Failed: {failed}")
    print("Semantic search is now ready in git_diff_processor.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  [INFO] Embedding generation interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        print(f"\n  [ERROR] Fatal error in embedding generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
