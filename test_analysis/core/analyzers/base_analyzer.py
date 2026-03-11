"""
Base analyzer abstract class.

All language-specific analyzers must implement this interface.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class AnalyzerResult:
    """Result from an analyzer run."""
    
    language: str
    framework: str
    output_dir: Path
    summary: Dict = field(default_factory=dict)
    files_analyzed: int = 0
    tests_found: int = 0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'language': self.language,
            'framework': self.framework,
            'output_dir': str(self.output_dir),
            'summary': self.summary,
            'files_analyzed': self.files_analyzed,
            'tests_found': self.tests_found,
            'errors': self.errors,
        }


class BaseAnalyzer(ABC):
    """
    Base class for all language-specific analyzers.
    
    Each analyzer must:
    1. Implement analyze() to produce all 8 JSON output files
    2. Return AnalyzerResult with summary data
    3. Handle errors gracefully
    """
    
    def __init__(self, language: str, supported_frameworks: List[str]):
        """
        Initialize analyzer.
        
        Args:
            language: Language this analyzer handles (e.g., 'java', 'python')
            supported_frameworks: List of frameworks this analyzer supports
        """
        self.language = language
        self.supported_frameworks = supported_frameworks
    
    @abstractmethod
    def analyze(self, repo_path: Path, output_dir: Path) -> AnalyzerResult:
        """
        Analyze a repository and produce all 8 JSON output files.
        
        This method must produce the following files in output_dir:
        - 01_test_files.json
        - 02_framework_detection.json
        - 03_test_registry.json
        - 04_static_dependencies.json
        - 04b_function_calls.json
        - 05_test_metadata.json
        - 06_reverse_index.json
        - 07_test_structure.json
        - 08_summary_report.json
        
        Args:
            repo_path: Path to repository root
            output_dir: Directory to write JSON output files
            
        Returns:
            AnalyzerResult with analysis summary and metadata
        """
        pass
    
    def get_language(self) -> str:
        """Return language this analyzer handles."""
        return self.language
    
    def get_supported_frameworks(self) -> List[str]:
        """Return frameworks this analyzer supports."""
        return self.supported_frameworks
    
    def supports_framework(self, framework: str) -> bool:
        """Check if analyzer supports a framework."""
        return framework in self.supported_frameworks
    
    def can_analyze(self, language: str, framework: Optional[str] = None) -> bool:
        """
        Check if this analyzer can analyze a language/framework combination.
        
        Args:
            language: Language to check
            framework: Optional framework to check
            
        Returns:
            True if analyzer can handle this combination
        """
        if language != self.language:
            return False
        if framework and not self.supports_framework(framework):
            return False
        return True
    
    def _ensure_output_dir(self, output_dir: Path) -> None:
        """Ensure output directory exists."""
        output_dir.mkdir(parents=True, exist_ok=True)
    
    def _log_progress(self, message: str) -> None:
        """Log progress message."""
        logger.info(f"[{self.language}] {message}")
