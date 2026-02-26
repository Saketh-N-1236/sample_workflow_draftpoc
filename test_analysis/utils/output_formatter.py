"""
Output formatting utilities for console and JSON output.

This module provides functions to:
- Format console output with clear headers and sections
- Save data to JSON files with proper formatting
- Display progress indicators
- Print structured data in a readable format
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime


def print_header(title: str, width: int = 50) -> None:
    """
    Print a formatted header for console output.
    
    Args:
        title: The title text to display
        width: Width of the header line (default: 50)
    
    Example:
        >>> print_header("Step 1: Scanning Test Files")
        ==================================================
        Step 1: Scanning Test Files
        ==================================================
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
    
    Example:
        >>> print_section("Found Test Files:")
          Found Test Files:
    """
    print(" " * indent + title)


def print_item(label: str, value: Any, indent: int = 4) -> None:
    """
    Print a labeled item with indentation.
    
    Args:
        label: The label text
        value: The value to display
        indent: Number of spaces to indent (default: 4)
    
    Example:
        >>> print_item("Total files:", 15)
            Total files: 15
    """
    print(" " * indent + f"{label} {value}")


def print_list(items: List[Any], label: str = "", max_items: int = 10, indent: int = 4) -> None:
    """
    Print a list of items, limiting the number shown.
    
    Args:
        items: List of items to print
        label: Optional label for the list
        max_items: Maximum number of items to show (default: 10)
        indent: Number of spaces to indent (default: 4)
    
    Example:
        >>> print_list(["file1.py", "file2.py"], "Files:", max_items=5)
            Files:
              - file1.py
              - file2.py
    """
    if label:
        print(" " * indent + label)
    
    for i, item in enumerate(items[:max_items]):
        print(" " * (indent + 2) + f"- {item}")
    
    if len(items) > max_items:
        remaining = len(items) - max_items
        print(" " * (indent + 2) + f"... and {remaining} more")


def save_json(data: Dict[str, Any], filepath: Path, pretty: bool = True) -> None:
    """
    Save data to a JSON file with optional pretty printing.
    
    Args:
        data: Dictionary to save as JSON
        filepath: Path where to save the file
        pretty: Whether to format JSON with indentation (default: True)
    
    Example:
        >>> data = {"total": 10, "items": [1, 2, 3]}
        >>> save_json(data, Path("output.json"))
        # Creates output.json with formatted JSON
    """
    # Ensure the directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Add metadata
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "data": data
    }
    
    # Write JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        else:
            json.dump(output_data, f, ensure_ascii=False)
    
    print(f"Saved to: {filepath}")


def print_summary(stats: Dict[str, Any], indent: int = 2) -> None:
    """
    Print a summary of statistics in a formatted way.
    
    Args:
        stats: Dictionary of statistics to display
        indent: Number of spaces to indent (default: 2)
    
    Example:
        >>> stats = {"total_files": 15, "total_tests": 50}
        >>> print_summary(stats)
          Summary:
            Total files: 15
            Total tests: 50
    """
    print(" " * indent + "Summary:")
    for key, value in stats.items():
        # Convert key from snake_case to Title Case
        label = key.replace('_', ' ').title()
        print(" " * (indent + 2) + f"{label}: {value}")


def print_progress(current: int, total: int, item_name: str = "items") -> None:
    """
    Print a progress indicator.
    
    Args:
        current: Current item number
        total: Total number of items
        item_name: Name of the items being processed (default: "items")
    
    Example:
        >>> print_progress(5, 10, "files")
        Processing: 5/10 files (50%)
    """
    percentage = (current / total * 100) if total > 0 else 0
    print(f"Processing: {current}/{total} {item_name} ({percentage:.1f}%)", end='\r')
    
    # Print newline when complete
    if current == total:
        print()  # Move to next line
