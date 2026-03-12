"""
Content summarization utilities for test code.

Implements priority-based extraction to create smart summaries of test content
that respect token limits while preserving the most important information.
"""

import re
from typing import List, Tuple


# Test content token limits per provider (approximate chars per token: ~4)
TEST_CONTENT_MAX_TOKENS = {
    'openai': 2000,   # ~8000 chars
    'ollama': 400,    # ~1600 chars
    'gemini': 1500    # ~6000 chars
}

# Pinecone metadata description max length
PINECONE_DESCRIPTION_MAX_CHARS = 1000


def extract_assertions(content: str) -> List[str]:
    """
    Extract all assertion statements from test content.
    
    Priority 1: Never truncate assertions as they are critical for understanding test behavior.
    """
    assertions = []
    
    # Python assertions
    patterns = [
        r'assert\s+[^\n]+',  # assert statements
        r'assert\s+[^\n]+\n',  # assert with newline
        r'self\.assert[A-Z]\w+\([^)]*\)',  # unittest assertions
        r'pytest\.raises\([^)]*\)',  # pytest.raises
        r'@pytest\.mark\.parametrize',  # parameterized test markers
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            assertion = match.group(0).strip()
            if assertion and assertion not in assertions:
                assertions.append(assertion)
    
    return assertions


def extract_function_calls(content: str, max_calls: int = 15) -> List[str]:
    """
    Extract function calls with arguments from test content.
    
    Priority 2: Keep first 15 function calls as they show what the test exercises.
    """
    function_calls = []
    
    # Pattern to match function calls: function_name(arg1, arg2, ...)
    # This is a simplified pattern - in practice, you might want more sophisticated parsing
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)'
    
    matches = re.finditer(pattern, content)
    for match in matches:
        call = match.group(0).strip()
        # Filter out common test framework calls
        if not any(fw in call.lower() for fw in ['def ', 'class ', 'import ', 'from ', 'if ', 'for ', 'while ']):
            if call and call not in function_calls:
                function_calls.append(call)
                if len(function_calls) >= max_calls:
                    break
    
    return function_calls


def extract_setup_code(content: str, max_chars: int = 500) -> str:
    """
    Extract setup/teardown logic from test content.
    
    Priority 3: Keep first 500 chars of setup code.
    """
    # Look for common setup patterns
    setup_patterns = [
        r'setUp\s*\([^)]*\)\s*:\s*.*?(?=\n\s*(?:def|class|@))',  # setUp method
        r'setUpClass\s*\([^)]*\)\s*:\s*.*?(?=\n\s*(?:def|class|@))',  # setUpClass
        r'@pytest\.fixture.*?\n.*?(?=\n\s*(?:def|class|@))',  # pytest fixtures
        r'with\s+[^:]+:.*?(?=\n\s*(?:def|class|@))',  # context managers
    ]
    
    setup_code = ''
    for pattern in setup_patterns:
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        for match in matches:
            setup_code += match.group(0) + '\n'
            if len(setup_code) >= max_chars:
                break
        if len(setup_code) >= max_chars:
            break
    
    # If no setup patterns found, take first few lines
    if not setup_code:
        lines = content.split('\n')[:10]
        setup_code = '\n'.join(lines)
    
    return setup_code[:max_chars]


def truncate_to_token_limit(text: str, provider: str = 'openai') -> str:
    """
    Truncate text to provider-specific token limit.
    
    Uses approximate token count (1 token ≈ 4 characters).
    """
    max_tokens = TEST_CONTENT_MAX_TOKENS.get(provider, 2000)
    max_chars = max_tokens * 4  # Approximate: 1 token ≈ 4 chars
    
    if len(text) <= max_chars:
        return text
    
    # Truncate at word boundary if possible
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')
    if last_space > max_chars * 0.9:  # If space is near the end
        truncated = truncated[:last_space]
    
    return truncated + '...'


def summarize_test_content(full_content: str, provider: str = 'openai') -> str:
    """
    Create priority-based summary of test content.
    
    Priority order:
    1. Assertions (all) - never truncate
    2. Function calls (first 15) - show what's tested
    3. Setup code (first 500 chars) - show context
    4. Remaining code (truncated if needed) - fill remaining space
    
    Args:
        full_content: Full test function body content
        provider: Embedding provider name ('openai', 'ollama', 'gemini')
    
    Returns:
        Summarized test content respecting token limits
    """
    if not full_content or not full_content.strip():
        return ''
    
    # Check if content is just a docstring (likely old format)
    # If it's short and doesn't contain code patterns, it's probably just a docstring
    if len(full_content) < 200 and not any(
        pattern in full_content for pattern in ['def ', 'assert ', 'self.', 'import ', '=']
    ):
        # Likely just a docstring, return as-is
        return full_content
    
    # Extract content after "--- Test Code ---" marker if present
    if '--- Test Code ---' in full_content:
        parts = full_content.split('--- Test Code ---', 1)
        docstring = parts[0].strip()
        test_code = parts[1].strip() if len(parts) > 1 else ''
    else:
        # Assume entire content is test code
        test_code = full_content
        docstring = ''
    
    # Priority 1: Extract all assertions
    assertions = extract_assertions(test_code)
    assertions_text = '\n'.join(assertions) if assertions else ''
    
    # Priority 2: Extract function calls (first 15)
    function_calls = extract_function_calls(test_code, max_calls=15)
    calls_text = '\n'.join(function_calls) if function_calls else ''
    
    # Priority 3: Extract setup code (first 500 chars)
    setup_text = extract_setup_code(test_code, max_chars=500)
    
    # Build summary with priority
    summary_parts = []
    
    if assertions_text:
        summary_parts.append(f"Assertions:\n{assertions_text}")
    
    if calls_text:
        summary_parts.append(f"Function calls:\n{calls_text}")
    
    if setup_text:
        summary_parts.append(f"Setup:\n{setup_text}")
    
    # Combine and truncate to token limit
    summary = '\n\n'.join(summary_parts)
    
    # If summary is empty, use original content (truncated)
    if not summary:
        summary = test_code
    
    # Truncate to provider-specific limit
    summary = truncate_to_token_limit(summary, provider)
    
    # Prepend docstring if exists
    if docstring:
        return f"{docstring}\n\n{summary}"
    
    return summary
