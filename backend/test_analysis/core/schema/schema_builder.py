"""
Dynamic schema builder.

Builds database schema based on detected languages and frameworks.
"""

from typing import Dict, List, Set
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class SchemaDefinition:
    """Database schema definition."""
    
    core_tables: List[str] = field(default_factory=lambda: [
        'test_registry',
        'test_dependencies',
        'reverse_index',
        'test_metadata',
        'test_structure',
        'test_function_mapping',
    ])
    
    java_tables: List[str] = field(default_factory=list)
    python_tables: List[str] = field(default_factory=list)
    js_tables: List[str] = field(default_factory=list)
    
    def get_all_tables(self) -> List[str]:
        """Get all table names."""
        all_tables = list(self.core_tables)
        all_tables.extend(self.java_tables)
        all_tables.extend(self.python_tables)
        all_tables.extend(self.js_tables)
        return all_tables
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'core_tables': self.core_tables,
            'java_tables': self.java_tables,
            'python_tables': self.python_tables,
            'js_tables': self.js_tables,
        }


class SchemaBuilder:
    """
    Builds database schema based on detected languages.
    
    Creates language-specific tables only for detected languages.
    """
    
    # Language-specific table definitions
    JAVA_TABLES = [
        'java_reflection_calls',  # Reflection usage in tests
        'java_di_fields',        # Dependency injection fields
        'java_annotations',      # All annotations on tests
    ]
    
    PYTHON_TABLES = [
        'python_fixtures',       # pytest fixtures
        'python_decorators',     # Test decorators
        'python_async_tests',    # Async test detection
    ]
    
    JS_TABLES = [
        'js_mocks',              # Mock usage
        'js_async_tests',        # Async test detection
    ]
    
    def build_schema(self, detection_report: Dict) -> SchemaDefinition:
        """
        Build schema based on detection report.
        
        Args:
            detection_report: Detection report from detection phase
            
        Returns:
            SchemaDefinition with tables to create
        """
        languages = detection_report.get('languages', {})
        detected_langs = set(languages.keys())
        
        schema = SchemaDefinition()
        
        # Add language-specific tables based on detection
        if 'java' in detected_langs:
            schema.java_tables = list(self.JAVA_TABLES)
            logger.info("Java detected - adding Java-specific tables")
        
        if 'python' in detected_langs:
            schema.python_tables = list(self.PYTHON_TABLES)
            logger.info("Python detected - adding Python-specific tables")
        
        if 'javascript' in detected_langs or 'typescript' in detected_langs:
            schema.js_tables = list(self.JS_TABLES)
            logger.info("JavaScript/TypeScript detected - adding JS-specific tables")
        
        # Count only core tables that are actually created in the database
        # Language-specific tables are planned but not yet implemented in table creation
        core_tables_count = len(schema.core_tables)
        logger.info(f"Schema built: {core_tables_count} core tables (language-specific tables planned but not yet created)")
        
        return schema


def build_schema_for_detection(detection_report: Dict) -> SchemaDefinition:
    """
    Convenience function to build schema from detection report.
    
    Args:
        detection_report: Detection report dictionary
        
    Returns:
        SchemaDefinition
    """
    builder = SchemaBuilder()
    return builder.build_schema(detection_report)
