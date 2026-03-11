"""
Dynamic schema builder for database tables.

Builds schema based on detected languages and frameworks.
"""

from .schema_builder import SchemaBuilder, build_schema_for_detection

__all__ = [
    'SchemaBuilder',
    'build_schema_for_detection',
]
