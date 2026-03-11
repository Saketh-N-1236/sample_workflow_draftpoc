"""
Language-specific analyzers.

Each analyzer implements the BaseAnalyzer interface and produces
all 8 JSON output files (01-08) for its language.
"""

from .base_analyzer import BaseAnalyzer, AnalyzerResult
from .java_analyzer import JavaAnalyzer
from .python_analyzer import PythonAnalyzer
from .javascript_analyzer import JavaScriptAnalyzer
from .treesitter_fallback import TreeSitterFallbackAnalyzer

__all__ = [
    'BaseAnalyzer',
    'AnalyzerResult',
    'JavaAnalyzer',
    'PythonAnalyzer',
    'JavaScriptAnalyzer',
    'TreeSitterFallbackAnalyzer',
]
