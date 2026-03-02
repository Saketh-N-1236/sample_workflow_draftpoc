"""
Language detection for multi-language projects.

Automatically detects which programming languages are present in a project
by scanning file extensions and analyzing project structure.
"""

from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter
from parsers.registry import initialize_registry, detect_language, get_registry
from config.config_loader import load_language_configs, get_language_config


def detect_languages(
    project_root: Path,
    config_path: Path = None,
    min_confidence: float = 0.01
) -> Dict[str, float]:
    """
    Detect languages in project by scanning file extensions.
    
    Scans the project directory for source files and maps their extensions
    to languages using the parser registry. Returns a confidence score
    (percentage of files) for each detected language.
    
    Args:
        project_root: Root directory of the project to scan
        config_path: Optional path to language config YAML file
        min_confidence: Minimum confidence threshold (0.01 = 1% of files)
    
    Returns:
        Dictionary mapping language names to confidence scores (0.0 to 1.0)
        Example: {'python': 0.75, 'java': 0.25}
    
    Example:
        >>> languages = detect_languages(Path("/project"))
        >>> print(languages)
        {'python': 0.75, 'java': 0.25}
    """
    # Initialize registry if config provided
    if config_path:
        initialize_registry(config_path)
    else:
        # Use default initialization
        initialize_registry()
    
    # Count file extensions
    extensions = Counter()
    total_files = 0
    
    # Common directories to exclude
    exclude_dirs = {
        '__pycache__', '.git', '.pytest_cache', 'node_modules',
        '.venv', 'venv', 'env', '.env', '.idea', '.vscode',
        'build', 'dist', '.mypy_cache', '.tox', 'htmlcov',
        'target', 'bin', 'obj', '.gradle'
    }
    
    # Scan for source files
    for filepath in project_root.rglob('*'):
        if filepath.is_file():
            # Skip excluded directories
            if any(excluded in filepath.parts for excluded in exclude_dirs):
                continue
            
            ext = filepath.suffix.lower()
            if ext:  # Has extension
                extensions[ext] += 1
                total_files += 1
    
    if total_files == 0:
        return {}
    
    # Map extensions to languages
    language_counts = Counter()
    registry = get_registry()
    
    for ext, count in extensions.items():
        # Try to detect language for this extension
        # Create a dummy file path to test
        dummy_path = project_root / f"dummy{ext}"
        language = detect_language(dummy_path)
        
        if language:
            language_counts[language] += count
    
    # Calculate confidence scores (percentage of files)
    result = {}
    for lang, count in language_counts.items():
        confidence = count / total_files if total_files > 0 else 0.0
        if confidence >= min_confidence:
            result[lang] = round(confidence, 3)
    
    # Sort by confidence (descending)
    return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))


def get_active_languages(
    project_root: Path,
    config_path: Path = None,
    min_confidence: float = 0.05
) -> List[str]:
    """
    Get list of active languages in project (above confidence threshold).
    
    Args:
        project_root: Root directory of the project
        config_path: Optional path to language config YAML file
        min_confidence: Minimum confidence threshold (default: 5%)
    
    Returns:
        List of language names, sorted by confidence (descending)
    
    Example:
        >>> languages = get_active_languages(Path("/project"))
        >>> print(languages)
        ['python', 'java']
    """
    detected = detect_languages(project_root, config_path, min_confidence)
    return list(detected.keys())


def get_language_statistics(
    project_root: Path,
    config_path: Path = None
) -> Dict[str, any]:
    """
    Get detailed statistics about languages in the project.
    
    Args:
        project_root: Root directory of the project
        config_path: Optional path to language config YAML file
    
    Returns:
        Dictionary with:
        - 'languages': Dict of language -> confidence
        - 'total_files': Total number of source files scanned
        - 'file_counts': Dict of extension -> count
        - 'active_languages': List of languages above threshold
    """
    # Initialize registry
    if config_path:
        initialize_registry(config_path)
    else:
        initialize_registry()
    
    # Count files by extension
    extensions = Counter()
    total_files = 0
    
    exclude_dirs = {
        '__pycache__', '.git', '.pytest_cache', 'node_modules',
        '.venv', 'venv', 'env', '.env', '.idea', '.vscode',
        'build', 'dist', '.mypy_cache', '.tox', 'htmlcov',
        'target', 'bin', 'obj', '.gradle'
    }
    
    for filepath in project_root.rglob('*'):
        if filepath.is_file():
            if any(excluded in filepath.parts for excluded in exclude_dirs):
                continue
            
            ext = filepath.suffix.lower()
            if ext:
                extensions[ext] += 1
                total_files += 1
    
    # Map to languages
    language_counts = Counter()
    registry = get_registry()
    
    for ext, count in extensions.items():
        dummy_path = project_root / f"dummy{ext}"
        language = detect_language(dummy_path)
        if language:
            language_counts[language] += count
    
    # Calculate confidences
    languages = {}
    for lang, count in language_counts.items():
        confidence = count / total_files if total_files > 0 else 0.0
        languages[lang] = round(confidence, 3)
    
    languages = dict(sorted(languages.items(), key=lambda x: x[1], reverse=True))
    active_languages = [lang for lang, conf in languages.items() if conf >= 0.05]
    
    return {
        'languages': languages,
        'total_files': total_files,
        'file_counts': dict(extensions),
        'active_languages': active_languages
    }
