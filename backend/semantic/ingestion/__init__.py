"""
Data ingestion module for semantic retrieval.

Provides load_test_files_from_repo (load test files from a repo path) and
transform_test_data for embedding generation. No JSON or database dependency.
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    'load_test_files_from_repo',
    'transform_test_data',
]


def __getattr__(name):
    """Lazy import for ingestion functions."""
    if name == 'load_test_files_from_repo':
        from semantic.ingestion.test_data_loader import load_test_files_from_repo
        return load_test_files_from_repo
    elif name == 'transform_test_data':
        from semantic.ingestion.data_transformer import transform_test_data
        return transform_test_data
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
