"""GitLab API service for repository operations."""

import os
import httpx
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse, quote
import logging

from services.http_client import get_shared_async_client

logger = logging.getLogger(__name__)


class GitLabService:
    """Service for GitLab API operations."""
    
    def __init__(self, api_token: Optional[str] = None, api_url: Optional[str] = None):
        """
        Initialize GitLab service.
        
        Args:
            api_token: GitLab personal access token (from env: GITLAB_API_TOKEN)
            api_url: GitLab API base URL (from env: GITLAB_API_URL, default: https://gitlab.com/api/v4)
        """
        self.api_token = api_token or os.getenv('GITLAB_API_TOKEN')
        self.default_api_url = api_url or os.getenv('GITLAB_API_URL', 'https://gitlab.com/api/v4')
        
        if not self.api_token:
            logger.warning("GITLAB_API_TOKEN not set. GitLab API features will be limited.")
        
        self.headers = {
            'PRIVATE-TOKEN': self.api_token,
            'Content-Type': 'application/json'
        } if self.api_token else {'Content-Type': 'application/json'}
    
    def get_api_url_for_repo(self, repo_url: str) -> str:
        """
        Get the correct API URL for a given repository URL.
        Automatically detects self-hosted GitLab instances.
        
        Args:
            repo_url: Repository URL
            
        Returns:
            API base URL (e.g., https://gitlab.com/api/v4 or http://gitlab.ideyalabs.com/api/v4)
        """
        try:
            parsed = urlparse(repo_url)
            hostname = parsed.hostname or ''
            
            # If it's not gitlab.com, it's a self-hosted instance
            if hostname and 'gitlab.com' not in hostname:
                # Construct API URL for self-hosted instance
                scheme = parsed.scheme or 'https'
                api_url = f"{scheme}://{hostname}/api/v4"
                logger.info(f"Detected self-hosted GitLab: {api_url}")
                return api_url
            
            # Default to configured API URL or gitlab.com
            return self.default_api_url
        except Exception as e:
            logger.warning(f"Failed to parse repo URL for API detection: {e}")
            return self.default_api_url
    
    @staticmethod
    def is_gitlab_url(url: str) -> bool:
        """
        Check if URL is a GitLab repository URL.
        
        Args:
            url: Repository URL
            
        Returns:
            True if URL is from GitLab
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ''
            return 'gitlab.com' in hostname or 'gitlab' in hostname.lower()
        except Exception:
            return False
    
    def parse_gitlab_url(self, repo_url: str) -> Dict[str, str]:
        """
        Parse GitLab repository URL to extract project path.
        
        Args:
            repo_url: GitLab repository URL (e.g., https://gitlab.com/group/project.git)
            
        Returns:
            Dictionary with 'project_path' (group/project) and 'hostname'
        """
        parsed = urlparse(repo_url)
        # Remove .git suffix if present
        path = parsed.path.strip('/').replace('.git', '')
        return {
            'project_path': path,
            'hostname': parsed.hostname or 'gitlab.com'
        }
    
    async def get_project_info(self, repo_url: str) -> Optional[Dict]:
        """
        Get GitLab project information.
        
        Args:
            repo_url: GitLab repository URL
            
        Returns:
            Project information dictionary or None if failed
        """
        if not self.api_token:
            logger.warning("Cannot fetch GitLab project info: API token not configured")
            return None
        
        try:
            # Get the correct API URL for this repository
            api_url = self.get_api_url_for_repo(repo_url)
            
            project_info = self.parse_gitlab_url(repo_url)
            project_path = project_info['project_path']
            # URL encode the project path (replace / with %2F)
            encoded_path = project_path.replace('/', '%2F')
            
            client = get_shared_async_client()
            response = await client.get(
                f"{api_url}/projects/{encoded_path}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"GitLab API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get GitLab project info: {e}")
            return None
    
    async def get_latest_commit(
        self,
        repo_url: str,
        branch: str = None,
        default_branch_hint: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get latest commit information.
        
        Args:
            repo_url: GitLab repository URL
            branch: Branch name (if None, uses default_branch_hint or project info)
            default_branch_hint: Optional default branch from DB to avoid an extra project API call
            
        Returns:
            Commit information dictionary or None if failed
        """
        if not self.api_token:
            logger.warning("Cannot fetch GitLab commits: API token not configured")
            return None
        
        try:
            # If branch not specified, prefer stored default from caller, then project API
            if branch is None:
                if default_branch_hint:
                    branch = default_branch_hint
                else:
                    project_info = await self.get_project_info(repo_url)
                    if project_info:
                        branch = project_info.get('default_branch') or 'main'
                    else:
                        branch = 'main'
            
            # Get the correct API URL for this repository
            api_url = self.get_api_url_for_repo(repo_url)
            
            project_info = self.parse_gitlab_url(repo_url)
            project_path = project_info['project_path']
            encoded_path = project_path.replace('/', '%2F')
            
            client = get_shared_async_client()
            response = await client.get(
                f"{api_url}/projects/{encoded_path}/repository/commits",
                headers=self.headers,
                params={'ref_name': branch, 'per_page': 1},
            )
            response.raise_for_status()
            commits = response.json()

            if commits and len(commits) > 0:
                return commits[0]
            logger.warning(f"No commits found for branch '{branch}'")
            return None
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if hasattr(e.response, 'text') else str(e)
            logger.error(f"GitLab API error: {e.response.status_code} - {error_text}")
            
            # If 404, the branch might not exist - try to get default branch
            if e.response.status_code == 404:
                logger.info(f"Branch '{branch}' not found, trying to get default branch")
                project_info = await self.get_project_info(repo_url)
                if project_info:
                    default_branch = project_info.get('default_branch')
                    if default_branch and default_branch != branch:
                        logger.info(f"Retrying with default branch: {default_branch}")
                        return await self.get_latest_commit(repo_url, branch=default_branch)
            
            return None
        except Exception as e:
            logger.error(f"Failed to get GitLab commits: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    async def validate_access(self, repo_url: str) -> bool:
        """
        Validate that we have access to the GitLab repository.
        
        Args:
            repo_url: GitLab repository URL
            
        Returns:
            True if access is valid, False otherwise
        """
        if not self.api_token:
            logger.warning("Cannot validate access: GITLAB_API_TOKEN not set")
            return False
        
        try:
            project_info = await self.get_project_info(repo_url)
            if project_info:
                logger.info(f"Access validated successfully for repository: {repo_url}")
                return True
            else:
                logger.warning(f"Failed to get project info for {repo_url} - access may be denied")
                return False
        except Exception as e:
            logger.error(f"Error validating access: {e}")
            return False
    
    def _format_gitlab_branch_rows(self, raw_branches: List[Dict]) -> List[Dict]:
        formatted_branches = []
        for branch in raw_branches:
            formatted_branches.append({
                'name': branch.get('name', ''),
                'default': branch.get('default', False),
                'protected': branch.get('protected', False),
                'commit_id': branch.get('commit', {}).get('id', '')[:8] if branch.get('commit') else '',
                'commit_message': branch.get('commit', {}).get('message', '')[:50] if branch.get('commit') else ''
            })
        return formatted_branches

    async def list_branches(
        self,
        repo_url: str,
        *,
        page: int = 1,
        per_page: int = 30,
        search: Optional[str] = None,
        fetch_all: bool = False,
    ) -> Dict[str, Any]:
        """
        List branches. By default returns one page (fast). Use fetch_all=True for full scan.

        Returns:
            dict with keys: branches (formatted), has_more, page, per_page
        """
        if not self.api_token:
            logger.warning("Cannot list branches: API token not configured")
            return {"branches": [], "has_more": False, "page": page, "per_page": per_page}

        try:
            api_url = self.get_api_url_for_repo(repo_url)
            project_info = self.parse_gitlab_url(repo_url)
            project_path = project_info['project_path']
            encoded_path = project_path.replace('/', '%2F')
            client = get_shared_async_client()

            if fetch_all:
                max_pages = max(1, min(int(os.getenv("BRANCH_LIST_MAX_PAGES", "100")), 1000))
                all_branches: List[Dict] = []
                p = 1
                pg_size = 100
                while True:
                    response = await client.get(
                        f"{api_url}/projects/{encoded_path}/repository/branches",
                        headers=self.headers,
                        params={'per_page': pg_size, 'page': p, **({'search': search} if search else {})},
                    )
                    response.raise_for_status()
                    batch = response.json()
                    if not batch:
                        break
                    all_branches.extend(batch)
                    total_pages = response.headers.get('X-Total-Pages')
                    if total_pages and p >= int(total_pages):
                        break
                    if 'rel="next"' not in response.headers.get('Link', ''):
                        break
                    p += 1
                    if p > max_pages:
                        logger.warning(
                            "GitLab branch list stopped at BRANCH_LIST_MAX_PAGES=%s (~%s branches)",
                            max_pages,
                            len(all_branches),
                        )
                        break
                formatted = self._format_gitlab_branch_rows(all_branches)
                logger.info("Fetched %s GitLab branches (fetch_all)", len(formatted))
                return {
                    "branches": formatted,
                    "has_more": False,
                    "page": 1,
                    "per_page": len(formatted),
                }

            eff_per_page = max(1, min(int(per_page), 100))
            eff_page = max(1, int(page))
            params: Dict[str, Any] = {'per_page': eff_per_page, 'page': eff_page}
            if search:
                params['search'] = search.strip()
            response = await client.get(
                f"{api_url}/projects/{encoded_path}/repository/branches",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            raw = response.json()
            formatted = self._format_gitlab_branch_rows(raw)
            total_pages_hdr = response.headers.get('X-Total-Pages')
            has_more = False
            if total_pages_hdr:
                has_more = eff_page < int(total_pages_hdr)
            else:
                has_more = len(raw) >= eff_per_page and 'rel="next"' in response.headers.get('Link', '')
            return {
                "branches": formatted,
                "has_more": has_more,
                "page": eff_page,
                "per_page": eff_per_page,
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"GitLab API error listing branches: {e.response.status_code} - {e.response.text}")
            return {"branches": [], "has_more": False, "page": page, "per_page": per_page}
        except Exception as e:
            logger.error(f"Failed to list branches: {e}")
            return {"branches": [], "has_more": False, "page": page, "per_page": per_page}

    async def get_branch(self, repo_url: str, branch_name: str) -> Optional[Dict]:
        """GET a single branch (used to inject default/selected when not on the current list page)."""
        if not self.api_token or not (branch_name or "").strip():
            return None
        try:
            api_url = self.get_api_url_for_repo(repo_url)
            project_info = self.parse_gitlab_url(repo_url)
            encoded_path = project_info["project_path"].replace("/", "%2F")
            enc_branch = quote(str(branch_name).strip(), safe="")
            client = get_shared_async_client()
            response = await client.get(
                f"{api_url}/projects/{encoded_path}/repository/branches/{enc_branch}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug("GitLab get_branch %s: %s", branch_name, e)
            return None

    def _pack_gitlab_diff_list(self, diff_rows: List[Dict]) -> Dict:
        """Normalize GitLab per-file diff array into our standard shape."""
        if not diff_rows:
            return {
                "diff": "",
                "changed_files": [],
                "stats": {"additions": 0, "deletions": 0, "files_changed": 0},
            }
        changed_files = [d.get("new_path", d.get("old_path", "")) for d in diff_rows]
        diff_content = [d.get("diff", "") for d in diff_rows if d.get("diff")]
        additions = sum(d.get("added_lines", 0) or 0 for d in diff_rows)
        deletions = sum(d.get("removed_lines", 0) or 0 for d in diff_rows)
        if additions == 0 and deletions == 0 and diff_content:
            full_diff = "\n".join(diff_content)
            additions = sum(
                1
                for line in full_diff.split("\n")
                if line.startswith("+") and not line.startswith("+++")
            )
            deletions = sum(
                1
                for line in full_diff.split("\n")
                if line.startswith("-") and not line.startswith("---")
            )
        cf = [f for f in changed_files if f]
        return {
            "diff": "\n".join(diff_content),
            "changed_files": cf,
            "stats": {
                "additions": additions,
                "deletions": deletions,
                "files_changed": len(cf),
            },
        }

    async def _fetch_commit_diff_raw(
        self, repo_url: str, commit_sha: str
    ) -> Optional[Dict]:
        """
        GET .../repository/commits/:sha/diff — works when repository/compare returns no diffs
        (seen on some self-hosted GitLab versions/settings).
        """
        if not self.api_token or not commit_sha:
            return None
        try:
            api_url = self.get_api_url_for_repo(repo_url)
            project_info = self.parse_gitlab_url(repo_url)
            project_path = project_info["project_path"]
            encoded_path = project_path.replace("/", "%2F")
            client = get_shared_async_client()
            response = await client.get(
                f"{api_url}/projects/{encoded_path}/repository/commits/{commit_sha}/diff",
                headers=self.headers,
            )
            response.raise_for_status()
            diff_data = response.json()
            if not isinstance(diff_data, list):
                return None
            packed = self._pack_gitlab_diff_list(diff_data)
            if packed.get("diff") or packed.get("changed_files"):
                logger.info(
                    "GitLab commit diff endpoint returned %s file(s) for %s…",
                    len(packed.get("changed_files") or []),
                    commit_sha[:8],
                )
            return packed
        except Exception as e:
            logger.warning("GitLab commit diff fallback failed: %s", e)
            return None

    async def get_commit_diff(self, repo_url: str, from_commit: str, to_commit: str) -> Optional[Dict]:
        """
        Get diff between two commits using GitLab API.
        No cloning needed!
        
        Args:
            repo_url: GitLab repository URL
            from_commit: Source commit SHA (or branch name)
            to_commit: Target commit SHA (or branch name)
            
        Returns:
            Dictionary with diff data, changed files, and stats, or None if failed
        """
        if not self.api_token:
            logger.warning("Cannot fetch commit diff: API token not configured")
            return None
        
        try:
            api_url = self.get_api_url_for_repo(repo_url)
            project_info = self.parse_gitlab_url(repo_url)
            project_path = project_info['project_path']
            encoded_path = project_path.replace('/', '%2F')
            
            client = get_shared_async_client()
            response = await client.get(
                f"{api_url}/projects/{encoded_path}/repository/compare",
                headers=self.headers,
                params={'from': from_commit, 'to': to_commit},
            )
            response.raise_for_status()
            compare_data = response.json()

            diff_text = compare_data.get('diffs', [])
            changed_files = [d.get('new_path', d.get('old_path', '')) for d in diff_text]

            diff_content = []
            for file_diff in diff_text:
                if file_diff.get('diff'):
                    diff_content.append(file_diff['diff'])

            additions = sum(d.get('added_lines', 0) or 0 for d in diff_text)
            deletions = sum(d.get('removed_lines', 0) or 0 for d in diff_text)

            if additions == 0 and deletions == 0 and diff_content:
                full_diff = '\n'.join(diff_content)
                additions = sum(1 for line in full_diff.split('\n') if line.startswith('+') and not line.startswith('+++'))
                deletions = sum(1 for line in full_diff.split('\n') if line.startswith('-') and not line.startswith('---'))

            result = {
                "diff": '\n'.join(diff_content),
                "changed_files": [f for f in changed_files if f],
                "stats": {
                    "additions": additions,
                    "deletions": deletions,
                    "files_changed": len([f for f in changed_files if f])
                }
            }
            if not (result["diff"] or "").strip() and not result["changed_files"]:
                logger.warning(
                    "GitLab compare returned no diffs (from=%s, to=%s); trying commit diff API",
                    str(from_commit)[:8],
                    str(to_commit)[:8],
                )
                fallback = await self._fetch_commit_diff_raw(repo_url, to_commit)
                if fallback and (
                    (fallback.get("diff") or "").strip()
                    or fallback.get("changed_files")
                ):
                    return fallback
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"GitLab API error getting commit diff: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get commit diff: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    async def get_latest_diff(
        self,
        repo_url: str,
        branch: str = None,
        default_branch_hint: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get diff for the latest commit on a branch using GitLab API.
        Compares latest commit with its parent.
        
        Args:
            repo_url: GitLab repository URL
            branch: Branch name (if None, uses default branch)
            
        Returns:
            Dictionary with diff data, changed files, and stats, or None if failed
        """
        if not self.api_token:
            logger.warning("Cannot fetch latest diff: API token not configured")
            return None
        
        try:
            # Get latest commit
            latest_commit = await self.get_latest_commit(
                repo_url, branch, default_branch_hint=default_branch_hint
            )
            if not latest_commit:
                logger.warning("No latest commit found")
                return None
            
            commit_id = latest_commit.get('id')
            parent_ids = latest_commit.get('parent_ids', [])
            
            if not commit_id:
                logger.warning("Commit ID not found in commit data")
                return None
            
            # If no parent (first commit), compare with empty tree
            if not parent_ids:
                # For first commit, we can get the commit diff directly
                api_url = self.get_api_url_for_repo(repo_url)
                project_info = self.parse_gitlab_url(repo_url)
                project_path = project_info['project_path']
                encoded_path = project_path.replace('/', '%2F')
                
                client = get_shared_async_client()
                response = await client.get(
                    f"{api_url}/projects/{encoded_path}/repository/commits/{commit_id}/diff",
                    headers=self.headers,
                )
                response.raise_for_status()
                diff_data = response.json()

                changed_files = [d.get('new_path', d.get('old_path', '')) for d in diff_data]
                diff_content = [d.get('diff', '') for d in diff_data if d.get('diff')]

                additions = sum(d.get('added_lines', 0) or 0 for d in diff_data)
                deletions = sum(d.get('removed_lines', 0) or 0 for d in diff_data)

                if additions == 0 and deletions == 0 and diff_content:
                    full_diff = '\n'.join(diff_content)
                    additions = sum(1 for line in full_diff.split('\n') if line.startswith('+') and not line.startswith('+++'))
                    deletions = sum(1 for line in full_diff.split('\n') if line.startswith('-') and not line.startswith('---'))

                return {
                    "diff": '\n'.join(diff_content),
                    "changed_files": [f for f in changed_files if f],
                    "stats": {
                        "additions": additions,
                        "deletions": deletions,
                        "files_changed": len([f for f in changed_files if f])
                    }
                }
            else:
                # Compare with parent commit
                parent_id = parent_ids[0]
                return await self.get_commit_diff(repo_url, parent_id, commit_id)
                
        except Exception as e:
            logger.error(f"Failed to get latest diff: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def get_webhook_events(self) -> List[str]:
        """
        Get available webhook events (for webhook setup).
        
        Returns:
            List of webhook event types
        """
        return [
            'push_events',
            'merge_requests_events',
            'tag_push_events',
            'issues_events',
            'note_events'
        ]