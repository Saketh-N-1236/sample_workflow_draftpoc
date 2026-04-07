"""Shared helpers for repository provider detection and diff payload normalization."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException

from services.gitlab_service import GitLabService
from services.github_service import GitHubService

logger = logging.getLogger(__name__)


def resolve_provider(repo_url: str, stored_provider: Optional[str]) -> str:
    """
    Return 'gitlab' or 'github' or raise HTTPException if unknown.

    stored_provider comes from the database; URL heuristics apply when unset.
    """
    if stored_provider in ("gitlab", "github"):
        return stored_provider
    if GitLabService.is_gitlab_url(repo_url):
        return "gitlab"
    if GitHubService.is_github_url(repo_url):
        return "github"
    raise HTTPException(
        status_code=400,
        detail="Could not determine repository provider. Specify 'github' or 'gitlab' when connecting.",
    )


def normalize_diff_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a copy with both snake_case and camelCase keys for downstream code.

    Mutates a shallow copy only; ensures changedFiles is present when changed_files exists.
    """
    out = dict(raw)
    cf = out.get("changed_files") or out.get("changedFiles") or []
    cf = [f for f in cf if f and str(f).strip()]
    out["changed_files"] = cf
    out["changedFiles"] = cf
    out.setdefault("diff", raw.get("diff", "") or "")
    out.setdefault("stats", raw.get("stats") or {})
    return out


def effective_branch(
    branch_query: Optional[str],
    selected_branch: Optional[str],
    default_branch: Optional[str],
) -> Optional[str]:
    """Resolve branch for API calls: query param > selected > default."""
    return branch_query or selected_branch or default_branch


def reflag_default_branches(branches: List[Dict[str, Any]], live_default: Optional[str]) -> None:
    """Mark default=True only for the provider's current default branch name."""
    if not live_default:
        return
    for b in branches:
        if b.get("name"):
            b["default"] = b["name"] == live_default


def sanitize_branch_rows(branches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop invalid rows, dedupe by name, normalize fields for BranchResponse."""
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for b in branches or []:
        name = str((b or {}).get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(
            {
                "name": name,
                "default": bool((b or {}).get("default")),
                "protected": bool((b or {}).get("protected", False)),
                "commit_id": str((b or {}).get("commit_id") or "")[:8],
                "commit_message": str((b or {}).get("commit_message") or "")[:200],
            }
        )
    return out


async def ensure_branches_present(
    provider: str,
    repo_url: str,
    branches: List[Dict[str, Any]],
    names: Set[str],
    *,
    gitlab_service: Optional[GitLabService] = None,
    github_service: Optional[GitHubService] = None,
) -> None:
    """
    Fetch any named branches missing from the list (default/selected not on first API page).
    Mutates branches in place (prepends found entries).
    """
    have = {str(b.get("name") or "").strip() for b in branches if b.get("name")}
    for name in sorted(names):
        n = str(name or "").strip()
        if not n or n in have:
            continue
        raw = None
        if provider == "gitlab" and gitlab_service:
            raw = await gitlab_service.get_branch(repo_url, n)
            if raw:
                branches.insert(
                    0,
                    {
                        "name": raw.get("name", n),
                        "default": bool(raw.get("default")),
                        "protected": bool(raw.get("protected", False)),
                        "commit_id": (raw.get("commit") or {}).get("id", "")[:8]
                        if raw.get("commit")
                        else "",
                        "commit_message": ((raw.get("commit") or {}).get("message") or "")[:50]
                        if raw.get("commit")
                        else "",
                    },
                )
                have.add(n)
        elif provider == "github" and github_service:
            raw = await github_service.get_branch(repo_url, n)
            if raw:
                c = raw.get("commit") or {}
                branches.insert(
                    0,
                    {
                        "name": raw.get("name", n),
                        "default": False,
                        "protected": bool(raw.get("protected", False)),
                        "commit_id": (c.get("sha") or "")[:8],
                        "commit_message": "",
                    },
                )
                have.add(n)
        else:
            logger.debug("ensure_branches_present: no service for provider=%s", provider)
