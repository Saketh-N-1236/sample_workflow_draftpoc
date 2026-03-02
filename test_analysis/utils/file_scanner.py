"""
File scanning utilities for discovering test files.

This module provides functions to:
- Recursively scan directories for test files
- Match test file patterns (configurable per language)
- Extract file metadata (size, line count)
- Categorize files by directory structure

Now supports multi-language test discovery through configuration.
"""

from pathlib import Path
from typing import List, Dict, Optional
import re
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from config.config_loader import load_language_configs, get_test_patterns, get_file_extensions
    from parsers.registry import detect_language, initialize_registry
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# Default test file patterns (Python, for backward compatibility)
DEFAULT_TEST_FILE_PATTERNS = [
    r'test_.*\.py$',      # test_*.py
    r'.*_test\.py$',      # *_test.py
    r'.*Test\.py$',       # *Test.py (Java-style, but sometimes used in Python)
]

# Global cache for language configs
_language_config_cache = None
_config_path_cache = None


def _load_language_configs(config_path: Path = None) -> Optional[Dict]:
    """Load language configs (cached)."""
    global _language_config_cache, _config_path_cache
    
    if not CONFIG_AVAILABLE:
        return None
    
    # Use cached config if path matches
    if config_path and config_path == _config_path_cache and _language_config_cache:
        return _language_config_cache
    
    try:
        if config_path is None:
            default_path = project_root / "config" / "language_configs.yaml"
            if default_path.exists():
                config_path = default_path
            else:
                return None
        
        if config_path.exists():
            config = load_language_configs(config_path)
            _language_config_cache = config
            _config_path_cache = config_path
            return config
    except Exception:
        pass
    
    return None


def is_test_file(filepath: Path, config_path: Path = None) -> bool:
    """
    Check if a file matches test file patterns.
    
    Now supports multi-language patterns from configuration.
    
    Args:
        filepath: Path to the file to check
        config_path: Optional path to language config YAML file
    
    Returns:
        True if the file matches test patterns, False otherwise
    
    Example:
        >>> is_test_file(Path("test_agent.py"))
        True
        >>> is_test_file(Path("agent.py"))
        False
    """
    filename = filepath.name
    
    # Try to use language-specific patterns
    if CONFIG_AVAILABLE:
        config = _load_language_configs(config_path)
        if config:
            # Initialize registry if needed
            try:
                initialize_registry(config_path)
            except Exception:
                pass
            
            # Detect language
            language = detect_language(filepath)
            if language:
                # Get test patterns for this language
                patterns = get_test_patterns(config, language)
                if patterns:
                    # Convert glob patterns to regex
                    for pattern in patterns:
                        regex = pattern.replace('.', r'\.').replace('*', '.*')
                        if re.match(regex, filename, re.IGNORECASE):
                            return True
    
    # Fallback to default Python patterns
    for pattern in DEFAULT_TEST_FILE_PATTERNS:
        if re.match(pattern, filename, re.IGNORECASE):
            return True
    
    return False


def scan_directory(root_dir: Path, exclude_dirs: Optional[List[str]] = None) -> List[Path]:
    """
    Recursively scan a directory for test files.
    
    Enhanced version that finds ALL test files using multiple strategies.
    
    Args:
        root_dir: Root directory to scan
        exclude_dirs: List of directory names to exclude (e.g., ['__pycache__', '.git'])
    
    Returns:
        List of Path objects for all test files found
    
    Example:
        >>> files = scan_directory(Path("test_repository"))
        >>> len(files)
        15
    """
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', '.git', '.pytest_cache', 'node_modules', '.venv', 'venv', 'env', '.env']
    
    test_files = []
    seen_files = set()  # Track files to avoid duplicates
    
    # Strategy 1: Standard test file patterns (test_*.py, *_test.py)
    for item in root_dir.rglob('*.py'):
        # Skip excluded directories
        if any(excluded in item.parts for excluded in exclude_dirs):
            continue
        
        # Skip .pyc files
        if item.suffix == '.pyc':
            continue
        
        # Check if it's a test file (using language-aware detection)
        if is_test_file(item, config_path):
            file_str = str(item.resolve())
            if file_str not in seen_files:
                seen_files.add(file_str)
                test_files.append(item)
    
    # Strategy 2: Check common test directories explicitly (even if not matching patterns)
    common_test_dirs = ['unit', 'integration', 'e2e', 'tests', 'test', 'end_to_end', 'endtoend']
    for dir_name in common_test_dirs:
        test_dir = root_dir / dir_name
        if test_dir.exists() and test_dir.is_dir():
            for ext in extensions_to_scan:
                for item in test_dir.rglob(f'*{ext}'):
                    # Skip excluded directories
                    if any(excluded in item.parts for excluded in exclude_dirs):
                        continue
                    
                    # Skip .pyc files
                    if item.suffix == '.pyc':
                        continue
                    
                    # Check if it's a test file (using language-aware detection)
                    if is_test_file(item, config_path):
                        file_str = str(item.resolve())
                        if file_str not in seen_files:
                            seen_files.add(file_str)
                            test_files.append(item)
    
    # Strategy 3: Look for files in test/test directories even if they don't match patterns
    # This catches files that might be tests but don't follow naming conventions
    for ext in extensions_to_scan:
        for item in root_dir.rglob(f'*{ext}'):
            if any(excluded in item.parts for excluded in exclude_dirs):
                continue
            
            if item.suffix == '.pyc':
                continue
            
            # If file is in a test directory, include it even if name doesn't match pattern
            # But still check if it's a test file using language-aware detection
            path_str = str(item).lower()
            if any(test_dir in path_str for test_dir in ['/test/', '/tests/', '\\test\\', '\\tests\\']):
                if is_test_file(item, config_path):
                    file_str = str(item.resolve())
                    if file_str not in seen_files:
                        seen_files.add(file_str)
                        test_files.append(item)
    
    return sorted(test_files)  # Return sorted list for consistency


def scan_directory_comprehensive(root_dir: Path, exclude_dirs: Optional[List[str]] = None, config_path: Path = None) -> List[Path]:
    """
    Comprehensive test file scanner that finds ALL test files.
    
    This is an alias for scan_directory (which is now enhanced).
    Kept for backward compatibility and clarity.
    
    Args:
        root_dir: Root directory to scan
        exclude_dirs: List of directory names to exclude
    
    Returns:
        List of Path objects for all test files found
    """
    return scan_directory(root_dir, exclude_dirs, config_path)


def get_file_metadata(filepath: Path) -> Dict[str, any]:
    """
    Extract metadata from a file.
    
    Args:
        filepath: Path to the file
    
    Returns:
        Dictionary with file metadata:
        - path: Relative path as string
        - absolute_path: Absolute path as string
        - size_bytes: File size in bytes
        - line_count: Number of lines in file
        - directory: Directory name (e.g., 'unit', 'integration')
    
    Example:
        >>> metadata = get_file_metadata(Path("test_repository/unit/test_agent.py"))
        >>> metadata['line_count']
        127
    """
    try:
        # Read file to count lines
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            line_count = len(lines)
        
        # Get file size
        size_bytes = filepath.stat().st_size
        
        # Determine directory category
        directory = _categorize_directory(filepath)
        
        return {
            "path": str(filepath),
            "absolute_path": str(filepath.absolute()),
            "size_bytes": size_bytes,
            "line_count": line_count,
            "directory": directory
        }
    except Exception as e:
        # Return minimal metadata if file can't be read
        return {
            "path": str(filepath),
            "absolute_path": str(filepath.absolute()),
            "size_bytes": 0,
            "line_count": 0,
            "directory": "unknown",
            "error": str(e)
        }


def _categorize_directory(filepath: Path) -> str:
    """
    Categorize a test file by its directory structure.
    
    Enhanced version with better detection for integration/e2e tests.
    
    Args:
        filepath: Path to the test file
    
    Returns:
        Category string: 'unit', 'integration', 'e2e', or 'other'
    
    Example:
        >>> _categorize_directory(Path("test_repository/unit/test_agent.py"))
        'unit'
    """
    parts = filepath.parts
    path_str = str(filepath).lower()
    
    # Check for e2e/end-to-end first (most specific)
    if 'e2e' in path_str or 'end_to_end' in path_str or 'endtoend' in path_str or 'end-to-end' in path_str:
        return 'e2e'
    
    # Check for integration
    if 'integration' in path_str:
        return 'integration'
    
    # Check for unit
    if 'unit' in path_str:
        return 'unit'
    
    # Check parent directory name
    if len(parts) > 1:
        parent_dir = parts[-2].lower()
        if parent_dir in ['e2e', 'end_to_end', 'endtoend', 'end-to-end']:
            return 'e2e'
        elif parent_dir == 'integration':
            return 'integration'
        elif parent_dir == 'unit':
            return 'unit'
    
    # Default to unit if in test_repository or tests directory
    if 'test_repository' in path_str or 'tests' in path_str:
        return 'unit'  # Default fallback
    
    return 'other'


def group_files_by_category(files: List[Path]) -> Dict[str, List[Path]]:
    """
    Group test files by their category (unit, integration, e2e, other).
    
    Args:
        files: List of test file paths
    
    Returns:
        Dictionary mapping category to list of files
    
    Example:
        >>> files = [Path("test_repository/unit/test_a.py"), Path("test_repository/integration/test_b.py")]
        >>> grouped = group_files_by_category(files)
        >>> len(grouped['unit'])
        1
    """
    grouped = {
        'unit': [],
        'integration': [],
        'e2e': [],
        'other': []
    }
    
    for filepath in files:
        category = _categorize_directory(filepath)
        grouped[category].append(filepath)
    
    return grouped
