"""
Abstract base class for language parsers.

Each language (Python, Java, TypeScript, etc.) implements this interface
to provide language-specific parsing capabilities.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional


class LanguageParser(ABC):
    """
    Abstract interface for language-specific parsing.
    
    All language parsers must implement this interface to be compatible
    with the multi-language test impact analysis system.
    """
    
    @property
    @abstractmethod
    def language_name(self) -> str:
        """
        Return language name (e.g., 'python', 'java', 'typescript').
        
        Returns:
            Language identifier string
        """
        pass
    
    @property
    @abstractmethod
    def file_extensions(self) -> List[str]:
        """
        Return supported file extensions (e.g., ['.py'], ['.java', '.jav']).
        
        Returns:
            List of file extensions (with leading dot)
        """
        pass
    
    @abstractmethod
    def can_parse(self, filepath: Path) -> bool:
        """
        Check if this parser can handle the file.
        
        Args:
            filepath: Path to the file
            
        Returns:
            True if parser can handle this file, False otherwise
        """
        pass
    
    @abstractmethod
    def parse_file(self, filepath: Path, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[Any]:
        """
        Parse file into language-specific AST.
        
        Args:
            filepath: Path to the file to parse
            max_retries: Maximum retry attempts (for file locking issues)
            retry_delay: Delay between retries in seconds
            
        Returns:
            Language-specific AST object, or None if parsing fails
        """
        pass
    
    @abstractmethod
    def extract_imports(self, ast: Any) -> Dict[str, List[str]]:
        """
        Extract import/package statements from AST.
        
        Args:
            ast: Language-specific AST object
            
        Returns:
            Dictionary with:
            - 'imports': List of module/package names
            - 'from_imports': List of (module, [names]) tuples (if applicable)
            - 'all_imports': Combined list of all imported modules
        """
        pass
    
    @abstractmethod
    def extract_classes(self, ast: Any) -> List[Dict[str, Any]]:
        """
        Extract class definitions from AST.
        
        Args:
            ast: Language-specific AST object
            
        Returns:
            List of dictionaries, each containing:
            - 'name': Class name
            - 'line_number': Line where class is defined
            - 'methods': List of method names (optional)
        """
        pass
    
    @abstractmethod
    def extract_functions(self, ast: Any) -> List[Dict[str, Any]]:
        """
        Extract function/method definitions from AST.
        
        Args:
            ast: Language-specific AST object
            
        Returns:
            List of dictionaries, each containing:
            - 'name': Function/method name
            - 'line_number': Line where function is defined
            - 'class_name': Class name if method, None if standalone function
            - 'is_async': Boolean indicating if async function
        """
        pass
    
    @abstractmethod
    def extract_test_methods(self, ast: Any) -> List[Dict[str, Any]]:
        """
        Extract test methods from AST.
        
        Args:
            ast: Language-specific AST object
            
        Returns:
            List of dictionaries, each containing:
            - 'name': Test method name
            - 'class_name': Test class name (if applicable)
            - 'line_number': Line where test is defined
            - 'is_async': Boolean indicating if async test
        """
        pass
    
    @abstractmethod
    def extract_function_calls(self, ast: Any) -> List[Dict[str, Any]]:
        """
        Extract function calls within test methods.
        
        Args:
            ast: Language-specific AST object
            
        Returns:
            List of dictionaries, one per test method:
            - 'test_method': Name of the test method
            - 'calls': List of call dictionaries with:
                - 'function': Function/method name
                - 'object': Object name (if method call)
                - 'type': 'direct' or 'method'
                - 'line_number': Line where call occurs
        """
        pass
    
    @abstractmethod
    def extract_string_references(self, ast: Any) -> List[str]:
        """
        Extract string-based references (e.g., patch('module.Class')).
        
        Args:
            ast: Language-specific AST object
            
        Returns:
            List of module/class names found in string literals
        """
        pass
    
    @abstractmethod
    def resolve_module_name(self, filepath: Path, project_root: Path) -> str:
        """
        Convert file path to module/package name.
        
        Args:
            filepath: Path to the file
            project_root: Root directory of the project
            
        Returns:
            Module/package name (e.g., 'agent.langgraph_agent')
        """
        pass
