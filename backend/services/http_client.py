"""Process-wide shared AsyncClient for GitLab/GitHub API calls (connection reuse)."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_shared: Optional[httpx.AsyncClient] = None


def get_shared_async_client() -> httpx.AsyncClient:
    global _shared
    if _shared is None:
        _shared = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
        logger.debug("Created shared httpx.AsyncClient for VCS APIs")
    return _shared


async def close_shared_async_client() -> None:
    global _shared
    if _shared is not None:
        await _shared.aclose()
        _shared = None
        logger.debug("Closed shared httpx.AsyncClient")
