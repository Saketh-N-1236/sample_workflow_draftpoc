"""
Semantic search functions for test selection using vector embeddings.
"""

from typing import List, Dict, Any, Optional
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest
from semantic_retrieval.backends import get_backend
from semantic_retrieval.config import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_MAX_RESULTS,
    SEMANTIC_THRESHOLD_STRICT,
    SEMANTIC_THRESHOLD_MODERATE,
    SEMANTIC_THRESHOLD_LENIENT,
    MIN_RESULTS_PER_TIER
)


def build_rich_change_description(
    changed_functions: list,
    file_changes: Optional[List[Dict]] = None
) -> str:
    """
    Build a rich, contextual description of code changes for semantic search.
    
    Includes:
    - File paths and class context
    - Related functions in the same file
    - Module-level context
    - Change type (new file, modified, etc.)
    
    Args:
        changed_functions: List of {'module': str, 'function': str}
        file_changes: Optional list of file change dictionaries from parse_git_diff
    
    Returns:
        Rich description string for embedding
    """
    if not changed_functions:
        return ""
    
    # Group functions by module
    by_module = {}
    for cf in changed_functions:
        module = cf.get('module', '')
        func = cf.get('function', '')
        if module not in by_module:
            by_module[module] = []
        by_module[module].append(func)
    
    # Build rich description
    parts = []
    
    # Add module-level context
    if len(by_module) == 1:
        module = list(by_module.keys())[0]
        functions = by_module[module]
        parts.append(f"Changed in module: {module}")
        parts.append(f"Changed functions: {', '.join(f'{f}()' for f in functions)}")
        
        # Try to extract file path and class from module
        if file_changes:
            for file_change in file_changes:
                file_path = file_change.get('file', '')
                if file_path.endswith('.py'):
                    # Try to match module to file
                    module_path = module.replace('.', '/') + '.py'
                    if module_path in file_path or file_path.endswith(module_path):
                        parts.append(f"File: {file_path}")
                        
                        # Extract class names from changed classes
                        changed_classes = file_change.get('changed_classes', [])
                        if changed_classes:
                            parts.append(f"Classes: {', '.join(changed_classes)}")
                        
                        # Add change status
                        status = file_change.get('status', 'modified')
                        if status == 'added':
                            parts.append("Status: New file")
                        break
    else:
        # Multiple modules
        parts.append("Changed across multiple modules:")
        for module, functions in by_module.items():
            parts.append(f"  - {module}: {', '.join(f'{f}()' for f in functions)}")
    
    # Add related context
    if len(changed_functions) > 1:
        parts.append(f"Total functions changed: {len(changed_functions)}")
    
    return ". ".join(parts) + "."


async def find_tests_semantic(
    conn,
    changed_functions: list,
    file_changes: Optional[List[Dict]] = None,
    similarity_threshold: Optional[float] = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    use_adaptive_thresholds: bool = True
) -> list:
    """
    Semantic search layer — finds tests by meaning, not name.

    Runs as Strategy 4 inside find_affected_tests().
    Only adds tests NOT already found by strategies 0-3.

    Uses the configured vector backend (ChromaDB or pgvector) for search.

    Args:
        conn: Database connection
        changed_functions: List of dicts from search_queries['changed_functions']:
          [{'module': 'agent.langgraph_agent', 'function': 'initialize'}, ...]
        file_changes: Optional list of file change dictionaries for rich context
        similarity_threshold: Optional fixed threshold (if None, uses adaptive)
        max_results: Maximum number of results to return
        use_adaptive_thresholds: If True, tries multiple thresholds with fallback

    Returns:
        List of test dicts with confidence_score already set (max 60).
        match_type will be 'semantic' for deduplication.

    Uses Ollama nomic-embed-text (768 dims).
    Semantic scores capped at 60 so they NEVER outrank exact matches.
    """
    if not changed_functions:
        return []

    # Build rich description of what changed
    change_description = build_rich_change_description(changed_functions, file_changes)
    
    if not change_description:
        return []

    # Get query embedding via Ollama
    settings = get_settings()
    llm = LLMFactory.create_embedding_provider(settings)
    response = await llm.get_embeddings(
        EmbeddingRequest(texts=[change_description])
    )
    query_embedding = response.embeddings[0]

    # Get the appropriate backend
    backend = get_backend(conn)
    
    # Use adaptive thresholds if enabled
    # Remove limit by using a very high max_results value
    effective_max_results = max(max_results, 10000) if max_results > 0 else 10000
    
    if use_adaptive_thresholds and similarity_threshold is None:
        # Try strict threshold first
        results = await backend.search_similar(
            query_embedding,
            SEMANTIC_THRESHOLD_STRICT,
            effective_max_results
        )
        
        # If not enough results, try moderate
        if len(results) < MIN_RESULTS_PER_TIER:
            moderate_results = await backend.search_similar(
                query_embedding,
                SEMANTIC_THRESHOLD_MODERATE,
                effective_max_results
            )
            # Combine and deduplicate (prefer higher similarity)
            seen_ids = {r.get('test_id') for r in results}
            for r in moderate_results:
                if r.get('test_id') not in seen_ids:
                    results.append(r)
        
        # If still not enough, try lenient
        if len(results) < MIN_RESULTS_PER_TIER:
            lenient_results = await backend.search_similar(
                query_embedding,
                SEMANTIC_THRESHOLD_LENIENT,
                effective_max_results
            )
            # Combine and deduplicate
            seen_ids = {r.get('test_id') for r in results}
            for r in lenient_results:
                if r.get('test_id') not in seen_ids:
                    results.append(r)
    else:
        # Use fixed threshold
        threshold = similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD
        results = await backend.search_similar(
            query_embedding,
            threshold,
            effective_max_results
        )

    return results


async def find_tests_semantic_multi_query(
    conn,
    changed_functions: list,
    file_changes: Optional[List[Dict]] = None,
    max_results: int = DEFAULT_MAX_RESULTS
) -> list:
    """
    Multi-query semantic search - generates multiple query variations and combines results.
    
    Creates queries from different perspectives:
    - Function-focused: "Function initialize in agent.langgraph_agent"
    - Class-focused: "Class LangGraphAgent in agent.langgraph_agent"
    - Module-focused: "Module agent.langgraph_agent"
    - Combined: Rich description with all context
    
    Args:
        conn: Database connection
        changed_functions: List of function change dicts
        file_changes: Optional file change information
        max_results: Maximum results per query
    
    Returns:
        Combined and deduplicated results, weighted by query type
    """
    if not changed_functions:
        return []
    
    settings = get_settings()
    llm = LLMFactory.create_embedding_provider(settings)
    backend = get_backend(conn)
    
    all_results = []
    seen_test_ids = set()
    
    # Query 1: Function-focused
    if changed_functions:
        func_query = "Functions: " + ", ".join(
            f"{cf['function']}() in {cf['module']}" 
            for cf in changed_functions[:5]  # Limit to first 5
        )
        func_response = await llm.get_embeddings(EmbeddingRequest(texts=[func_query]))
        func_embedding = func_response.embeddings[0]
        func_results = await backend.search_similar(
            func_embedding,
            SEMANTIC_THRESHOLD_LENIENT,
            max_results
        )
        # Weight function queries higher
        for r in func_results:
            if r.get('test_id') not in seen_test_ids:
                r['query_weight'] = 1.0
                all_results.append(r)
                seen_test_ids.add(r.get('test_id'))
    
    # Query 2: Module-focused
    if changed_functions:
        modules = list(set(cf['module'] for cf in changed_functions))
        module_query = "Modules: " + ", ".join(modules[:3])  # Limit to first 3 modules
        module_response = await llm.get_embeddings(EmbeddingRequest(texts=[module_query]))
        module_embedding = module_response.embeddings[0]
        module_results = await backend.search_similar(
            module_embedding,
            SEMANTIC_THRESHOLD_LENIENT,
            max_results
        )
        # Weight module queries lower
        for r in module_results:
            if r.get('test_id') not in seen_test_ids:
                r['query_weight'] = 0.7
                all_results.append(r)
                seen_test_ids.add(r.get('test_id'))
    
    # Query 3: Rich combined description (most important)
    rich_query = build_rich_change_description(changed_functions, file_changes)
    if rich_query:
        rich_response = await llm.get_embeddings(EmbeddingRequest(texts=[rich_query]))
        rich_embedding = rich_response.embeddings[0]
        rich_results = await backend.search_similar(
            rich_embedding,
            SEMANTIC_THRESHOLD_LENIENT,
            max_results
        )
        # Weight rich queries highest
        for r in rich_results:
            test_id = r.get('test_id')
            if test_id not in seen_test_ids:
                r['query_weight'] = 1.2
                all_results.append(r)
                seen_test_ids.add(test_id)
            else:
                # Boost existing result if found by rich query
                for existing in all_results:
                    if existing.get('test_id') == test_id:
                        existing['query_weight'] = max(existing.get('query_weight', 1.0), 1.2)
                        # Boost similarity score
                        existing['similarity'] = max(
                            existing.get('similarity', 0),
                            r.get('similarity', 0)
                        )
                        break
    
    # Sort by weighted similarity (similarity * query_weight)
    for r in all_results:
        r['weighted_similarity'] = r.get('similarity', 0) * r.get('query_weight', 1.0)
    
    all_results.sort(key=lambda x: x.get('weighted_similarity', 0), reverse=True)
    
    # Remove query_weight and weighted_similarity before returning
    for r in all_results:
        r.pop('query_weight', None)
        r.pop('weighted_similarity', None)
    
    return all_results[:max_results]
