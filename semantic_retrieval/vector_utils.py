"""
Vector utilities for pgvector format conversion.
"""

from typing import List


def embedding_to_pgvector(embedding: List[float]) -> str:
    """
    Convert Python list of floats to pgvector string format.
    
    Args:
        embedding: List of floats (e.g., [0.1, 0.2, ...])
    
    Returns:
        pgvector string format: '[0.1,0.2,...]'
    """
    return '[' + ','.join(str(v) for v in embedding) + ']'


def pgvector_to_embedding(pgvector_str: str) -> List[float]:
    """
    Convert pgvector string back to Python list of floats.
    
    Args:
        pgvector_str: pgvector string format: '[0.1,0.2,...]'
    
    Returns:
        List of floats
    """
    # Remove brackets and split by comma
    return [float(x.strip()) for x in pgvector_str.strip('[]').split(',')]
