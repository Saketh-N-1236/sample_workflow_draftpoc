"""
Output formatting utilities for console output.

This module provides functions for formatted console output,
similar to the test_analysis utilities but simplified for database operations.
"""

from datetime import datetime


def print_header(title: str, width: int = 50) -> None:
    """
    Print a formatted header for console output.
    
    Args:
        title: The title text to display
        width: Width of the header line (default: 50)
    """
    print("=" * width)
    print(title)
    print("=" * width)


def print_section(title: str, indent: int = 2) -> None:
    """
    Print a section header with indentation.
    
    Args:
        title: The section title
        indent: Number of spaces to indent (default: 2)
    """
    print(" " * indent + title)


def print_item(label: str, value: any = "", indent: int = 4) -> None:
    """
    Print a labeled item with indentation.
    
    Args:
        label: The label text
        value: The value to display (optional)
        indent: Number of spaces to indent (default: 4)
    """
    if value:
        print(" " * indent + f"{label}: {value}")
    else:
        print(" " * indent + label)
