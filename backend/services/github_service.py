"""GitHub API service for repository operations."""

import os
import httpx
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse, quote
import logging

from services.http_client import get_shared_async_client

logger = logging.getLogger(__name__)


class GitHubService:
    """Service for GitHub API operations."""
    
    def __init__(self, api_token: Optional[str] = None, api_url: Optional[str] = None):
        """
        Initialize GitHub service.
        
        Args:
            api_token: GitHub personal access token (from env: GITHUB_API_TOKEN)
            api_url: GitHub API base URL (from env: GITHUB_API_URL, default: https://api.github.com)
        """
        self.api_token = api_token or os.getenv('GITHUB_API_TOKEN')
        self.default_api_url = api_url or os.getenv('GITHUB_API_URL', 'https://api.github.com')
        
        if not self.api_token:
            logger.warning("GITHUB_API_TOKEN not set. GitHub API features will be limited.")
        
        self.headers = {
            'Authorization': f'token {self.api_token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        } if self.api_token else {
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
    
    @staticmethod
    def is_github_url(url: str) -> bool:
        """
        Check if URL is a GitHub repository URL.
        
        Args:
            url: Repository URL
            
        Returns:
            True if URL is from GitHub
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ''
            return 'github.com' in hostname.lower() or 'github.io' in hostname.lower()
        except:
            return False
    
    def parse_github_url(self, repo_url: str) -> Dict[str, str]:
        """
        Parse GitHub repository URL to extract owner and repo name.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Dictionary with owner and repo
        """
        try:
            parsed = urlparse(repo_url)
            path = parsed.path.strip('/')
            
            # Remove .git suffix if present
            if path.endswith('.git'):
                path = path[:-4]
            
            # Extract owner and repo from path
            parts = path.split('/')
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1]
                return {
                    'owner': owner,
                    'repo': repo
                }
            else:
                raise ValueError(f"Invalid GitHub URL format: {repo_url}")
        except Exception as e:
            logger.error(f"Failed to parse GitHub URL {repo_url}: {e}")
            raise
    
    async def get_repository_info(self, repo_url: str) -> Optional[Dict]:
        """
        Get repository information.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Repository information dictionary or None if failed
        """
        if not self.api_token:
            logger.warning("Cannot fetch GitHub repository info: API token not configured")
            return None
        
        try:
            repo_info = self.parse_github_url(repo_url)
            owner = repo_info['owner']
            repo = repo_info['repo']
            
            client = get_shared_async_client()
            response = await client.get(
                f"{self.default_api_url}/repos/{owner}/{repo}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get GitHub repository info: {e}")
            return None
    
    async def validate_access(self, repo_url: str) -> bool:
        """
        Validate that we have access to the GitHub repository.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            True if access is valid, False otherwise
        """
        if not self.api_token:
            logger.warning("Cannot validate access: GITHUB_API_TOKEN not set")
            return False
        
        try:
            repo_info = await self.get_repository_info(repo_url)
            if repo_info:
                logger.info(f"Access validated successfully for repository: {repo_url}")
                return True
            else:
                logger.warning(f"Failed to get repository info for {repo_url} - access may be denied")
                return False
        except Exception as e:
            logger.error(f"Error validating access: {e}")
            return False
    
    def _format_github_branch_rows(self, raw_branches: List[Dict], default_branch: str) -> List[Dict]:
        formatted_branches = []
        for branch in raw_branches:
            formatted_branches.append({
                'name': branch.get('name', ''),
                'default': branch.get('name') == default_branch,
                'protected': branch.get('protected', False),
                'commit_id': branch.get('commit', {}).get('sha', '')[:8] if branch.get('commit') else '',
                'commit_message': ''
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
        default_branch_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List branches. Default: single page. GitHub REST has no server-side branch search;
        optional `search` filters the current page client-side (use fetch_all to widen).
        """
        if not self.api_token:
            logger.warning("Cannot list branches: API token not configured")
            return {"branches": [], "has_more": False, "page": page, "per_page": per_page}

        try:
            repo_info = self.parse_github_url(repo_url)
            owner = repo_info['owner']
            repo = repo_info['repo']

            if default_branch_name:
                default_branch = default_branch_name
            else:
                repo_info_data = await self.get_repository_info(repo_url)
                default_branch = repo_info_data.get('default_branch', 'main') if repo_info_data else 'main'

            client = get_shared_async_client()
            eff_per_page = max(1, min(int(per_page), 100))
            eff_page = max(1, int(page))

            if fetch_all:
                max_pages = max(1, min(int(os.getenv("BRANCH_LIST_MAX_PAGES", "100")), 1000))
                all_branches: List[Dict] = []
                p = 1
                pg_size = 100
                while True:
                    response = await client.get(
                        f"{self.default_api_url}/repos/{owner}/{repo}/branches",
                        headers=self.headers,
                        params={'per_page': pg_size, 'page': p},
                    )
                    response.raise_for_status()
                    batch = response.json()
                    if not batch:
                        break
                    all_branches.extend(batch)
                    if 'rel="next"' not in response.headers.get('Link', ''):
                        break
                    p += 1
                    if p > max_pages:
                        logger.warning(
                            "GitHub branch list stopped at BRANCH_LIST_MAX_PAGES=%s (~%s branches)",
                            max_pages,
                            len(all_branches),
                        )
                        break
                formatted = self._format_github_branch_rows(all_branches, default_branch)
                if search:
                    s = search.strip().lower()
                    formatted = [b for b in formatted if s in b['name'].lower()]
                logger.info("Fetched %s GitHub branches (fetch_all)", len(formatted))
                return {
                    "branches": formatted,
                    "has_more": False,
                    "page": 1,
                    "per_page": len(formatted),
                }

            response = await client.get(
                f"{self.default_api_url}/repos/{owner}/{repo}/branches",
                headers=self.headers,
                params={'per_page': eff_per_page, 'page': eff_page},
            )
            response.raise_for_status()
            raw = response.json()
            formatted = self._format_github_branch_rows(raw, default_branch)
            if search:
                s = search.strip().lower()
                formatted = [b for b in formatted if s in b['name'].lower()]
            has_more = 'rel="next"' in response.headers.get('Link', '')
            return {
                "branches": formatted,
                "has_more": has_more,
                "page": eff_page,
                "per_page": eff_per_page,
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error listing branches: {e.response.status_code} - {e.response.text}")
            return {"branches": [], "has_more": False, "page": page, "per_page": per_page}
        except Exception as e:
            logger.error(f"Failed to list branches: {e}")
            return {"branches": [], "has_more": False, "page": page, "per_page": per_page}

    async def get_branch(self, repo_url: str, branch_name: str) -> Optional[Dict]:
        """GET a single branch (inject default/selected when missing from a list page)."""
        if not self.api_token or not (branch_name or "").strip():
            return None
        try:
            ri = self.parse_github_url(repo_url)
            owner, r = ri["owner"], ri["repo"]
            enc = quote(str(branch_name).strip(), safe="")
            client = get_shared_async_client()
            response = await client.get(
                f"{self.default_api_url}/repos/{owner}/{r}/branches/{enc}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug("GitHub get_branch %s: %s", branch_name, e)
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
            repo_url: GitHub repository URL
            branch: Branch name (if None, uses default_branch_hint or repo info)
            default_branch_hint: Optional default branch from DB to skip an extra API call
            
        Returns:
            Commit information dictionary or None if failed
        """
        if not self.api_token:
            logger.warning("Cannot fetch GitHub commits: API token not configured")
            return None
        
        try:
            repo_info = self.parse_github_url(repo_url)
            owner = repo_info['owner']
            repo = repo_info['repo']
            
            if branch is None:
                if default_branch_hint:
                    branch = default_branch_hint
                else:
                    repo_info_data = await self.get_repository_info(repo_url)
                    if repo_info_data:
                        branch = repo_info_data.get('default_branch', 'main')
                    else:
                        branch = 'main'
            
            client = get_shared_async_client()
            response = await client.get(
                f"{self.default_api_url}/repos/{owner}/{repo}/commits/{branch}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get GitHub commits: {e}")
            return None
    
    async def get_commit_diff(self, repo_url: str, from_commit: str, to_commit: str) -> Optional[Dict]:
        """
        Get diff between two commits using GitHub API.
        
        Args:
            repo_url: GitHub repository URL
            from_commit: Source commit SHA (or branch name)
            to_commit: Target commit SHA (or branch name)
            
        Returns:
            Dictionary with diff data, changed files, and stats, or None if failed
        """
        if not self.api_token:
            logger.warning("Cannot fetch commit diff: API token not configured")
            return None
        
        try:
            repo_info = self.parse_github_url(repo_url)
            owner = repo_info['owner']
            repo = repo_info['repo']
            
            client = get_shared_async_client()
            response = await client.get(
                f"{self.default_api_url}/repos/{owner}/{repo}/compare/{from_commit}...{to_commit}",
                headers=self.headers,
            )
            response.raise_for_status()
            compare_data = response.json()

            files = compare_data.get('files', [])
            changed_files = [f.get('filename', '') for f in files]

            diff_content = []
            for file_diff in files:
                filename = file_diff.get('filename', '')
                patch = file_diff.get('patch', '')
                status = file_diff.get('status', 'modified')

                if patch:
                    if not patch.startswith('diff --git'):
                        if status == 'added':
                            diff_header = f"diff --git a/{filename} b/{filename}\nnew file mode 100644\nindex 0000000..{file_diff.get('sha', '1111111')[:7]}\n--- /dev/null\n+++ b/{filename}\n"
                        elif status == 'removed':
                            diff_header = f"diff --git a/{filename} b/{filename}\ndeleted file mode 100644\nindex {file_diff.get('sha', '1111111')[:7]}..0000000\n--- a/{filename}\n+++ /dev/null\n"
                        else:
                            diff_header = f"diff --git a/{filename} b/{filename}\nindex {file_diff.get('sha', '1111111')[:7]}..{file_diff.get('sha', '2222222')[:7]} 100644\n--- a/{filename}\n+++ b/{filename}\n"
                        diff_content.append(diff_header + patch)
                    else:
                        diff_content.append(patch)

            additions = sum(f.get('additions', 0) for f in files)
            deletions = sum(f.get('deletions', 0) for f in files)

            return {
                "diff": '\n'.join(diff_content),
                "changed_files": [f for f in changed_files if f],
                "stats": {
                    "additions": additions,
                    "deletions": deletions,
                    "files_changed": len([f for f in changed_files if f])
                }
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error getting commit diff: {e.response.status_code} - {e.response.text}")
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
        Get diff for the latest commit on a branch using GitHub API.
        Compares latest commit with its parent.
        
        Args:
            repo_url: GitHub repository URL
            branch: Branch name (if None, uses default_branch_hint or default branch)
            default_branch_hint: Optional default branch from DB
            
        Returns:
            Dictionary with diff data, changed files, and stats, or None if failed
        """
        if not self.api_token:
            logger.warning("Cannot fetch latest diff: API token not configured")
            return None
        
        try:
            latest_commit = await self.get_latest_commit(
                repo_url, branch, default_branch_hint=default_branch_hint
            )
            if not latest_commit:
                logger.warning("No latest commit found")
                return None
            
            commit_sha = latest_commit.get('sha')
            parents = latest_commit.get('parents', [])
            
            if not commit_sha:
                logger.warning("Commit SHA not found in commit data")
                return None
            
            # If no parent (first commit), get the commit diff directly
            if not parents:
                repo_info = self.parse_github_url(repo_url)
                owner = repo_info['owner']
                repo = repo_info['repo']

                client = get_shared_async_client()
                response = await client.get(
                    f"{self.default_api_url}/repos/{owner}/{repo}/commits/{commit_sha}",
                    headers=self.headers,
                )
                response.raise_for_status()
                commit_data = response.json()

                files = commit_data.get('files', [])
                changed_files = [f.get('filename', '') for f in files]
                diff_content = []
                for file_diff in files:
                    filename = file_diff.get('filename', '')
                    patch = file_diff.get('patch', '')
                    status = file_diff.get('status', 'modified')

                    if patch:
                        if not patch.startswith('diff --git'):
                            if status == 'added':
                                diff_header = f"diff --git a/{filename} b/{filename}\nnew file mode 100644\nindex 0000000..{file_diff.get('sha', '1111111')[:7]}\n--- /dev/null\n+++ b/{filename}\n"
                            elif status == 'removed':
                                diff_header = f"diff --git a/{filename} b/{filename}\ndeleted file mode 100644\nindex {file_diff.get('sha', '1111111')[:7]}..0000000\n--- a/{filename}\n+++ /dev/null\n"
                            else:
                                diff_header = f"diff --git a/{filename} b/{filename}\nindex {file_diff.get('sha', '1111111')[:7]}..{file_diff.get('sha', '2222222')[:7]} 100644\n--- a/{filename}\n+++ b/{filename}\n"
                            diff_content.append(diff_header + patch)
                        else:
                            diff_content.append(patch)

                additions = sum(f.get('additions', 0) for f in files)
                deletions = sum(f.get('deletions', 0) for f in files)

                return {
                    "diff": '\n'.join(diff_content),
                    "changed_files": [f for f in changed_files if f],
                    "stats": {
                        "additions": additions,
                        "deletions": deletions,
                        "files_changed": len([f for f in changed_files if f])
                    }
                }

            parent_sha = parents[0].get('sha')
            return await self.get_commit_diff(repo_url, parent_sha, commit_sha)
                
        except Exception as e:
            logger.error(f"Failed to get latest diff: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
