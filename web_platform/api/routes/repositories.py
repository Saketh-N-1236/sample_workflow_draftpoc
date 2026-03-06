"""Repository management routes."""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from typing import List
from datetime import datetime

# Add web_platform to path
web_platform_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(web_platform_path))

from api.models.repository import (
    RepositoryCreate, 
    RepositoryResponse,
    RepositoryUpdate,
    RiskThresholdUpdate,
    DiffResponse,
    BranchesResponse,
    BranchResponse
)
from services.git_service import GitService
from services.gitlab_service import GitLabService
from services.github_service import GitHubService
from services.repository_db import (
    create_repository,
    get_repository_by_id,
    get_repository_by_url,
    list_repositories as db_list_repositories,
    update_repository as db_update_repository,
    create_repositories_table
)

router = APIRouter(prefix="/repositories", tags=["repositories"])

# Initialize logger at module level
import logging
logger = logging.getLogger(__name__)

git_service = GitService()

# Initialize database table on module load
try:
    create_repositories_table()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not initialize repositories table: {e}. Make sure to run create_repositories_table.py first.")


@router.get("", response_model=List[RepositoryResponse])
async def list_repositories():
    """
    List all connected repositories.
    
    Returns a list of all repositories that have been connected to the system.
    """
    try:
        repos = db_list_repositories()
        return [RepositoryResponse(**repo) for repo in repos]
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")


@router.post("/connect", response_model=RepositoryResponse)
async def connect_repository(repo_data: RepositoryCreate):
    """
    Connect to a git repository (no cloning - uses API only).
    
    Supports both GitHub and GitLab:
    - GitHub: Set GITHUB_API_TOKEN environment variable for private repos
    - GitLab: Set GITLAB_API_TOKEN environment variable for private repos
    - Uses API for all operations (no local clone needed)
    """
    try:
        # Validate URL format
        if not repo_data.url or not repo_data.url.strip():
            raise HTTPException(status_code=400, detail="Repository URL is required")
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Auto-detect provider if not provided
        provider = repo_data.provider
        if not provider:
            if git_service.is_gitlab_url(repo_data.url):
                provider = 'gitlab'
            elif GitHubService.is_github_url(repo_data.url):
                provider = 'github'
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not detect repository provider. Please specify 'github' or 'gitlab' in the provider field."
                )
        
        # Validate access based on provider
        if provider == 'gitlab':
            logger.info(f"Connecting to GitLab repository (API only): {repo_data.url}")
            
            gitlab_service = GitLabService()
            
            # Log token status for debugging
            import os
            token_set = bool(os.getenv('GITLAB_API_TOKEN'))
            logger.info(f"GITLAB_API_TOKEN is {'set' if token_set else 'NOT set'}")
            logger.info(f"GitLabService API token is {'set' if gitlab_service.api_token else 'NOT set'}")
            
            has_access = await gitlab_service.validate_access(repo_data.url)
            
            if not has_access:
                error_detail = "Access denied."
                if not gitlab_service.api_token:
                    error_detail += " GITLAB_API_TOKEN is not set in environment variables."
                else:
                    error_detail += " Token may be invalid or lack access to this repository."
                error_detail += " Check your .env file and ensure the token has 'read_api' and 'read_repository' scopes."
                
                logger.error(error_detail)
                raise HTTPException(status_code=403, detail=error_detail)
            
            logger.info(f"Successfully validated access to GitLab repository: {repo_data.url}")
            
        elif provider == 'github':
            logger.info(f"Connecting to GitHub repository (API only): {repo_data.url}")
            
            github_service = GitHubService()
            
            # Log token status for debugging
            import os
            token_set = bool(os.getenv('GITHUB_API_TOKEN'))
            logger.info(f"GITHUB_API_TOKEN is {'set' if token_set else 'NOT set'}")
            logger.info(f"GitHubService API token is {'set' if github_service.api_token else 'NOT set'}")
            
            has_access = await github_service.validate_access(repo_data.url)
            
            if not has_access:
                error_detail = "Access denied."
                if not github_service.api_token:
                    error_detail += " GITHUB_API_TOKEN is not set in environment variables."
                else:
                    error_detail += " Token may be invalid or lack access to this repository."
                error_detail += " Check your .env file and ensure the token has 'repo' scope."
                
                logger.error(error_detail)
                raise HTTPException(status_code=403, detail=error_detail)
            
            logger.info(f"Successfully validated access to GitHub repository: {repo_data.url}")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported provider: {provider}. Supported providers: 'github', 'gitlab'"
            )
        
        # Get default branch for the repository
        default_branch = None
        if provider == 'gitlab':
            gitlab_service = GitLabService()
            branches = await gitlab_service.list_branches(repo_data.url)
            if branches:
                default_branch = next((b['name'] for b in branches if b.get('default')), branches[0]['name'] if branches else None)
        elif provider == 'github':
            github_service = GitHubService()
            branches = await github_service.list_branches(repo_data.url)
            if branches:
                default_branch = next((b['name'] for b in branches if b.get('default')), branches[0]['name'] if branches else None)
        
        # Create repository in database
        repository_data = create_repository(
            url=repo_data.url,
            provider=provider,
            local_path=None,  # No local path needed - using API only
            selected_branch=default_branch,  # Set selected branch to default initially
            default_branch=default_branch
        )
        
        logger.info(f"Repository connected (no clone): {repository_data['id']} - {repo_data.url} ({provider})")
        
        return RepositoryResponse(**repository_data)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        raise HTTPException(status_code=400, detail=f"Failed to connect repository: {error_msg}")


@router.get("/{repo_id}/branches", response_model=BranchesResponse)
async def list_branches(repo_id: str):
    """
    List all branches in the repository.
    Uses GitLab/GitHub API for repositories (no local clone needed).
    """
    # Get repository from database
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    try:
        repo_url = repo["url"]
        provider = repo.get("provider")  # Get stored provider or detect
        
        # Determine provider
        if not provider:
            if git_service.is_gitlab_url(repo_url):
                provider = 'gitlab'
            elif GitHubService.is_github_url(repo_url):
                provider = 'github'
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not determine repository provider."
                )
        
        # Use appropriate API based on provider
        if provider == 'gitlab':
            gitlab_service = GitLabService()
            branches = await gitlab_service.list_branches(repo_url)
            
            if not branches:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to list branches via GitLab API. Check GITLAB_API_TOKEN."
                )
            
            # Find default branch
            default_branch = next((b['name'] for b in branches if b.get('default')), None)
            
            return BranchesResponse(
                branches=[BranchResponse(**b) for b in branches],
                default_branch=default_branch
            )
            
        elif provider == 'github':
            github_service = GitHubService()
            branches = await github_service.list_branches(repo_url)
            
            if not branches:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to list branches via GitHub API. Check GITHUB_API_TOKEN."
                )
            
            # Find default branch
            default_branch = next((b['name'] for b in branches if b.get('default')), None)
            
            return BranchesResponse(
                branches=[BranchResponse(**b) for b in branches],
                default_branch=default_branch
            )
        else:
            raise HTTPException(
                status_code=501,
                detail=f"Branch listing via API is not supported for provider: {provider}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list branches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list branches: {str(e)}")


@router.get("/{repo_id}/diff", response_model=DiffResponse)
async def get_diff(repo_id: str, branch: str = None):
    """
    Get git diff for the latest commit on a specific branch.
    Uses GitLab/GitHub API (no local clone needed).
    
    Args:
        repo_id: Repository ID
        branch: Branch name (optional, defaults to selected branch or default branch)
    """
    # Get repository from database
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    try:
        repo_url = repo["url"]
        provider = repo.get("provider")  # Get stored provider
        
        # Use provided branch, or selected_branch, or default_branch
        if not branch:
            branch = repo.get("selected_branch") or repo.get("default_branch")
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Determine provider
        if not provider:
            if git_service.is_gitlab_url(repo_url):
                provider = 'gitlab'
            elif GitHubService.is_github_url(repo_url):
                provider = 'github'
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not determine repository provider."
                )
        
        # Use appropriate API based on provider
        if provider == 'gitlab':
            gitlab_service = GitLabService()
            diff_data = await gitlab_service.get_latest_diff(repo_url, branch=branch)
            
            if not diff_data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get diff via GitLab API. Check GITLAB_API_TOKEN and branch name."
                )
            
            logger.info(f"Diff data for repo {repo_id}, branch {branch}: diff_length={len(diff_data.get('diff', ''))}, files={len(diff_data.get('changed_files', []))}")
            
            return DiffResponse(
                diff=diff_data.get("diff", ""),
                changedFiles=diff_data.get("changed_files", []),
                stats=diff_data.get("stats", {}),
                branch=branch
            )
            
        elif provider == 'github':
            github_service = GitHubService()
            diff_data = await github_service.get_latest_diff(repo_url, branch=branch)
            
            if not diff_data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get diff via GitHub API. Check GITHUB_API_TOKEN and branch name."
                )
            
            logger.info(f"Diff data for repo {repo_id}, branch {branch}: diff_length={len(diff_data.get('diff', ''))}, files={len(diff_data.get('changed_files', []))}")
            
            return DiffResponse(
                diff=diff_data.get("diff", ""),
                changedFiles=diff_data.get("changed_files", []),
                stats=diff_data.get("stats", {}),
                branch=branch
            )
        else:
            raise HTTPException(
                status_code=501,
                detail=f"Diff via API is not supported for provider: {provider}"
            )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Failed to get diff: {str(e)}"
        logger.error(f"Diff error for repo {repo_id}: {error_detail}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/{repo_id}")
async def get_repository(repo_id: str):
    """Get repository information."""
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    return RepositoryResponse(**repo)


@router.put("/{repo_id}", response_model=RepositoryResponse)
async def update_repository(repo_id: str, repo_update: RepositoryUpdate):
    """
    Update repository settings (e.g., selected branch).
    
    Args:
        repo_id: Repository ID
        repo_update: Update data (e.g., selected_branch)
    """
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    try:
        updated_repo = db_update_repository(
            repo_id=repo_id,
            selected_branch=repo_update.selected_branch
        )
        
        if not updated_repo:
            raise HTTPException(status_code=500, detail="Failed to update repository")
        
        return RepositoryResponse(**updated_repo)
    except Exception as e:
        logger.error(f"Failed to update repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update repository: {str(e)}")


@router.patch("/{repo_id}/threshold", response_model=RepositoryResponse)
async def update_risk_threshold(repo_id: str, threshold_update: RiskThresholdUpdate):
    """
    Update the risk threshold for a repository.
    
    Args:
        repo_id: Repository ID
        threshold_update: Request body with threshold value
    """
    threshold = threshold_update.threshold
    
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    # Validate threshold - allow None (disables risk analysis) or positive integer
    if threshold is not None and threshold < 1:
        raise HTTPException(status_code=400, detail="Risk threshold must be at least 1, or None to disable risk analysis")
    
    try:
        # Update the repository with new threshold
        # Pass _update_risk_threshold=True to allow setting None (disables risk analysis)
        updated_repo = db_update_repository(
            repo_id=repo_id,
            risk_threshold=threshold,
            _update_risk_threshold=True
        )
        
        if not updated_repo:
            raise HTTPException(status_code=500, detail="Failed to update risk threshold")
        
        # Verify the update by fetching the repository again
        verified_repo = get_repository_by_id(repo_id)
        if verified_repo:
            logger.info(f"Risk threshold updated for repo {repo_id}: {verified_repo.get('risk_threshold')}")
            return RepositoryResponse(**verified_repo)
        else:
            return RepositoryResponse(**updated_repo)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update risk threshold: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update risk threshold: {str(e)}")


@router.post("/{repo_id}/refresh", response_model=RepositoryResponse)
async def refresh_repository(repo_id: str):
    """
    Refresh repository connection and validate access.
    
    Re-validates the repository connection, checks access permissions,
    and updates the last refreshed timestamp.
    """
    # Get repository from database
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    try:
        repo_url = repo["url"]
        provider = repo.get("provider")
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Determine provider if not stored
        if not provider:
            if git_service.is_gitlab_url(repo_url):
                provider = 'gitlab'
            elif GitHubService.is_github_url(repo_url):
                provider = 'github'
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not determine repository provider."
                )
        
        # Re-validate access based on provider
        if provider == 'gitlab':
            gitlab_service = GitLabService()
            has_access = await gitlab_service.validate_access(repo_url)
            
            if not has_access:
                error_detail = "Access denied."
                if not gitlab_service.api_token:
                    error_detail += " GITLAB_API_TOKEN is not set in environment variables."
                else:
                    error_detail += " Token may be invalid or lack access to this repository."
                
                logger.error(error_detail)
                raise HTTPException(status_code=403, detail=error_detail)
            
            logger.info(f"Successfully refreshed GitLab repository: {repo_url}")
            
        elif provider == 'github':
            github_service = GitHubService()
            has_access = await github_service.validate_access(repo_url)
            
            if not has_access:
                error_detail = "Access denied."
                if not github_service.api_token:
                    error_detail += " GITHUB_API_TOKEN is not set in environment variables."
                else:
                    error_detail += " Token may be invalid or lack access to this repository."
                
                logger.error(error_detail)
                raise HTTPException(status_code=403, detail=error_detail)
            
            logger.info(f"Successfully refreshed GitHub repository: {repo_url}")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported provider: {provider}. Supported providers: 'github', 'gitlab'"
            )
        
        # Update repository metadata in database
        from datetime import datetime
        updated_repo = db_update_repository(
            repo_id=repo_id,
            last_refreshed=datetime.now()
        )
        
        if not updated_repo:
            raise HTTPException(status_code=500, detail="Failed to update repository")
        
        return RepositoryResponse(**updated_repo)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to refresh repository: {str(e)}")
