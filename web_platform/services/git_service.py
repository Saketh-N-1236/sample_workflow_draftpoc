"""Git service for repository operations."""

import os
import git
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class GitService:
    """Service for git repository operations."""
    
    def __init__(self, storage_path: str = None):
        """Initialize git service."""
        if storage_path is None:
            # Default to web_platform/repos
            self.storage_path = Path(__file__).parent.parent / "repos"
        else:
            self.storage_path = Path(storage_path)
        
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Lazy import GitLab service to avoid circular dependencies
        self._gitlab_service = None
    
    def _get_gitlab_service(self):
        """Lazy load GitLab service."""
        if self._gitlab_service is None:
            try:
                from services.gitlab_service import GitLabService
                self._gitlab_service = GitLabService()
            except Exception as e:
                logger.warning(f"Could not initialize GitLab service: {e}")
                return None
        return self._gitlab_service
    
    @staticmethod
    def is_gitlab_url(repo_url: str) -> bool:
        """
        Check if URL is a GitLab repository URL.
        
        Args:
            repo_url: Repository URL
            
        Returns:
            True if URL is from GitLab
        """
        try:
            from services.gitlab_service import GitLabService
            return GitLabService.is_gitlab_url(repo_url)
        except ImportError:
            # Fallback check
            return 'gitlab.com' in repo_url.lower() or 'gitlab' in repo_url.lower()
    
    async def clone_repository(self, repo_url: str, repo_id: str) -> str:
        """
        Clone a git repository (supports both GitHub and GitLab).
        
        Args:
            repo_url: Git repository URL
            repo_id: Unique identifier for the repository
            
        Returns:
            Local path to the cloned repository
        """
        repo_path = self.storage_path / repo_id
        
        # For GitLab URLs, optionally validate access first
        if self.is_gitlab_url(repo_url):
            gitlab_service = self._get_gitlab_service()
            if gitlab_service:
                try:
                    has_access = await gitlab_service.validate_access(repo_url)
                    if not has_access:
                        logger.warning(f"GitLab access validation failed for {repo_url}. Proceeding with clone anyway.")
                except Exception as e:
                    logger.warning(f"GitLab access validation error: {e}. Proceeding with clone.")
        
        try:
            if repo_path.exists():
                # Repository already exists, update it
                repo = git.Repo(repo_path)
                if repo.remotes.origin:
                    repo.remotes.origin.pull()
            else:
                # Clone new repository
                # For GitLab, ensure URL format is correct and add token if available
                if self.is_gitlab_url(repo_url):
                    if not repo_url.endswith('.git'):
                        # GitLab URLs work better with .git suffix
                        if not repo_url.endswith('/'):
                            repo_url = repo_url + '.git'
                    
                    # Add token to URL for authentication if available
                    gitlab_service = self._get_gitlab_service()
                    if gitlab_service and gitlab_service.api_token:
                        # Insert token into URL: http://gitlab.com/repo.git -> http://oauth2:TOKEN@gitlab.com/repo.git
                        from urllib.parse import urlparse, urlunparse
                        parsed = urlparse(repo_url)
                        # Use oauth2 as username (GitLab supports this)
                        auth_url = urlunparse((
                            parsed.scheme,
                            f"oauth2:{gitlab_service.api_token}@{parsed.netloc}",
                            parsed.path,
                            parsed.params,
                            parsed.query,
                            parsed.fragment
                        ))
                        repo = git.Repo.clone_from(auth_url, repo_path)
                    else:
                        repo = git.Repo.clone_from(repo_url, repo_path)
                else:
                    # GitHub or other Git repository
                    repo = git.Repo.clone_from(repo_url, repo_path)
            
            return str(repo_path)
        except git.exc.GitCommandError as e:
            error_msg = str(e)
            if self.is_gitlab_url(repo_url):
                error_msg += " For GitLab repositories, ensure GITLAB_API_TOKEN is set if the repo is private."
            raise Exception(f"Git command failed: {error_msg}. Check repository URL and access permissions.")
        except Exception as e:
            raise Exception(f"Failed to clone repository: {str(e)}")
    
    async def list_branches(self, repo_path: str) -> List[Dict]:
        """
        List all branches in the repository.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            List of branch dictionaries with name and commit info
        """
        import logging
        logger = logging.getLogger(__name__)
        
        repo_path_obj = Path(repo_path)
        if not repo_path_obj.exists():
            raise Exception(f"Repository path does not exist: {repo_path}")
        
        try:
            repo = git.Repo(repo_path)
        except git.exc.InvalidGitRepositoryError:
            raise Exception(f"Invalid git repository at {repo_path}")
        
        branches = []
        try:
            # Get all remote branches
            for ref in repo.remotes.origin.refs:
                if ref.name.startswith('origin/'):
                    branch_name = ref.name.replace('origin/', '')
                    # Skip HEAD reference
                    if branch_name != 'HEAD':
                        try:
                            commit = ref.commit
                            branches.append({
                                'name': branch_name,
                                'default': branch_name == repo.head.ref.name if hasattr(repo.head, 'ref') else False,
                                'protected': False,  # GitPython doesn't provide this info
                                'commit_id': commit.hexsha[:8],
                                'commit_message': commit.message.split('\n')[0][:50] if commit.message else ''
                            })
                        except Exception as e:
                            logger.debug(f"Could not get commit info for branch {branch_name}: {e}")
            
            # Also include local branches
            for branch in repo.branches:
                branch_name = branch.name
                # Skip if already added from remote
                if not any(b['name'] == branch_name for b in branches):
                    try:
                        commit = branch.commit
                        branches.append({
                            'name': branch_name,
                            'default': branch_name == repo.head.ref.name if hasattr(repo.head, 'ref') else False,
                            'protected': False,
                            'commit_id': commit.hexsha[:8],
                            'commit_message': commit.message.split('\n')[0][:50] if commit.message else ''
                        })
                    except Exception as e:
                        logger.debug(f"Could not get commit info for local branch {branch_name}: {e}")
            
            # Sort by name
            branches.sort(key=lambda x: x['name'])
            
            return branches
        except Exception as e:
            logger.error(f"Failed to list branches: {e}")
            return []
    
    async def get_latest_diff(self, repo_path: str, branch: str = None) -> Dict:
        """
        Get git diff for the latest commit on a specific branch.
        
        Args:
            repo_path: Path to the repository
            branch: Branch name (if None, uses current HEAD branch)
            
        Returns:
            Dictionary with diff content, changed files, and stats
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Validate path exists
        repo_path_obj = Path(repo_path)
        if not repo_path_obj.exists():
            raise Exception(f"Repository path does not exist: {repo_path}")
        
        try:
            repo = git.Repo(repo_path)
        except git.exc.InvalidGitRepositoryError:
            raise Exception(f"Invalid git repository at {repo_path}")
        except Exception as e:
            raise Exception(f"Failed to open repository at {repo_path}: {str(e)}")
        
        # Check if repository is valid
        if repo.bare:
            return {
                "diff": "",
                "changed_files": [],
                "stats": {}
            }
        
        # Switch to specified branch if provided
        original_branch = None
        if branch:
            try:
                # Fetch latest from remote
                try:
                    repo.remotes.origin.fetch()
                except Exception as e:
                    logger.debug(f"Could not fetch from remote: {e}")
                
                # Save current branch
                try:
                    original_branch = repo.head.ref.name if hasattr(repo.head, 'ref') else None
                except:
                    pass
                
                # Check if branch exists locally or remotely
                branch_exists = False
                try:
                    # Check local branches
                    if branch in [b.name for b in repo.branches]:
                        repo.git.checkout(branch)
                        branch_exists = True
                    # Check remote branches
                    elif f'origin/{branch}' in [ref.name for ref in repo.refs]:
                        # Create local branch tracking remote
                        repo.git.checkout('-b', branch, f'origin/{branch}')
                        branch_exists = True
                except Exception as e:
                    logger.warning(f"Could not checkout branch {branch}: {e}")
                
                if not branch_exists:
                    logger.warning(f"Branch {branch} not found, using current branch")
            except Exception as e:
                logger.warning(f"Failed to switch to branch {branch}: {e}")
        
        # Check if repository has any commits
        try:
            # Try to get the commit count
            commit_count = len(list(repo.iter_commits()))
            if commit_count == 0:
                # Empty repository - no commits
                return {
                    "diff": "",
                    "changed_files": [],
                    "stats": {
                        "additions": 0,
                        "deletions": 0,
                        "files_changed": 0
                    }
                }
        except Exception as e:
            logger.warning(f"Could not count commits: {e}")
            # Continue to try getting diff anyway
        
        # Get latest commit
        try:
            head = repo.head
            if not head.is_valid():
                return {
                    "diff": "",
                    "changed_files": [],
                    "stats": {
                        "additions": 0,
                        "deletions": 0,
                        "files_changed": 0
                    }
                }
        except Exception as e:
            logger.warning(f"HEAD is not valid: {e}")
            return {
                "diff": "",
                "changed_files": [],
                "stats": {
                    "additions": 0,
                    "deletions": 0,
                    "files_changed": 0
                }
            }
        
        # Get diff between HEAD and HEAD~1
        try:
            commits = list(repo.iter_commits(max_count=2))
            if not commits:
                return {
                    "diff": "",
                    "changed_files": [],
                    "stats": {
                        "additions": 0,
                        "deletions": 0,
                        "files_changed": 0
                    }
                }
            
            diff = None
            diff_text = ""
            
            if len(commits) == 1:
                # Only one commit - compare with empty tree
                try:
                    diff = commits[0].diff(git.NULL_TREE)
                    diff_text = repo.git.diff(git.NULL_TREE, commits[0].hexsha)
                except Exception as e:
                    logger.warning(f"Failed to diff with NULL_TREE: {e}")
                    # Try alternative: get diff text directly
                    try:
                        diff_text = repo.git.diff(git.NULL_TREE, commits[0].hexsha)
                        # Parse diff text to get file list
                        diff = commits[0].diff(git.NULL_TREE) if diff_text else []
                    except Exception as e2:
                        logger.warning(f"Failed to get commit diff: {e2}")
                        diff = []
                        diff_text = ""
            else:
                # Multiple commits - compare latest with previous
                try:
                    diff = commits[0].diff(commits[1])
                    # Try to get diff text with unified format
                    try:
                        diff_text = repo.git.diff(commits[1].hexsha, commits[0].hexsha, unified=3)
                    except:
                        try:
                            diff_text = repo.git.diff(commits[1].hexsha, commits[0].hexsha)
                        except:
                            diff_text = ""
                except Exception as e:
                    logger.warning(f"Failed to diff commits: {e}")
                    # Fallback: try to get diff from HEAD
                    try:
                        diff = repo.head.commit.diff(commits[1])
                        try:
                            diff_text = repo.git.diff(commits[1].hexsha, 'HEAD', unified=3)
                        except:
                            diff_text = repo.git.diff(commits[1].hexsha, 'HEAD')
                    except Exception as e2:
                        logger.warning(f"Fallback diff failed: {e2}")
                        diff = []
                        diff_text = ""
            
            # If diff is None or empty, try working directory diff
            if diff is None or (not diff and not diff_text):
                try:
                    diff = repo.head.commit.diff()
                    diff_text = repo.git.diff('HEAD')
                except Exception as e3:
                    logger.warning(f"Working directory diff failed: {e3}")
                    diff = []
                    diff_text = ""
            
        except Exception as e:
            logger.error(f"Unexpected error getting diff: {e}", exc_info=True)
            # Return empty diff instead of failing
            return {
                "diff": "",
                "changed_files": [],
                "stats": {
                    "additions": 0,
                    "deletions": 0,
                    "files_changed": 0
                }
            }
        
        # Process diff items
        changed_files = []
        additions = 0
        deletions = 0
        
        if diff:
            try:
                for item in diff:
                    file_path = item.b_path if item.b_path else item.a_path
                    if file_path:
                        changed_files.append(file_path)
                    # Fix: Check if attributes exist and use getattr with default
                    if hasattr(item, 'insertions'):
                        additions += item.insertions or 0
                    if hasattr(item, 'deletions'):
                        deletions += item.deletions or 0
            except Exception as e:
                logger.warning(f"Error processing diff items: {e}")
                # Continue processing even if stats fail
        
        # If we have changed files but no diff text, generate it from diff items
        if changed_files and not diff_text:
            logger.warning("Have changed files but no diff text, generating from diff items")
            try:
                # Generate diff text from diff items
                diff_parts = []
                for item in diff:
                    try:
                        # Get patch for this item
                        if hasattr(item, 'diff'):
                            patch = item.diff.decode('utf-8') if hasattr(item.diff, 'decode') else str(item.diff)
                            if patch:
                                diff_parts.append(patch)
                    except Exception as e:
                        logger.debug(f"Could not get patch for {item}: {e}")
                
                if diff_parts:
                    diff_text = '\n'.join(diff_parts)
                else:
                    # Last resort: generate per-file diffs
                    logger.info("Trying per-file diff generation")
                    for file_path in changed_files[:20]:  # Limit to first 20 files
                        try:
                            if len(commits) > 1:
                                file_diff = repo.git.diff(commits[1].hexsha, commits[0].hexsha, '--', file_path)
                            else:
                                file_diff = repo.git.diff(git.NULL_TREE, commits[0].hexsha, '--', file_path)
                            if file_diff:
                                diff_parts.append(file_diff)
                        except Exception as e:
                            logger.debug(f"Could not get diff for {file_path}: {e}")
                    diff_text = '\n'.join(diff_parts)
            except Exception as e:
                logger.warning(f"Failed to generate diff text from items: {e}")
        
        result = {
            "diff": diff_text or "",
            "changed_files": changed_files,
            "stats": {
                "additions": additions,
                "deletions": deletions,
                "files_changed": len(changed_files)
            }
        }
        
        # Log for debugging
        logger.info(f"Generated diff: {len(result['diff'])} chars, {len(result['changed_files'])} files, stats={result['stats']}")
        if not result['diff'] and result['changed_files']:
            logger.warning(f"WARNING: Diff text is empty but {len(result['changed_files'])} files changed!")
        
        return result
