"""
Detection report module.

Combines language and framework detection into a comprehensive report.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .language_detector import detect_languages, LanguageDetectionResult
from .framework_detector import detect_frameworks, FrameworkDetectionResult
import logging

logger = logging.getLogger(__name__)


@dataclass
class DetectionReport:
    """Comprehensive detection report combining language and framework detection."""
    
    languages: Dict[str, int] = field(default_factory=dict)
    files_by_language: Dict[str, List[str]] = field(default_factory=dict)
    frameworks_by_language: Dict[str, List[str]] = field(default_factory=dict)
    framework_confidence: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    def get_languages(self) -> List[str]:
        """Get list of detected languages."""
        return list(self.languages.keys())
    
    def get_frameworks(self, language: str) -> List[str]:
        """Get detected frameworks for a language."""
        return self.frameworks_by_language.get(language, [])
    
    def has_language(self, language: str) -> bool:
        """Check if a language was detected."""
        return language in self.languages
    
    def has_framework(self, language: str, framework: str) -> bool:
        """Check if a framework was detected for a language."""
        return framework in self.frameworks_by_language.get(language, [])
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'languages': self.languages,
            'files_by_language': self.files_by_language,
            'frameworks_by_language': self.frameworks_by_language,
            'framework_confidence': self.framework_confidence,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DetectionReport':
        """Create from dictionary."""
        return cls(
            languages=data.get('languages', {}),
            files_by_language=data.get('files_by_language', {}),
            frameworks_by_language=data.get('frameworks_by_language', {}),
            framework_confidence=data.get('framework_confidence', {}),
        )


def create_detection_report(
    repo_path: Path,
    include_test_files_only: bool = False,
    framework_sample_size: int = 50
) -> DetectionReport:
    """
    Create a comprehensive detection report for a repository.
    
    Args:
        repo_path: Path to repository root
        include_test_files_only: If True, only scan test files
        framework_sample_size: Maximum files to sample for framework detection
        
    Returns:
        DetectionReport with languages and frameworks detected
    """
    logger.info(f"Creating detection report for repository: {repo_path}")
    
    # Step 1: Detect languages
    lang_result = detect_languages(repo_path, include_test_files_only=include_test_files_only)
    
    if not lang_result.languages:
        logger.warning(f"No languages detected in {repo_path}")
        return DetectionReport()
    
    # Step 2: Detect frameworks
    fw_result = detect_frameworks(
        repo_path,
        lang_result.languages,
        lang_result.files_by_language,
        sample_size=framework_sample_size
    )
    
    # Step 3: Combine results
    report = DetectionReport(
        languages=lang_result.languages,
        files_by_language={
            lang: [str(f) for f in files]
            for lang, files in lang_result.files_by_language.items()
        },
        frameworks_by_language=fw_result.frameworks_by_language,
        framework_confidence=fw_result.confidence,
    )
    
    logger.info(f"Detection complete: {len(report.languages)} languages, "
                f"{sum(len(fws) for fws in report.frameworks_by_language.values())} frameworks")
    
    return report
