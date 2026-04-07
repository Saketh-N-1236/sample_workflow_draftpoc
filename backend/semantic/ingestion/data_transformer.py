"""
Data transformer for semantic retrieval.

Transforms test data from various sources for embedding generation.
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def transform_test_data(tests: List[Dict], source: str = 'json') -> List[Dict]:
    """
    Transform test data for embedding generation.
    
    Args:
        tests: List of test dictionaries
        source: Source type ('json', 'db', 'in_memory')
    
    Returns:
        Transformed list of test dictionaries
    """
    # For now, just return as-is
    # Future: Add transformations like normalization, enrichment, etc.
    return tests
