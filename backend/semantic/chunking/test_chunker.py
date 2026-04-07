"""
Test chunker for semantic retrieval.

Implements intelligent chunking strategies for large test content.
Chunks entire test files by method boundaries when possible.
Extracts test name and class/suite name per chunk for display in selection results.
"""

import re
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def extract_test_display_names(chunk_content: str, language: str = 'python') -> Dict[str, str]:
    """
    Extract method_name (test name) and class_name (suite/describe/class) from chunk content
    so semantic results can show meaningful names instead of N/A.

    Returns:
        Dict with 'method_name' and 'class_name' (both may be empty).
    """
    if not chunk_content or not chunk_content.strip():
        return {'method_name': '', 'class_name': ''}

    method_name = ''
    class_name = ''
    # Use first ~2000 chars to avoid scanning huge chunks
    head = chunk_content[:2000] if len(chunk_content) > 2000 else chunk_content

    if language in ('javascript', 'typescript'):
        # describe('SuiteName', ...) or describe("SuiteName"...) or describe(`SuiteName`...)
        describe_re = re.compile(
            r"(?:describe|context)\s*\(\s*['\"`]([^'\"`]+)['\"`]",
            re.IGNORECASE
        )
        # it('test name', ...) or test('test name', ...)
        it_re = re.compile(
            r"(?:it|test)\s*\(\s*['\"`]([^'\"`]+)['\"`]",
            re.IGNORECASE
        )
        describes = describe_re.findall(head)
        its = it_re.findall(head)
        if describes:
            class_name = describes[-1].strip()  # innermost describe
        if its:
            method_name = its[0].strip()  # first it/test in chunk
        if not method_name and describes:
            method_name = describes[-1].strip()

    elif language == 'python':
        # class TestXxx: or class TestXxx(
        class_re = re.compile(r"^\s*class\s+(Test\w+)\s*[:\(]", re.MULTILINE | re.IGNORECASE)
        # def test_xxx( or def test_xxx(
        def_re = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.MULTILINE)
        classes = class_re.findall(head)
        defs = def_re.findall(head)
        if classes:
            class_name = classes[-1]
        if defs:
            method_name = defs[0].replace('_', ' ')

    elif language == 'java':
        # @Test public void testXxx( or void testXxx(
        method_re = re.compile(r"(?:public\s+)?void\s+(test\w+)\s*\(", re.IGNORECASE)
        class_re = re.compile(r"^\s*(?:public\s+)?class\s+(\w+)\s*(?:\{|extends)", re.MULTILINE)
        methods = method_re.findall(head)
        classes = class_re.findall(head)
        if classes:
            class_name = classes[0]
        if methods:
            method_name = re.sub(r'([A-Z])', r' \1', methods[0]).strip().replace('test ', '')

    return {'method_name': method_name or '', 'class_name': class_name or ''}


def _find_method_boundaries(content: str, language: str = 'python') -> List[int]:
    """
    Find method/function boundaries in test content.
    
    Args:
        content: Test file content
        language: Programming language ('python', 'javascript', 'java')
    
    Returns:
        List of character positions where methods/functions start
    """
    boundaries = [0]  # Start of file
    
    if language == 'python':
        # Match: def test_*, def test*, @pytest.fixture, class Test*
        patterns = [
            r'^\s*def\s+test',  # def test_*
            r'^\s*class\s+Test',  # class Test*
            r'^\s*@pytest',  # @pytest decorators
        ]
    elif language in ('javascript', 'typescript'):
        # Match: describe(, it(, test(, beforeEach(, afterEach(
        patterns = [
            r'^\s*(describe|it|test|beforeEach|afterEach|beforeAll|afterAll)\s*\(',
        ]
    elif language == 'java':
        # Match: @Test, public void test*, @BeforeEach, @AfterEach
        patterns = [
            r'^\s*@Test',
            r'^\s*public\s+void\s+test',
            r'^\s*@BeforeEach',
            r'^\s*@AfterEach',
        ]
    else:
        # Generic: look for function/test keywords
        patterns = [
            r'^\s*(function|def|public\s+void)\s+test',
        ]
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                # Calculate character position
                char_pos = sum(len(l) + 1 for l in lines[:i])  # +1 for newline
                if char_pos not in boundaries:
                    boundaries.append(char_pos)
                break
    
    boundaries.append(len(content))  # End of file
    return sorted(set(boundaries))


def _find_test_only_boundaries(content: str, language: str = 'python') -> List[int]:
    """
    Find character positions where individual test cases start (one chunk per test).
    Used for test-based chunking: each chunk = one it(), one test_*, or one @Test method.
    """
    boundaries = [0]

    if language == 'python':
        patterns = [r'^\s*def\s+test\w*\s*\(']
    elif language in ('javascript', 'typescript'):
        patterns = [r'^\s*(it|test)\s*\(']
    elif language == 'java':
        patterns = [r'^\s*@Test', r'^\s*public\s+void\s+test\w+\s*\(']
    else:
        patterns = [r'^\s*def\s+test', r'^\s*(it|test)\s*\(']

    lines = content.split('\n')
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                char_pos = sum(len(l) + 1 for l in lines[:i])
                if char_pos not in boundaries:
                    boundaries.append(char_pos)
                break

    boundaries.append(len(content))
    return sorted(set(boundaries))


def chunk_file_by_tests(
    test_content: str,
    language: str = 'python',
    max_chunk_size: int = 8000,
) -> List[Dict[str, Any]]:
    """
    Chunk test file by individual tests: one chunk per test (it/test, def test_*, @Test method).
    Stores content with the test so the vector DB has test-level granularity (test + content).

    Returns same chunk shape as chunk_test_intelligently. Returns [] if no test boundaries
    are found so caller can fall back to chunk_test_intelligently.
    """
    if not test_content or not test_content.strip():
        return []

    boundaries = _find_test_only_boundaries(test_content, language)
    # Need at least one test start (boundaries = [0, test1_start, ..., len])
    if len(boundaries) <= 2:
        return []

    chunks = []
    # Emit one chunk per test: from each test start to the next (skip index 0 so we don't chunk imports/describe)
    for i in range(1, len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        chunk_content = test_content[start:end]
        if not chunk_content.strip():
            continue
        names = extract_test_display_names(chunk_content, language)
        start_line = test_content[:start].count('\n') + 1
        end_line = test_content[:end].count('\n') + 1
        chunks.append({
            'content': chunk_content,
            'chunk_index': len(chunks),
            'start_line': start_line,
            'end_line': end_line,
            'metadata': {
                'chunk_type': 'test',
                'size': len(chunk_content),
                'test_index': i - 1,
            },
            'method_name': names['method_name'],
            'class_name': names['class_name'],
        })

    return chunks


def chunk_test_intelligently(
    test_content: str, 
    max_chunk_size: int = 2000,
    language: str = 'python',
    prefer_method_boundaries: bool = True
) -> List[Dict[str, Any]]:
    """
    Chunk test content intelligently by test method boundaries.
    
    Attempts to chunk at method/function boundaries when possible,
    falls back to character-based splitting if needed.
    
    Args:
        test_content: Full test file content
        max_chunk_size: Maximum characters per chunk
        language: Programming language for boundary detection
        prefer_method_boundaries: Whether to prefer method boundaries
    
    Returns:
        List of chunks with metadata
    """
    if not test_content:
        return []
    
    # If content is small enough, return single chunk
    if len(test_content) <= max_chunk_size:
        names = extract_test_display_names(test_content, language)
        return [{
            'content': test_content,
            'chunk_index': 0,
            'start_line': 1,
            'end_line': test_content.count('\n') + 1,
            'metadata': {'chunk_type': 'single', 'size': len(test_content)},
            'method_name': names['method_name'],
            'class_name': names['class_name']
        }]

    chunks = []
    
    if prefer_method_boundaries:
        # Try to chunk at method boundaries
        boundaries = _find_method_boundaries(test_content, language)
        
        if len(boundaries) > 2:  # More than just start and end
            # Chunk by method boundaries
            chunk_index = 0
            for i in range(len(boundaries) - 1):
                start = boundaries[i]
                end = boundaries[i + 1]
                chunk_content = test_content[start:end]
                
                # If chunk is still too large, split it further
                if len(chunk_content) > max_chunk_size:
                    # Split this chunk into smaller pieces
                    sub_start = start
                    while sub_start < end:
                        sub_end = min(sub_start + max_chunk_size, end)
                        sub_chunk = test_content[sub_start:sub_end]
                        names = extract_test_display_names(sub_chunk, language)
                        chunks.append({
                            'content': sub_chunk,
                            'chunk_index': chunk_index,
                            'start_line': test_content[:sub_start].count('\n') + 1,
                            'end_line': test_content[:sub_end].count('\n') + 1,
                            'metadata': {
                                'chunk_type': 'method_boundary_split',
                                'size': len(sub_chunk),
                                'method_boundary': i < len(boundaries) - 2
                            },
                            'method_name': names['method_name'],
                            'class_name': names['class_name']
                        })
                        sub_start = sub_end
                        chunk_index += 1
                else:
                    names = extract_test_display_names(chunk_content, language)
                    chunks.append({
                        'content': chunk_content,
                        'chunk_index': chunk_index,
                        'start_line': test_content[:start].count('\n') + 1,
                        'end_line': test_content[:end].count('\n') + 1,
                        'metadata': {
                            'chunk_type': 'method_boundary',
                            'size': len(chunk_content),
                            'method_index': i
                        },
                        'method_name': names['method_name'],
                        'class_name': names['class_name']
                    })
                    chunk_index += 1

            if chunks:
                logger.debug(f"Chunked {len(chunks)} chunks using method boundaries")
                return chunks
    
    # Fallback: character-based splitting
    chunk_index = 0
    start = 0
    while start < len(test_content):
        end = min(start + max_chunk_size, len(test_content))
        
        # Try to break at line boundary
        if end < len(test_content):
            # Look for nearest newline
            line_break = test_content.rfind('\n', start, end)
            if line_break > start:
                end = line_break + 1
        
        chunk_content = test_content[start:end]
        names = extract_test_display_names(chunk_content, language)
        chunks.append({
            'content': chunk_content,
            'chunk_index': chunk_index,
            'start_line': test_content[:start].count('\n') + 1,
            'end_line': test_content[:end].count('\n') + 1,
            'metadata': {
                'chunk_type': 'character_split',
                'size': len(chunk_content)
            },
            'method_name': names['method_name'],
            'class_name': names['class_name']
        })
        start = end
        chunk_index += 1

    return chunks
