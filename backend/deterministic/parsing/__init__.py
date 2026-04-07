"""
Deterministic parsing — git diff parsing and search-query building.

Structural parsing lives alongside the deterministic DB pipeline.
"""

from deterministic.parsing.diff_parser import (
    analyze_file_change_type,
    build_search_queries,
    extract_changed_functions_with_modules,
    extract_definitions_from_diff,
    extract_deleted_added_renamed_symbols,
    extract_production_classes_from_file,
    extract_production_modules_from_file,
    extract_test_file_candidates,
    is_production_file,
    is_production_python_file,
    parse_git_diff,
    read_diff_file,
)

__all__ = [
    "analyze_file_change_type",
    "build_search_queries",
    "extract_changed_functions_with_modules",
    "extract_definitions_from_diff",
    "extract_deleted_added_renamed_symbols",
    "extract_production_classes_from_file",
    "extract_production_modules_from_file",
    "extract_test_file_candidates",
    "is_production_file",
    "is_production_python_file",
    "parse_git_diff",
    "read_diff_file",
]
