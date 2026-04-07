"""
Step 9: Generate Embeddings for Semantic Search (NEW APPROACH)

NEW APPROACH: Loads test files directly from test repository, chunks by tests,
and stores test + content in Pinecone.

This bypasses JSON files and database - works directly with test repository files.

Flow:
1. Load test files from repository (load_test_files_from_repo)
2. Chunk by tests: one chunk per test (it/test, def test_*, @Test) with its content (chunk_file_by_tests)
3. If no tests detected, fall back to method-boundary chunking (chunk_test_intelligently)
4. Generate embeddings for each chunk and store in Pinecone (content stored with test name/class)

Run ONCE after uploading test repository:
    python -m semantic.embedding_generation.embedding_generator

Or set TEST_REPO_PATH environment variable and run analysis pipeline.

Re-run only when new tests are added or test files change.
"""

import asyncio
import os
import sys
from pathlib import Path

# Same path setup pattern as other pipeline scripts
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(1, str(Path(__file__).parent.parent))

# Import config.settings BEFORE semantic.config to avoid shadowing
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

from semantic.backends import get_backend
from semantic.config import BATCH_SIZE, VECTOR_BACKEND
from semantic.ingestion.test_data_loader import (
    load_test_files_from_repo,
    load_tests_from_analysis,
)
from semantic.embedding_generation.text_builder import build_embedding_text
from semantic.chunking.test_chunker import (
    chunk_test_intelligently,
    chunk_file_by_tests,
)
from test_analysis.utils.output_formatter import print_header, print_section, print_item

import logging
logger = logging.getLogger(__name__)


async def store_embeddings(tests: list, conn=None) -> tuple:
    """
    Generate and store embeddings for all tests in batches of 10.
    Uses LLMFactory.create_embedding_provider(settings) → OllamaClient.
    Stores embeddings in Pinecone.
    """
    settings = get_settings()
    llm = LLMFactory.create_embedding_provider(settings)

    # Get actual embedding dimensions from the provider
    embedding_dimensions = llm.get_embedding_dimensions()
    if embedding_dimensions is None:
        embedding_dimensions = 768
        print(f"Warning: Embedding provider did not specify dimensions, defaulting to {embedding_dimensions}")

    # Get test_repo_id from environment if available
    test_repo_id = os.getenv('TEST_REPO_ID', None)
    if test_repo_id:
        for test in tests:
            test['test_repo_id'] = test_repo_id

    # Get the appropriate backend
    backend = get_backend(conn)

    # Get provider name and model name dynamically
    provider_name = llm.provider_name
    embedding_model = llm.embedding_model if hasattr(llm, 'embedding_model') else "unknown"
    embedding_provider = provider_name.lower()

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
                
                try:
                    backend._recreate_index_with_dimension(embedding_dimensions)
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

    print_section(f"Generating embeddings for {len(tests)} tests (with chunking for large tests)...")
    print_item("Provider", provider_name)
    print_item("Model", embedding_model)
    print_item("Dimensions", str(embedding_dimensions))
    print_item("Batch size", str(BATCH_SIZE))
    print_item("Backend", VECTOR_BACKEND)
    print_item("Chunking", "Enabled for tests > 2000 chars")
    print()

    # Generate all embeddings first (with chunking for large test files)
    embeddings_list = []
    test_chunks_list = []  # Store test chunks for multi-chunk tests
    failed_generation = 0
    total_chunks = 0
    
    # Prefer analysis-based tests (real test names + content from analyzers)
    is_analysis_based = any(test.get('is_analysis_based') for test in tests[:1] if tests)
    is_file_based = any(test.get('is_file_chunk') or test.get('content') for test in tests[:1] if tests) and not is_analysis_based

    if is_analysis_based:
        # One vector per test (or per chunk of long test); method_name/class_name from analyzer
        print(f"  [ANALYSIS] Using analyzer test names and content ({len(tests)} tests)")
        TEST_CHUNK_MAX = 8000
        for i, test in enumerate(tests):
            try:
                content = test.get('content', '')
                method_name = test.get('method_name', '')
                class_name = test.get('class_name', '')
                if not content and not method_name:
                    continue
                if len(content) > TEST_CHUNK_MAX and content:
                    chunks = chunk_test_intelligently(
                        content,
                        max_chunk_size=TEST_CHUNK_MAX,
                        language=test.get('language', 'python'),
                        prefer_method_boundaries=True,
                    )
                    for chunk in (chunks or [{'content': content, 'chunk_index': 0, 'total_chunks': 1}]):
                        chunk_test = test.copy()
                        chunk_test['content'] = chunk.get('content', content)
                        chunk_test['method_name'] = method_name
                        chunk_test['class_name'] = class_name
                        chunk_test['chunk_index'] = chunk.get('chunk_index', 0)
                        chunk_test['total_chunks'] = len(chunks) if chunks else 1
                        chunk_test['is_chunk'] = len(chunks or []) > 1
                        text = build_embedding_text(chunk_test, provider=embedding_provider)
                        request = EmbeddingRequest(texts=[text])
                        response = await llm.get_embeddings(request)
                        embedding = response.embeddings[0]
                        test_chunks_list.append(chunk_test)
                        embeddings_list.append(embedding)
                        total_chunks += 1
                else:
                    text = build_embedding_text(test, provider=embedding_provider)
                    request = EmbeddingRequest(texts=[text])
                    response = await llm.get_embeddings(request)
                    embedding = response.embeddings[0]
                    test_chunks_list.append(test)
                    embeddings_list.append(embedding)
                    total_chunks += 1
                if (i + 1) % 20 == 0 or i == len(tests) - 1:
                    pct = round((i + 1) / len(tests) * 100, 1)
                    print(f"  Analysis tests: {i + 1}/{len(tests)} ({pct}%) | Chunks: {total_chunks}", end='\r')
            except Exception as e:
                logger.warning(f"Failed to embed analysis test {test.get('test_id', '')}: {e}")
                embeddings_list.append(None)
                test_chunks_list.append(None)
                failed_generation += 1
    elif is_file_based:
        # Chunk by tests first (one vector per test + content); fallback to method-boundary chunking
        print(f"  [NEW] Chunking test repo by tests (one chunk per test), then storing in vector DB")
        MAX_CHUNK_SIZE = 2000  # For fallback chunking
        TEST_CHUNK_MAX = 8000  # Max size for a single-test chunk (test + content)

        for i, test_file in enumerate(tests):
            try:
                file_content = test_file.get('content', '')
                language = test_file.get('language', 'python')
                file_path = test_file.get('relative_path', test_file.get('file_path', ''))

                if not file_content:
                    logger.warning(f"Skipping empty file: {file_path}")
                    continue

                # Prefer test-based chunking: one chunk per test (it/test, def test_*, @Test) with content
                chunks = chunk_file_by_tests(
                    file_content,
                    language=language,
                    max_chunk_size=TEST_CHUNK_MAX,
                )
                if not chunks:
                    # Fallback: chunk by method boundaries or character split
                    chunks = chunk_test_intelligently(
                        file_content,
                        max_chunk_size=MAX_CHUNK_SIZE,
                        language=language,
                        prefer_method_boundaries=True,
                    )
                
                if chunks:
                    # Generate embedding for each chunk
                    for chunk in chunks:
                        chunk_test = test_file.copy()
                        chunk_test['content'] = chunk['content']
                        chunk_test['chunk_index'] = chunk['chunk_index']
                        chunk_test['total_chunks'] = len(chunks)
                        chunk_test['chunk_metadata'] = chunk.get('metadata', {})
                        chunk_test['start_line'] = chunk.get('start_line', 1)
                        chunk_test['end_line'] = chunk.get('end_line', 1)
                        chunk_test['is_chunk'] = True
                        chunk_test['original_file_id'] = test_file['test_id']
                        # Use chunk-extracted names so semantic results show test/class instead of N/A
                        chunk_test['method_name'] = chunk.get('method_name') or chunk_test.get('method_name') or ''
                        chunk_test['class_name'] = chunk.get('class_name') or chunk_test.get('class_name') or ''
                        
                        # Build embedding text from chunk
                        text = build_embedding_text(chunk_test, provider=embedding_provider)
                        request = EmbeddingRequest(texts=[text])
                        response = await llm.get_embeddings(request)
                        embedding = response.embeddings[0]
                        
                        test_chunks_list.append(chunk_test)
                        embeddings_list.append(embedding)
                        total_chunks += 1
                else:
                    # Fallback: single embedding for file
                    text = build_embedding_text(test_file, provider=embedding_provider)
                    request = EmbeddingRequest(texts=[text])
                    response = await llm.get_embeddings(request)
                    embedding = response.embeddings[0]
                    test_chunks_list.append(test_file)
                    embeddings_list.append(embedding)
                
                # Progress update
                if (i + 1) % 10 == 0 or i == len(tests) - 1:
                    pct = round((i + 1) / len(tests) * 100, 1)
                    print(f"  Processing files: {i + 1}/{len(tests)} ({pct}%) | Chunks: {total_chunks}", end='\r')
                    
            except Exception as e:
                logger.warning(f"Failed to process file {test_file.get('file_path', 'unknown')}: {e}")
                embeddings_list.append(None)
                test_chunks_list.append(None)
                failed_generation += 1
    else:
        # LEGACY APPROACH: Chunk individual test descriptions
        print(f"  [LEGACY] Using description-based chunking approach")
        MAX_CONTENT_LENGTH = 2000
        
        for i in range(0, len(tests), BATCH_SIZE):
            batch = tests[i: i + BATCH_SIZE]
            current = min(i + BATCH_SIZE, len(tests))
            pct = round(current / len(tests) * 100, 1)
            print(f"  Generating embeddings: {current}/{len(tests)} ({pct}%) | Chunks: {total_chunks}", end='\r')

            for test in batch:
                try:
                    # Get test content for chunking
                    description = test.get('description', '')
                    test_content = description if description else ''
                    
                    # Check if test content is large enough to chunk
                    should_chunk = len(test_content) > MAX_CONTENT_LENGTH
                    
                    if should_chunk and test_content:
                        # Chunk the test content intelligently
                        chunks = chunk_test_intelligently(test_content, max_chunk_size=MAX_CONTENT_LENGTH)
                        
                        if chunks:
                            # Generate embedding for each chunk
                            for chunk_idx, chunk in enumerate(chunks):
                                # Build embedding text with chunk content
                                chunk_test = test.copy()
                                chunk_test['description'] = chunk['content']
                                chunk_test['chunk_index'] = chunk['chunk_index']
                                chunk_test['chunk_metadata'] = chunk.get('metadata', {})
                                chunk_test['method_name'] = chunk.get('method_name') or chunk_test.get('method_name') or ''
                                chunk_test['class_name'] = chunk.get('class_name') or chunk_test.get('class_name') or ''

                                text = build_embedding_text(chunk_test, provider=embedding_provider)
                                request = EmbeddingRequest(texts=[text])
                                response = await llm.get_embeddings(request)
                                embedding = response.embeddings[0]
                                
                                # Store chunk with test metadata
                                chunk_test['original_test_id'] = test['test_id']
                                chunk_test['is_chunk'] = True
                                chunk_test['total_chunks'] = len(chunks)
                                
                                test_chunks_list.append(chunk_test)
                                embeddings_list.append(embedding)
                                total_chunks += 1
                        else:
                            # Fallback to single embedding if chunking fails
                            text = build_embedding_text(test, provider=embedding_provider)
                            request = EmbeddingRequest(texts=[text])
                            response = await llm.get_embeddings(request)
                            embedding = response.embeddings[0]
                            embeddings_list.append(embedding)
                            test_chunks_list.append(test)
                    else:
                        # Single embedding for small tests
                        text = build_embedding_text(test, provider=embedding_provider)
                        request = EmbeddingRequest(texts=[text])
                        response = await llm.get_embeddings(request)
                        embedding = response.embeddings[0]
                        embeddings_list.append(embedding)
                        test_chunks_list.append(test)
                        
                except asyncio.CancelledError:
                    print(f"\n  [WARN] Embedding generation cancelled for {test.get('test_id', 'unknown')}")
                    embeddings_list.append(None)
                    test_chunks_list.append(None)
                    failed_generation += 1
                    raise
                except KeyboardInterrupt:
                    print(f"\n  [WARN] Embedding generation interrupted")
                    embeddings_list.append(None)
                    test_chunks_list.append(None)
                    failed_generation += 1
                    raise
                except Exception as e:
                    print(f"\n  [WARN] Failed to generate embedding for {test.get('test_id', 'unknown')}: {e}")
                    embeddings_list.append(None)
                    test_chunks_list.append(None)
                    failed_generation += 1

    print()
    
    # Filter out tests with failed embeddings
    valid_tests = []
    valid_embeddings = []
    for test_chunk, embedding in zip(test_chunks_list, embeddings_list):
        if embedding is not None and test_chunk is not None:
            valid_tests.append(test_chunk)
            valid_embeddings.append(embedding)
    
    # Store embeddings using backend
    print(f"  Storing {len(valid_embeddings)} embeddings via {VECTOR_BACKEND} backend...")
    try:
        delete_existing = bool(test_repo_id)
        stored, failed_storage = await backend.store_embeddings(
            valid_tests, valid_embeddings, delete_existing=delete_existing
        )
        
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
        return stored, total_failed, total_chunks
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
        # Return with chunk count even on error
        return 0, len(valid_embeddings), total_chunks


async def main():
    print_header("Step 9: Generating Embeddings for Semantic Search (NEW APPROACH)")
    print()

    # Load test files directly from repository (TEST_REPO_PATH required)
    test_repo_path = os.getenv('TEST_REPO_PATH')
    if not test_repo_path:
        print()
        print("ERROR: TEST_REPO_PATH is required. Set it to the extracted test repository directory path.")
        print("Example: export TEST_REPO_PATH=/path/to/backend/data/test_repo_data/<hash>")
        print()
        return

    print_section("Loading tests (analyzer names + content preferred)...")
    test_repo_id_env = os.getenv('TEST_REPO_ID', '')
    try:
        test_repo_path_obj = Path(test_repo_path)
        if not test_repo_path_obj.exists():
            raise FileNotFoundError(f"Test repository path does not exist: {test_repo_path}")

        # Prefer analysis pipeline so Pinecone gets real test names (e.g. "describe > it" for JS)
        tests = load_tests_from_analysis(test_repo_path_obj, repo_id=test_repo_id_env)
        if tests:
            print_item("Source", "analysis (analyzer test names + content)")
            print_item("Tests loaded", len(tests))
        else:
            tests = load_test_files_from_repo(test_repo_path_obj)
            print_item("Source", "file scan (fallback)")
            print_item("Test files loaded", len(tests))
        print_item("Repository path", str(test_repo_path_obj))
        print()

        if not tests:
            print("Warning: No test files found in repository.")
            print("Make sure the repository contains test files matching patterns:")
            print("  Python: test_*.py, *_test.py")
            print("  JavaScript: *.test.js, *.spec.js, *.test.ts, *.spec.ts")
            print("  Java: *Test.java, *Tests.java, *TestCase.java")
            return

    except Exception as e:
        print(f"Error loading test files: {e}")
        import traceback
        traceback.print_exc()
        return

    # Pinecone doesn't require a database connection
    stored, failed, chunks_created = await store_embeddings(tests, conn=None)

    print()
    print_header("Step 9 Complete!")
    print(f"Embeddings stored: {stored} | Failed: {failed}")
    if chunks_created and chunks_created > len(tests):
        print(f"Total chunks created: {chunks_created} (from {len(tests)} files)")
    print("Semantic search is now ready in git_diff_processor.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  [INFO] Embedding generation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n  [ERROR] Fatal error in embedding generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
