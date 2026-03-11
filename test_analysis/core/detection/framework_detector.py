"""
Framework detection module.

Detects test frameworks present in a repository by analyzing imports and annotations.
"""

from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)

# Framework detection patterns
FRAMEWORK_IMPORT_PATTERNS = {
    # Java frameworks
    'junit5': [
        r'import\s+org\.junit\.jupiter',
        r'import\s+org\.junit\.jupiter\.api',
    ],
    'junit4': [
        r'import\s+org\.junit\.(?!jupiter)',
        r'import\s+junit\.framework',
    ],
    'junit3': [
        r'import\s+junit\.framework',
    ],
    'testng': [
        r'import\s+org\.testng',
    ],
    'mockito': [
        r'import\s+org\.mockito',
    ],
    'spring': [
        r'import\s+org\.springframework\.test',
        r'import\s+org\.springframework\.boot\.test',
    ],
    # Python frameworks
    'pytest': [
        r'import\s+pytest',
        r'from\s+pytest',
    ],
    'unittest': [
        r'import\s+unittest',
        r'from\s+unittest',
    ],
    'nose': [
        r'import\s+nose',
        r'from\s+nose',
    ],
    # JavaScript frameworks
    'jest': [
        r'import.*from\s+["\']jest["\']',
        r'require\s*\(\s*["\']jest["\']',
    ],
    'mocha': [
        r'import.*from\s+["\']mocha["\']',
        r'require\s*\(\s*["\']mocha["\']',
    ],
    'jasmine': [
        r'import.*from\s+["\']jasmine["\']',
        r'require\s*\(\s*["\']jasmine["\']',
    ],
    'vitest': [
        r'import.*from\s+["\']vitest["\']',
        r'require\s*\(\s*["\']vitest["\']',
    ],
}

# Framework annotation patterns
FRAMEWORK_ANNOTATION_PATTERNS = {
    'junit5': [
        r'@Test\b',
        r'@ParameterizedTest',
        r'@ExtendWith',
        r'@SpringBootTest',
    ],
    'junit4': [
        r'@RunWith',
        r'@org\.junit\.Test',
    ],
    'testng': [
        r'@org\.testng\.annotations\.Test',
        r'@Test\s*\(',
    ],
    'pytest': [
        r'@pytest\.fixture',
        r'@pytest\.mark',
    ],
}

# Language-specific framework mapping
LANGUAGE_FRAMEWORKS = {
    'java': ['junit5', 'junit4', 'junit3', 'testng', 'mockito', 'spring'],
    'python': ['pytest', 'unittest', 'nose'],
    'javascript': ['jest', 'mocha', 'jasmine', 'vitest'],
    'typescript': ['jest', 'mocha', 'jasmine', 'vitest'],
}


class FrameworkDetectionResult:
    """Result of framework detection."""
    
    def __init__(self, frameworks_by_language: Dict[str, List[str]], confidence: Dict[str, Dict[str, str]]):
        """
        Initialize detection result.
        
        Args:
            frameworks_by_language: Dictionary mapping language to list of detected frameworks
            confidence: Dictionary mapping language to framework confidence levels
        """
        self.frameworks_by_language = frameworks_by_language
        self.confidence = confidence
    
    def get_frameworks(self, language: str) -> List[str]:
        """Get detected frameworks for a language."""
        return self.frameworks_by_language.get(language, [])
    
    def get_confidence(self, language: str, framework: str) -> str:
        """Get confidence level for a framework."""
        return self.confidence.get(language, {}).get(framework, 'low')
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'frameworks_by_language': self.frameworks_by_language,
            'confidence': self.confidence,
        }


def detect_frameworks_in_file(filepath: Path, language: str) -> Dict[str, int]:
    """
    Detect frameworks in a single file.
    
    Args:
        filepath: Path to file
        language: Language of the file
        
    Returns:
        Dictionary mapping framework name to vote count
    """
    try:
        content = filepath.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        logger.debug(f"Cannot read {filepath}: {e}")
        return {}
    
    votes: Dict[str, int] = defaultdict(int)
    
    # Check import patterns
    for framework, patterns in FRAMEWORK_IMPORT_PATTERNS.items():
        # Only check frameworks relevant to this language
        if language not in LANGUAGE_FRAMEWORKS:
            continue
        if framework not in LANGUAGE_FRAMEWORKS[language]:
            continue
        
        for pattern in patterns:
            if re.search(pattern, content, re.MULTILINE):
                votes[framework] += 2  # Imports are strong indicators
                break
    
    # Check annotation patterns (mainly for Java)
    if language in ['java', 'kotlin']:
        for framework, patterns in FRAMEWORK_ANNOTATION_PATTERNS.items():
            if framework not in LANGUAGE_FRAMEWORKS.get(language, []):
                continue
            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE):
                    votes[framework] += 3  # Annotations are very strong indicators
                    break
    
    return dict(votes)


def detect_frameworks(
    repo_path: Path,
    languages: Dict[str, int],
    files_by_language: Dict[str, List[Path]],
    sample_size: int = 50
) -> FrameworkDetectionResult:
    """
    Detect test frameworks present in a repository.
    
    Args:
        repo_path: Path to repository root
        languages: Dictionary mapping language to file count (from language detection)
        files_by_language: Dictionary mapping language to list of file paths
        sample_size: Maximum number of files to sample per language
        
    Returns:
        FrameworkDetectionResult with detected frameworks per language
    """
    frameworks_by_language: Dict[str, List[str]] = defaultdict(list)
    confidence: Dict[str, Dict[str, str]] = defaultdict(dict)
    
    for language, file_count in languages.items():
        if language == 'unknown':
            continue
        
        files = files_by_language.get(language, [])
        if not files:
            continue
        
        # Sample files if too many
        sample_files = files[:sample_size] if len(files) > sample_size else files
        
        # Collect votes from all files
        all_votes: Dict[str, int] = defaultdict(int)
        for filepath in sample_files:
            file_votes = detect_frameworks_in_file(filepath, language)
            for framework, vote_count in file_votes.items():
                all_votes[framework] += vote_count
        
        # Determine frameworks (frameworks with votes >= 3)
        detected = [
            fw for fw, votes in sorted(all_votes.items(), key=lambda x: -x[1])
            if votes >= 3
        ]
        
        if detected:
            frameworks_by_language[language] = detected
            # Set confidence based on vote counts
            for fw in detected:
                votes = all_votes[fw]
                if votes >= 10:
                    conf = 'high'
                elif votes >= 5:
                    conf = 'medium'
                else:
                    conf = 'low'
                confidence[language][fw] = conf
        
        logger.info(f"Language {language}: detected frameworks {detected} (votes: {dict(all_votes)})")
    
    return FrameworkDetectionResult(dict(frameworks_by_language), dict(confidence))
