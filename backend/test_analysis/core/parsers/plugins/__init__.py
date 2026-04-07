"""
Parse plugins run after Tree-sitter when TS yields no test discovery.
Order: regex_fallback (built-in), then optional future plugins.
"""

from typing import Any, Callable, Dict, List, Tuple

ParsePlugin = Callable[[Any, str, str, Any], Dict]


def default_plugin_chain() -> List[Tuple[str, ParsePlugin]]:
    from test_analysis.core.parsers.plugins.regex_fallback import regex_fallback_parse

    return [
        ("regex_fallback", regex_fallback_parse),
    ]
