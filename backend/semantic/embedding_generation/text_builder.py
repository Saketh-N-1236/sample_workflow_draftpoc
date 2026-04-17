"""
Text builder for embedding generation.

Builds rich text descriptions from test data for embedding.
"""

from semantic.chunking.content_summarizer import (
    summarize_test_content,
    PINECONE_DESCRIPTION_MAX_CHARS
)


def build_embedding_text(test: dict, provider: str = 'openai') -> str:
    """
    Build rich plain-text description for embedding.
    
    Works with:
    - ANALYSIS: Analyzer-based tests (method_name + content from RepoAnalyzer)
    - File chunks (content from test files directly)
    - LEGACY: Test descriptions (from JSON/database)
    
    Args:
        test: Test dictionary with metadata (file chunk or test description)
        provider: Embedding provider name ('openai', 'ollama', 'gemini')
    
    Returns:
        Rich text description for embedding
    """
    parts = []

    # ANALYSIS-BASED: Real test name + test body (from language analyzers)
    if test.get('is_analysis_based'):
        # Strong identifiers first
        _method = test.get('method_name') or ''
        _class  = test.get('class_name') or ''
        _file   = test.get('test_file_path') or test.get('file_path') or test.get('relative_path') or ''
        id_parts = []
        if _class:
            id_parts.append(f"Class: {_class}")
        if _method:
            id_parts.append(f"Method: {_method}")
        if _file:
            id_parts.append(f"File: {_file}")
        if id_parts:
            parts.append("Identifiers: " + " | ".join(id_parts))

        if _method:
            parts.append(f"Test: {_method}")
        if _class:
            parts.append(f"Component: {_class}")
        if test.get('language') and test['language'] != 'unknown':
            parts.append(f"Language: {test['language']}")
        content = test.get('content', '')
        if content:
            if len(content) > 6000:
                summary = summarize_test_content(content, provider=provider)
                parts.append(f"Test code: {summary}" if summary else f"Test code: {content[:6000]}...")
            else:
                parts.append(f"Test code: {content}")
        if test.get('total_chunks', 1) > 1:
            parts.append(f"Chunk {test.get('chunk_index', 0) + 1} of {test['total_chunks']}")
        embedding_text = '\n'.join(parts).strip()
        if content and len(content) > PINECONE_DESCRIPTION_MAX_CHARS:
            s = summarize_test_content(content, provider=provider)
            if s:
                test['test_content_summary'] = s[:PINECONE_DESCRIPTION_MAX_CHARS]
        return embedding_text

    # NEW APPROACH: Handle file chunks
    if test.get('is_file_chunk') or test.get('content'):
        # File-based chunking approach
        file_path = test.get('relative_path') or test.get('file_path', '')
        file_name = test.get('file_name', '')
        module = test.get('module', '')
        language = test.get('language', 'unknown')
        chunk_content = test.get('content', '')
        chunk_index = test.get('chunk_index', 0)
        total_chunks = test.get('total_chunks', 1)
        method_name = test.get('method_name') or ''
        class_name = test.get('class_name') or ''
        
        # Strong identifiers first
        id_parts = []
        if class_name:
            id_parts.append(f"Class: {class_name}")
        if method_name:
            id_parts.append(f"Method: {method_name}")
        if file_path:
            id_parts.append(f"File: {file_path}")
        if id_parts:
            parts.append("Identifiers: " + " | ".join(id_parts))

        # File metadata
        if file_name:
            parts.append(f"Test file: {file_name}")
        
        if module:
            parts.append(f"Module: {module}")
        
        if language != 'unknown':
            parts.append(f"Language: {language}")
        
        # Chunk information
        if total_chunks > 1:
            parts.append(f"Chunk {chunk_index + 1} of {total_chunks}")
        
        # Content summary (for large chunks)
        if chunk_content:
            if len(chunk_content) > 500:
                # Summarize large chunks
                content_summary = summarize_test_content(chunk_content, provider=provider)
                if content_summary:
                    parts.append(f"Test code: {content_summary}")
                else:
                    # Fallback: use first 500 chars
                    parts.append(f"Test code: {chunk_content[:500]}...")
            else:
                # Use full content for small chunks
                parts.append(f"Test code: {chunk_content}")
        
        embedding_text = '\n'.join(parts).strip()
        
        # Store summary for Pinecone metadata
        if chunk_content and len(chunk_content) > PINECONE_DESCRIPTION_MAX_CHARS:
            summary = summarize_test_content(chunk_content, provider=provider)
            if summary:
                test['test_content_summary'] = summary[:PINECONE_DESCRIPTION_MAX_CHARS]
        
        return embedding_text
    
    # LEGACY APPROACH: Handle test descriptions (from JSON/database)
    _method = test.get('method_name') or ''
    _class  = test.get('class_name') or ''
    _file   = test.get('test_file_path') or test.get('file_path') or test.get('relative_path') or ''
    id_parts = []
    if _class:
        id_parts.append(f"Class: {_class}")
    if _method:
        id_parts.append(f"Method: {_method}")
    if _file:
        id_parts.append(f"File: {_file}")
    if id_parts:
        parts.append("Identifiers: " + " | ".join(id_parts))

    if _method:
        readable = _method.replace('test_', '').replace('_', ' ')
        parts.append(f"Test: {readable}")

    if _class:
        readable_class = _class.replace('Test', '').replace('_', ' ')
        parts.append(f"Component: {readable_class}")

    # Check if description contains test content (vs just docstring)
    description = test.get('description', '')
    if description:
        # Check if description contains test content (has "--- Test Code ---" marker or is long)
        if '--- Test Code ---' in description or len(description) > 200:
            # Likely contains test content (not just docstring)
            # Generate smart summary
            content_summary = summarize_test_content(description, provider=provider)
            if content_summary:
                parts.append(f"Test code: {content_summary}")
        else:
            # Just docstring
            parts.append(f"Purpose: {description}")

    if test.get('module'):
        parts.append(f"Module under test: {test['module']}")

    # Add function-level context (most important for semantic matching)
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

    embedding_text = '\n'.join(parts).strip()
    
    # Store the content summary for Pinecone metadata
    if description and ('--- Test Code ---' in description or len(description) > 200):
        test['test_content_summary'] = summarize_test_content(description, provider=provider)
        # Truncate for Pinecone metadata (first 1000 chars)
        if test['test_content_summary']:
            test['test_content_summary'] = test['test_content_summary'][:PINECONE_DESCRIPTION_MAX_CHARS]
    
    return embedding_text
