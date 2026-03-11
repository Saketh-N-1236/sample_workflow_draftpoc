"""
Base plugin interface for language-specific dependency extraction.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Set, Optional
import logging

logger = logging.getLogger(__name__)


class DependencyPlugin(ABC):
    """
    Base class for language-specific dependency extraction plugins.
    
    Each plugin handles:
    1. Import extraction from source code
    2. Production code identification (vs test frameworks)
    3. Class/module name extraction from imports
    4. String-based reference extraction (e.g., patch() calls)
    """
    
    def __init__(self, language: str):
        """
        Initialize the plugin.
        
        Args:
            language: Language name (e.g., 'java', 'python', 'javascript')
        """
        self.language = language
    
    @abstractmethod
    def extract_imports(self, filepath: Path, content: str) -> List[str]:
        """
        Extract all import statements from a file.
        
        Args:
            filepath: Path to the source file
            content: File content as string
        
        Returns:
            List of import strings (e.g., ['com.example.Foo', 'org.bar.Baz'])
        """
        pass
    
    @abstractmethod
    def is_production_import(self, import_name: str) -> bool:
        """
        Check if an import is production code (not test framework or stdlib).
        
        Args:
            import_name: Full import name (e.g., 'com.strmecast.istream.request.LoginRequest')
        
        Returns:
            True if it's production code, False otherwise
        """
        pass
    
    @abstractmethod
    def extract_class_name(self, import_name: str) -> Optional[str]:
        """
        Extract class/module name from an import.
        
        Args:
            import_name: Full import (e.g., 'com.strmecast.istream.request.LoginRequest')
        
        Returns:
            Class name (e.g., 'LoginRequest') or None if not a class import
        """
        pass
    
    @abstractmethod
    def extract_string_references(self, filepath: Path, content: str) -> List[str]:
        """
        Extract string-based references (e.g., patch() calls, mock() calls).
        
        Args:
            filepath: Path to the source file
            content: File content as string
        
        Returns:
            List of referenced class/module names
        """
        pass
    
    def extract_dependencies(self, filepath: Path) -> Dict:
        """
        Extract all dependencies from a file (main entry point).
        
        Args:
            filepath: Path to the source file
        
        Returns:
            Dictionary with dependency information:
            {
                'file_path': str,
                'language': str,
                'imports': List[str],
                'production_imports': List[str],
                'production_classes': List[str],  # Extracted class names
                'string_references': List[str],
                'production_string_references': List[str],
                'all_production_references': List[str],
                'total_import_count': int,
                'production_import_count': int,
            }
        """
        try:
            content = filepath.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            logger.error(f"Cannot read {filepath}: {e}")
            return self._empty_result(str(filepath))
        
        # Extract all imports
        all_imports = self.extract_imports(filepath, content)
        
        # Filter for production code
        production_imports = [
            imp for imp in all_imports
            if self.is_production_import(imp)
        ]
        
        # Extract class names from production imports
        production_classes = []
        for imp in production_imports:
            class_name = self.extract_class_name(imp)
            if class_name:
                production_classes.append(class_name)
        
        # Extract string-based references
        string_refs = self.extract_string_references(filepath, content)
        production_string_refs = [
            ref for ref in string_refs
            if self.is_production_import(ref)
        ]
        
        # For Java: if no production imports found, try to infer from test structure
        inferred_refs = []
        if self.language == 'java' and not production_imports:
            if hasattr(self, 'infer_production_dependencies_from_test_structure'):
                try:
                    inferred_refs = self.infer_production_dependencies_from_test_structure(filepath, content)
                    # Filter inferred refs to ensure they're production code
                    inferred_refs = [ref for ref in inferred_refs if self.is_production_import(ref) or not any(tf in ref.lower() for tf in ['test', 'junit', 'mockito'])]
                except Exception as e:
                    logger.debug(f"Inference failed for {filepath.name}: {e}")
        
        # Combine all production references (imports + string refs + inferred)
        all_production_refs = set(production_imports)
        all_production_refs.update(production_string_refs)
        all_production_refs.update(inferred_refs)
        
        # Extract class names from inferred refs too
        for inf_ref in inferred_refs:
            class_name = self.extract_class_name(inf_ref)
            if class_name and class_name not in production_classes:
                production_classes.append(class_name)
        
        return {
            'file_path': str(filepath),
            'language': self.language,
            'imports': all_imports,
            'production_imports': production_imports,
            'production_classes': production_classes,
            'string_references': string_refs,
            'production_string_references': production_string_refs,
            'inferred_references': inferred_refs,  # NEW: Track inferred dependencies
            'all_production_references': sorted(list(all_production_refs)),
            'total_import_count': len(all_imports),
            'production_import_count': len(production_imports) + len(inferred_refs),  # Include inferred in count
        }
    
    def _empty_result(self, file_path: str) -> Dict:
        """Return empty result structure."""
        return {
            'file_path': file_path,
            'language': self.language,
            'imports': [],
            'production_imports': [],
            'production_classes': [],
            'string_references': [],
            'production_string_references': [],
            'all_production_references': [],
            'total_import_count': 0,
            'production_import_count': 0,
        }


class PluginRegistry:
    """
    Registry for managing language-specific dependency plugins.
    """
    
    def __init__(self):
        self._plugins: Dict[str, DependencyPlugin] = {}
    
    def register(self, plugin: DependencyPlugin):
        """Register a plugin for a language."""
        self._plugins[plugin.language] = plugin
        logger.info(f"Registered dependency plugin for {plugin.language}")
    
    def get_plugin(self, language: str) -> Optional[DependencyPlugin]:
        """Get plugin for a language."""
        return self._plugins.get(language)
    
    def get_plugin_for_file(self, filepath: Path) -> Optional[DependencyPlugin]:
        """Get plugin based on file extension."""
        ext = filepath.suffix.lower()
        language_map = {
            '.java': 'java',
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.kt': 'kotlin',
            '.rb': 'ruby',
            '.cs': 'csharp',
            '.go': 'go',
        }
        language = language_map.get(ext)
        if language:
            return self.get_plugin(language)
        return None
    
    def has_plugin(self, language: str) -> bool:
        """Check if a plugin exists for a language."""
        return language in self._plugins


# Global registry instance
_registry = None

def get_registry() -> PluginRegistry:
    """Get or create the global plugin registry."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
        # Auto-register built-in plugins
        from .java_plugin import JavaDependencyPlugin
        from .python_plugin import PythonDependencyPlugin
        from .javascript_plugin import JavaScriptDependencyPlugin
        
        _registry.register(JavaDependencyPlugin())
        _registry.register(PythonDependencyPlugin())
        _registry.register(JavaScriptDependencyPlugin())
    return _registry
