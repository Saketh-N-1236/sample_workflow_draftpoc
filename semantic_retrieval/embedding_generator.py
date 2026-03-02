"""
Step 9: Generate Embeddings for Semantic Search

Reads:
  - test_analysis/outputs/03_test_registry.json
  - test_analysis/outputs/05_test_metadata.json

For each test, builds a rich text description, generates a 768-dim
embedding using Ollama nomic-embed-text, stores using configured backend:
  - ChromaDB (default): Stores in semantic_retrieval/chromadb_data/
  - pgvector: Stores in planon1.test_metadata.embedding (vector(768))

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
    VECTOR_BACKEND=chromadb  # or 'pgvector' if pgvector is installed
"""

import asyncio
import json
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

OUTPUT_DIR    = Path(__file__).parent.parent / "test_analysis" / "outputs"
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
    Stores embeddings using the configured vector backend (ChromaDB or pgvector).
    """
    settings = get_settings()
    llm      = LLMFactory.create_embedding_provider(settings)
    # llm is OllamaClient when EMBEDDING_PROVIDER=ollama

    # Get the appropriate backend
    backend = get_backend(conn)

    print_section(f"Generating embeddings for {len(tests)} tests...")
    print_item("Provider",   "Ollama")
    print_item("Model",      settings.ollama_embedding_model)
    print_item("Dimensions", "768")
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
    stored, failed_storage = await backend.store_embeddings(valid_tests, valid_embeddings)
    
    total_failed = failed_generation + failed_storage
    
    print()
    return stored, total_failed


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

    # Get connection (needed for pgvector backend, optional for ChromaDB)
    conn = get_connection() if VECTOR_BACKEND == 'pgvector' else None
    try:
        stored, failed = await store_embeddings(tests, conn)
    finally:
        if conn:
            conn.close()

    print()
    print_header("Step 9 Complete!")
    print(f"Embeddings stored: {stored} | Failed: {failed}")
    print("Semantic search is now ready in git_diff_processor.")


if __name__ == "__main__":
    asyncio.run(main())
