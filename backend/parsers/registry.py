"""
Compatibility shim for code that imported parsers.registry (removed legacy package).

Delegates to test_analysis.core.parsers.registry.
"""

from __future__ import annotations

from typing import Optional

from pathlib import Path

from test_analysis.core.parsers.registry import (
    ParserRegistry,
    get_parser_registry,
)


def initialize_registry(config_path: Optional[Path] = None) -> None:
    """
    Warm or reset the global parser registry.

    config_path is accepted for API compatibility; language configs are loaded
    separately via config.config_loader.load_language_configs.
    """
    get_parser_registry().clear_cache()


def get_registry() -> ParserRegistry:
    """Return the shared ParserRegistry instance."""
    return get_parser_registry()
