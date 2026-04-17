"""
Provider-agnostic caps for embedding API inputs.

OpenAI text-embedding-* models accept at most 8192 tokens per input. Large git diffs
(100k+ chars) exceed this and return HTTP 400. We truncate to a safe character budget
(conservative vs. tokens for code-heavy text).
"""

from __future__ import annotations

import os
from typing import Tuple

# Conservative default: stay under ~8192 tokens even for dense code (often <4 chars/token).
_DEFAULT_MAX_CHARS = 12_000


def truncate_for_embedding_api(
    text: str,
    *,
    max_chars: int | None = None,
) -> Tuple[str, bool]:
    """
    Return (possibly truncated) text safe for a single embedding request.

    Set env EMBEDDING_INPUT_MAX_CHARS to override the default cap (2000–100000).
    Returns (text, was_truncated).
    """
    if not text:
        return text, False
    cap = max_chars
    if cap is None:
        raw = os.environ.get("EMBEDDING_INPUT_MAX_CHARS", "").strip()
        try:
            cap = int(raw) if raw else _DEFAULT_MAX_CHARS
        except ValueError:
            cap = _DEFAULT_MAX_CHARS
    cap = max(2_000, min(cap, 100_000))
    if len(text) <= cap:
        return text, False
    return text[:cap], True
