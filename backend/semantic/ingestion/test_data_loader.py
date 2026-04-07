"""
Test data loader for semantic retrieval.

Provides:
- load_test_files_from_repo(): load test files directly from a repository path for chunking.
- load_tests_from_analysis(): load tests from RepoAnalyzer (analyzer test names + content) for embedding.
"""

import logging
import hashlib
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


def load_tests_from_analysis(test_repo_path: Path, repo_id: str = "") -> List[Dict]:
    """
    Load tests from the analysis pipeline (RepoAnalyzer) so embeddings use
    language-specific test names (e.g. "describe > it" for JS) and per-test content.

    Use this when analysis has already run or can run; prefer over load_test_files_from_repo
    so Pinecone stores the real test name and related content for better retrieval.

    Args:
        test_repo_path: Path to the test repository directory.
        repo_id: Optional test_repo_id (for Pinecone namespace / deletion).

    Returns:
        List of test dicts with test_id, method_name (full_name), class_name (describe),
        content (test body), file_path, language, etc. Empty list if analysis fails or no tests.
    """
    try:
        from test_analysis.engine.repo_analyzer import RepoAnalyzer
    except ImportError:
        logger.debug("load_tests_from_analysis: test_analysis not available")
        return []

    if not test_repo_path.exists() or not test_repo_path.is_dir():
        return []

    analyzer = RepoAnalyzer()
    result = analyzer.analyze(test_repo_path, repo_id=repo_id or "")
    if not result.all_tests:
        return []

    out = []
    for t in result.all_tests:
        out.append({
            "test_id": t.id,
            "method_name": t.full_name,
            "class_name": t.describe or "",
            "content": t.content or "",
            "file_path": t.file,
            "relative_path": str(Path(t.file).name) if t.file else "",
            "language": t.language,
            "line_number": t.line_number,
            "test_repo_id": result.repo_id or repo_id,
            "description": t.description or t.full_name,
            "is_analysis_based": True,
        })
    logger.info(f"[INGESTION] Loaded {len(out)} tests from analysis (analyzer names + content)")
    return out

# Test file patterns by language (matching test_analysis plugins)
TEST_FILE_PATTERNS = {
    'python': ['test_*.py', '*_test.py'],
    'javascript': ['*.test.js', '*.test.ts', '*.test.jsx', '*.test.tsx',
                    '*.spec.js', '*.spec.ts', '*.spec.jsx', '*.spec.tsx'],
    'java': ['*Test.java', '*Tests.java', '*TestCase.java'],
    'typescript': ['*.test.ts', '*.test.tsx', '*.spec.ts', '*.spec.tsx'],
}

# Exclude directories (same as language_detector)
EXCLUDE_DIRS = {
    'target', 'build', '.git', '.gradle', '.mvn',
    'node_modules', '.idea', '.vscode', 'bin', 'out',
    '__pycache__', '.pytest_cache', '.venv', 'venv',
    'dist', '.next', '.nuxt', '.cache', 'coverage',
}


def load_test_files_from_repo(test_repo_path: Path) -> List[Dict]:
    """
    Load test files directly from test repository (NEW APPROACH).
    
    Scans the repository for test files, reads their content, and prepares
    them for chunking and embedding generation.
    
    This is the NEW approach that bypasses JSON files and database,
    working directly with test repository files.
    
    Args:
        test_repo_path: Path to the test repository directory
    
    Returns:
        List of test file dictionaries with content and metadata
    """
    if not test_repo_path.exists():
        raise FileNotFoundError(f"Test repository path does not exist: {test_repo_path}")
    
    if not test_repo_path.is_dir():
        raise ValueError(f"Test repository path must be a directory: {test_repo_path}")
    
    logger.info(f"[INGESTION] Scanning test repository: {test_repo_path}")
    
    test_files = []
    test_repo_path = test_repo_path.resolve()
    
    # Scan for test files using language-specific patterns
    for language, patterns in TEST_FILE_PATTERNS.items():
        for pattern in patterns:
            # Use glob to find matching files
            for test_file in test_repo_path.rglob(pattern):
                # Skip excluded directories
                if any(excluded in test_file.parts for excluded in EXCLUDE_DIRS):
                    continue
                
                # Skip if not a file
                if not test_file.is_file():
                    continue
                
                try:
                    # Read file content
                    with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Generate unique ID from file path
                    file_id = hashlib.sha256(str(test_file.relative_to(test_repo_path)).encode()).hexdigest()[:16]
                    
                    # Determine relative path
                    relative_path = str(test_file.relative_to(test_repo_path))
                    
                    # Extract basic metadata from file path
                    file_name = test_file.name
                    file_stem = test_file.stem
                    
                    # Derive module from path
                    path_parts = test_file.relative_to(test_repo_path).parts
                    module_parts = [p.replace('.py', '').replace('.js', '').replace('.ts', '') 
                                   for p in path_parts[:-1]]  # Exclude filename
                    module = '.'.join(module_parts) if module_parts else file_stem
                    
                    test_files.append({
                        'test_id': f"file_{file_id}",
                        'file_path': str(test_file),
                        'relative_path': relative_path,
                        'file_name': file_name,
                        'file_stem': file_stem,
                        'module': module,
                        'language': language,
                        'content': content,
                        'content_length': len(content),
                        'line_count': content.count('\n') + 1,
                        'is_file_chunk': True,  # Mark as file-level (will be chunked later)
                    })
                    
                except Exception as e:
                    logger.warning(f"[INGESTION] Failed to read test file {test_file}: {e}")
                    continue
    
    logger.info(f"[INGESTION] Found {len(test_files)} test files in repository")
    return test_files
