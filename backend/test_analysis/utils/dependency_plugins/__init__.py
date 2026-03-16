"""
Dependency Extraction Plugins

Language-specific plugins for extracting and identifying production code dependencies.
Each plugin knows how to:
1. Extract imports from its language
2. Identify production code vs test frameworks
3. Extract class/module names from imports
4. Handle language-specific patterns
"""

from .base import DependencyPlugin, PluginRegistry, get_registry
from .java_plugin import JavaDependencyPlugin
from .python_plugin import PythonDependencyPlugin
from .javascript_plugin import JavaScriptDependencyPlugin

__all__ = [
    'DependencyPlugin',
    'PluginRegistry',
    'get_registry',
    'JavaDependencyPlugin',
    'PythonDependencyPlugin',
    'JavaScriptDependencyPlugin',
]
