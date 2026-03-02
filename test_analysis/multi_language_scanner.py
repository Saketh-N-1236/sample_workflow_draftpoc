"""
Multi-language test file scanner.

Scans projects with multiple programming languages and uses appropriate
parsers for each language to discover and analyze test files.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from parsers.registry import get_parser, initialize_registry, get_registry
from parsers.base import LanguageParser
from config.config_loader import load_language_configs, get_test_patterns, get_file_extensions, get_language_config
from test_analysis.language_detector import get_active_languages


def scan_multi_language(
    project_root: Path,
    test_directories: Optional[List[str]] = None,
    config_path: Path = None,
    exclude_dirs: Optional[List[str]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scan project for test files across multiple languages.
    
    Uses language detection to identify active languages, then scans
    for test files using language-specific patterns and parsers.
    
    Args:
        project_root: Root directory of the project
        test_directories: Optional list of test directory names to prioritize
        config_path: Optional path to language config YAML file
        exclude_dirs: Optional list of directory names to exclude
    
    Returns:
        Dictionary mapping language names to lists of test file info:
        {
            'python': [
                {
                    'file_path': Path(...),
                    'language': 'python',
                    'parser': PythonParser instance,
                    ...
                }
            ],
            'java': [...]
        }
    """
    # Initialize registry
    if config_path:
        initialize_registry(config_path)
        config = load_language_configs(config_path)
    else:
        initialize_registry()
        try:
            default_config_path = project_root / "config" / "language_configs.yaml"
            if default_config_path.exists():
                config = load_language_configs(default_config_path)
            else:
                config = {}
        except Exception:
            config = {}
    
    # Detect active languages
    active_languages = get_active_languages(project_root, config_path)
    
    if not active_languages:
        # Fallback to Python if no languages detected
        active_languages = ['python']
    
    # Default exclude directories
    if exclude_dirs is None:
        exclude_dirs = [
            '__pycache__', '.git', '.pytest_cache', 'node_modules',
            '.venv', 'venv', 'env', '.env', '.idea', '.vscode',
            'build', 'dist', '.mypy_cache', '.tox', 'htmlcov',
            'target', 'bin', 'obj', '.gradle', '.mvn'
        ]
    
    # Scan for each language
    results = defaultdict(list)
    
    for language in active_languages:
        # Get language config
        lang_config = get_language_config(config, language) if config else None
        
        if not lang_config:
            # Skip if no config (parser might not be available)
            continue
        
        # Get test patterns for this language
        test_patterns = get_test_patterns(config, language) if config else []
        file_extensions = get_file_extensions(config, language) if config else []
        
        # If no patterns, use default based on extensions
        if not test_patterns and file_extensions:
            # Default patterns: test_*.ext, *_test.ext
            for ext in file_extensions:
                ext_clean = ext.lstrip('.')
                test_patterns.extend([
                    f"test_*.{ext_clean}",
                    f"*_test.{ext_clean}"
                ])
        
        # Scan for test files
        test_files = _scan_language_tests(
            project_root,
            language,
            file_extensions,
            test_patterns,
            test_directories,
            exclude_dirs
        )
        
        # Get parser for each file and extract info
        for test_file in test_files:
            parser = get_parser(test_file)
            if parser:
                file_info = {
                    'file_path': test_file,
                    'language': language,
                    'parser': parser,
                    'extension': test_file.suffix
                }
                results[language].append(file_info)
    
    return dict(results)


def _scan_language_tests(
    project_root: Path,
    language: str,
    extensions: List[str],
    test_patterns: List[str],
    test_directories: Optional[List[str]],
    exclude_dirs: List[str]
) -> List[Path]:
    """
    Scan for test files for a specific language.
    
    Args:
        project_root: Root directory
        language: Language name
        extensions: File extensions for this language
        test_patterns: Test file name patterns
        test_directories: Optional test directory names
        exclude_dirs: Directories to exclude
    
    Returns:
        List of test file paths
    """
    import re
    
    test_files = []
    seen_files = set()
    
    # Build regex patterns from test patterns
    regex_patterns = []
    for pattern in test_patterns:
        # Convert glob pattern to regex
        regex = pattern.replace('.', r'\.').replace('*', '.*')
        regex_patterns.append(re.compile(regex, re.IGNORECASE))
    
    # Strategy 1: Scan by extension and match patterns
    for ext in extensions:
        for filepath in project_root.rglob(f'*{ext}'):
            # Skip excluded directories
            if any(excluded in filepath.parts for excluded in exclude_dirs):
                continue
            
            # Skip if already seen
            file_str = str(filepath.resolve())
            if file_str in seen_files:
                continue
            
            # Check if matches test pattern
            filename = filepath.name
            matches_pattern = False
            for regex in regex_patterns:
                if regex.match(filename):
                    matches_pattern = True
                    break
            
            # Also check if in test directory
            in_test_dir = False
            if test_directories:
                path_lower = str(filepath).lower()
                for test_dir in test_directories:
                    if f'/{test_dir}/' in path_lower or f'\\{test_dir}\\' in path_lower:
                        in_test_dir = True
                        break
            
            if matches_pattern or in_test_dir:
                test_files.append(filepath)
                seen_files.add(file_str)
    
    # Strategy 2: Explicitly check test directories
    if test_directories:
        for test_dir_name in test_directories:
            test_dir = project_root / test_dir_name
            if test_dir.exists() and test_dir.is_dir():
                for ext in extensions:
                    for filepath in test_dir.rglob(f'*{ext}'):
                        if any(excluded in filepath.parts for excluded in exclude_dirs):
                            continue
                        
                        file_str = str(filepath.resolve())
                        if file_str not in seen_files:
                            test_files.append(filepath)
                            seen_files.add(file_str)
    
    return sorted(test_files)


def get_test_files_by_language(
    project_root: Path,
    config_path: Path = None
) -> Dict[str, List[Path]]:
    """
    Get test files grouped by language.
    
    Convenience function that returns just the file paths grouped by language.
    
    Args:
        project_root: Root directory of the project
        config_path: Optional path to language config YAML file
    
    Returns:
        Dictionary mapping language names to lists of test file paths
    """
    results = scan_multi_language(project_root, config_path=config_path)
    
    # Extract just the file paths
    return {
        lang: [info['file_path'] for info in file_infos]
        for lang, file_infos in results.items()
    }
