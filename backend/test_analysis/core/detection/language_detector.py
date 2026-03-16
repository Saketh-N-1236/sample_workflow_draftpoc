"""
Language detection module.

Detects programming languages present in a repository by scanning file extensions.
"""

from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Language detection by file extension
LANGUAGE_BY_EXTENSION = {
    '.py':   'python',
    '.java': 'java',
    '.js':   'javascript',
    '.ts':   'typescript',
    '.tsx':  'typescript',
    '.jsx':  'javascript',
    '.kt':   'kotlin',
    '.rb':   'ruby',
    '.cs':   'csharp',
    '.go':   'go',
    '.scala': 'scala',
    '.clj':  'clojure',
    '.hs':   'haskell',
    '.rs':   'rust',
    '.cpp':  'cpp',
    '.c':    'c',
    '.php':  'php',
    '.swift': 'swift',
    '.dart': 'dart',
}

# Exclude directories
EXCLUDE_DIRS = {
    'target', 'build', '.git', '.gradle', '.mvn',
    'node_modules', '.idea', '.vscode', 'bin', 'out',
    '__pycache__', '.pytest_cache', '.venv', 'venv',
    'dist', '.next', '.nuxt', '.cache', 'coverage',
}


class LanguageDetectionResult:
    """Result of language detection."""
    
    def __init__(self, languages: Dict[str, int], files_by_language: Dict[str, List[Path]]):
        """
        Initialize detection result.
        
        Args:
            languages: Dictionary mapping language name to file count
            files_by_language: Dictionary mapping language name to list of file paths
        """
        self.languages = languages
        self.files_by_language = files_by_language
    
    def get_languages(self) -> List[str]:
        """Get list of detected languages."""
        return list(self.languages.keys())
    
    def get_file_count(self, language: str) -> int:
        """Get file count for a language."""
        return self.languages.get(language, 0)
    
    def get_files(self, language: str) -> List[Path]:
        """Get files for a language."""
        return self.files_by_language.get(language, [])
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'languages': self.languages,
            'files_by_language': {
                lang: [str(f) for f in files]
                for lang, files in self.files_by_language.items()
            }
        }


def detect_language_from_extension(filepath: Path) -> str:
    """
    Detect language from file extension.
    
    Args:
        filepath: Path to file
        
    Returns:
        Language name or 'unknown' if not recognized
    """
    ext = filepath.suffix.lower()
    return LANGUAGE_BY_EXTENSION.get(ext, 'unknown')


def should_scan_file(filepath: Path) -> bool:
    """
    Check if a file should be scanned (not in excluded directories).
    
    Args:
        filepath: Path to file
        
    Returns:
        True if file should be scanned, False otherwise
    """
    parts = set(filepath.parts)
    return not any(excluded in parts for excluded in EXCLUDE_DIRS)


def detect_languages(repo_path: Path, include_test_files_only: bool = False) -> LanguageDetectionResult:
    """
    Detect all programming languages present in a repository.
    
    Args:
        repo_path: Path to repository root
        include_test_files_only: If True, only scan test files (by naming patterns)
        
    Returns:
        LanguageDetectionResult with detected languages and file counts
    """
    repo_path = Path(repo_path).resolve()
    
    if not repo_path.exists():
        logger.warning(f"Repository path does not exist: {repo_path}")
        return LanguageDetectionResult({}, {})
    
    languages: Dict[str, int] = defaultdict(int)
    files_by_language: Dict[str, List[Path]] = defaultdict(list)
    
    # Test file patterns for filtering
    test_patterns = {
        '.py': [r'test_.*\.py$', r'.*_test\.py$'],
        '.java': [r'.*Test\.java$', r'.*Tests\.java$'],
        '.js': [r'.*\.test\.js$', r'.*\.spec\.js$'],
        '.ts': [r'.*\.test\.ts$', r'.*\.spec\.ts$'],
    }
    
    import re
    compiled_patterns = {
        ext: [re.compile(p) for p in patterns]
        for ext, patterns in test_patterns.items()
    }
    
    def is_test_file(filepath: Path) -> bool:
        """Check if file matches test patterns."""
        if not include_test_files_only:
            return True
        ext = filepath.suffix.lower()
        if ext not in compiled_patterns:
            return True  # Include unknown extensions
        name = filepath.name
        return any(pattern.match(name) for pattern in compiled_patterns[ext])
    
    # Scan repository
    scanned = 0
    for filepath in repo_path.rglob('*'):
        if not filepath.is_file():
            continue
        
        if not should_scan_file(filepath):
            continue
        
        if not is_test_file(filepath):
            continue
        
        language = detect_language_from_extension(filepath)
        if language != 'unknown':
            languages[language] += 1
            files_by_language[language].append(filepath)
            scanned += 1
    
    logger.info(f"Scanned {scanned} files, detected {len(languages)} languages: {dict(languages)}")
    
    return LanguageDetectionResult(dict(languages), dict(files_by_language))
