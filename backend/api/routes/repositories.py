"""Repository management routes."""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime

# Add backend/ to path: backend/api/routes/ -> parent.parent.parent = backend/
_backend_path = Path(__file__).parent.parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

from api.models.repository import (
    RepositoryCreate, 
    RepositoryResponse,
    RepositoryUpdate,
    RiskThresholdUpdate,
    DiffResponse,
    BranchesResponse,
    BranchResponse
)
from services.gitlab_service import GitLabService
from services.github_service import GitHubService
from services.repository_vcs import (
    resolve_provider,
    effective_branch,
    normalize_diff_payload,
    reflag_default_branches,
    sanitize_branch_rows,
    ensure_branches_present,
)
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
            if GitLabService.is_gitlab_url(repo_data.url):
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
            
            # Verify API token is configured
            import os
            token_set = bool(os.getenv('GITLAB_API_TOKEN'))
            if not token_set:
                logger.warning("GITLAB_API_TOKEN is not set in environment variables")
            if not gitlab_service.api_token:
                logger.warning("GitLabService API token is not configured")
            
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
            
            # Verify API token is configured
            import os
            token_set = bool(os.getenv('GITHUB_API_TOKEN'))
            if not token_set:
                logger.warning("GITHUB_API_TOKEN is not set in environment variables")
            if not github_service.api_token:
                logger.warning("GitHubService API token is not configured")
            
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
        
        # Default branch from project/repo API (avoids listing every branch on connect)
        default_branch = None
        if provider == 'gitlab':
            gitlab_service = GitLabService()
            pinfo = await gitlab_service.get_project_info(repo_data.url)
            if pinfo:
                default_branch = pinfo.get('default_branch')
        elif provider == 'github':
            github_service = GitHubService()
            info = await github_service.get_repository_info(repo_data.url)
            if info:
                default_branch = info.get('default_branch')
        
        # Create repository in database
        repository_data = create_repository(
            url=repo_data.url,
            provider=provider,
            local_path=None,  # No local path needed - using API only
            selected_branch=default_branch,  # Set selected branch to default initially
            default_branch=default_branch
        )
        
        logger.info(f"Repository connected : {repository_data['id']} - {repo_data.url} ({provider})")
        
        return RepositoryResponse(**repository_data)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        raise HTTPException(status_code=400, detail=f"Failed to connect repository: {error_msg}")


@router.get("/{repo_id}/branches", response_model=BranchesResponse)
async def list_branches(
    repo_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=100),
    search: Optional[str] = Query(None, description="Filter branches (GitLab: server-side; GitHub: current page)"),
    fetch_all: bool = Query(
        True,
        description="If true (default), list all branches up to BRANCH_LIST_MAX_PAGES. Set false for one page only.",
    ),
):
    """
    List branches. Defaults match the UI dropdown: full list + accurate default from the provider.
    When fetch_all=false, default/selected branches are still injected if missing from the page.
    """
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    try:
        repo_url = repo["url"]
        provider = resolve_provider(repo_url, repo.get("provider"))
        stored_default = repo.get("default_branch")
        selected = repo.get("selected_branch")

        gitlab_service = GitLabService()
        github_service = GitHubService()

        live_default: Optional[str] = None
        if provider == "gitlab":
            pinfo = await gitlab_service.get_project_info(repo_url)
            if pinfo:
                live_default = pinfo.get("default_branch")
        elif provider == "github":
            ginfo = await github_service.get_repository_info(repo_url)
            if ginfo:
                live_default = ginfo.get("default_branch")

        effective_default = live_default or stored_default

        if provider == "gitlab":
            result = await gitlab_service.list_branches(
                repo_url,
                page=page,
                per_page=per_page,
                search=search,
                fetch_all=fetch_all,
            )
            branches = list(result.get("branches") or [])
            await ensure_branches_present(
                provider,
                repo_url,
                branches,
                {effective_default, selected, stored_default},
                gitlab_service=gitlab_service,
            )
        elif provider == "github":
            result = await github_service.list_branches(
                repo_url,
                page=page,
                per_page=per_page,
                search=search,
                fetch_all=fetch_all,
                default_branch_name=effective_default,
            )
            branches = list(result.get("branches") or [])
            await ensure_branches_present(
                provider,
                repo_url,
                branches,
                {effective_default, selected, stored_default},
                github_service=github_service,
            )
        else:
            raise HTTPException(
                status_code=501,
                detail=f"Branch listing via API is not supported for provider: {provider}"
            )

        reflag_default_branches(branches, effective_default)
        branches = sanitize_branch_rows(branches)

        selected_s = str(selected or "").strip()
        live_s = str(effective_default or "").strip()

        def _branch_sort_key(b: dict) -> tuple:
            n = b.get("name") or ""
            if live_s and n == live_s:
                return (0, n.lower())
            if selected_s and n == selected_s:
                return (1, n.lower())
            return (2, n.lower())

        branches.sort(key=_branch_sort_key)

        default_branch = live_default or stored_default
        if not default_branch:
            default_branch = next((b["name"] for b in branches if b.get("default")), None)

        return BranchesResponse(
            branches=[BranchResponse(**b) for b in branches],
            default_branch=default_branch,
            page=result.get("page", page),
            per_page=result.get("per_page", per_page),
            has_more=result.get("has_more", False),
            fetch_all=fetch_all,
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
        provider = resolve_provider(repo_url, repo.get("provider"))
        branch = effective_branch(branch, repo.get("selected_branch"), repo.get("default_branch"))
        default_hint = repo.get("default_branch")
        
        if provider == 'gitlab':
            gitlab_service = GitLabService()
            diff_data = await gitlab_service.get_latest_diff(
                repo_url, branch=branch, default_branch_hint=default_hint
            )
            
            if not diff_data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get diff via GitLab API. Check GITLAB_API_TOKEN and branch name."
                )
            
            norm = normalize_diff_payload(diff_data)
            logger.info(
                f"Diff data for repo {repo_id}, branch {branch}: diff_length={len(norm.get('diff', ''))}, "
                f"files={len(norm.get('changedFiles', []))}"
            )
            
            return DiffResponse(
                diff=norm["diff"],
                changedFiles=norm["changedFiles"],
                stats=norm["stats"],
                branch=branch
            )
            
        elif provider == 'github':
            github_service = GitHubService()
            diff_data = await github_service.get_latest_diff(
                repo_url, branch=branch, default_branch_hint=default_hint
            )
            
            if not diff_data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get diff via GitHub API. Check GITHUB_API_TOKEN and branch name."
                )
            
            norm = normalize_diff_payload(diff_data)
            logger.info(
                f"Diff data for repo {repo_id}, branch {branch}: diff_length={len(norm.get('diff', ''))}, "
                f"files={len(norm.get('changedFiles', []))}"
            )
            
            return DiffResponse(
                diff=norm["diff"],
                changedFiles=norm["changedFiles"],
                stats=norm["stats"],
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
            if GitLabService.is_gitlab_url(repo_url):
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
