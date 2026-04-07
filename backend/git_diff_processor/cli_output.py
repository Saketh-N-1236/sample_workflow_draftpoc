"""CLI print helpers for git_diff_processor (kept separate from selection logic)."""

from typing import Any


def print_header(title: str, width: int = 50) -> None:
    """Print a formatted header."""
    print("=" * width)
    print(title)
    print("=" * width)


def print_section(title: str, indent: int = 2) -> None:
    """Print a section header."""
    print(" " * indent + title)


def print_item(label: str, value: Any = "", indent: int = 4) -> None:
    """Print a labeled item."""
    if value != "" and value is not None:
        print(" " * indent + f"{label}: {value}")
    else:
        print(" " * indent + label)
