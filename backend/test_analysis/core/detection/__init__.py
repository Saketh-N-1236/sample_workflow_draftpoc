"""
Language and framework detection modules.
"""

from .language_detector import detect_languages, LanguageDetectionResult
from .framework_detector import detect_frameworks, FrameworkDetectionResult
from .detection_report import DetectionReport, create_detection_report

__all__ = [
    'detect_languages',
    'LanguageDetectionResult',
    'detect_frameworks',
    'FrameworkDetectionResult',
    'DetectionReport',
    'create_detection_report',
]
