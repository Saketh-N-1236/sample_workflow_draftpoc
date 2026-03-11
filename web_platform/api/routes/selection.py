"""Test selection routes."""

import sys
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from datetime import datetime

# Add web_platform to path
web_platform_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(web_platform_path))

from api.models.repository import SelectionResponse
from api.models.semantic import SemanticConfig
from services.selection_service import SelectionService
from services.repository_db import get_repository_by_id, update_repository

router = APIRouter(prefix="/repositories", tags=["selection"])
selection_service = SelectionService()
logger = logging.getLogger(__name__)


@router.post("/{repo_id}/select-tests", response_model=SelectionResponse)
async def select_tests(repo_id: str):
    """Run test selection using diff from GitLab/GitHub API."""
    # Get repository from database
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    try:
        repo_url = repo["url"]
        provider = repo.get("provider")  # Get stored provider
        # Get risk threshold - preserve None if disabled, convert to int if set
        risk_threshold = repo.get("risk_threshold")
        if risk_threshold is not None:
            risk_threshold = int(risk_threshold)  # Ensure it's an integer
        # If risk_threshold is None, keep it as None (risk analysis disabled)
        
        # Get diff from API (no local clone needed)
        from services.gitlab_service import GitLabService
        from services.github_service import GitHubService
        
        # Use selected branch or default branch
        branch = repo.get("selected_branch") or repo.get("default_branch")
        
        # Determine provider
        if not provider:
            from services.gitlab_service import GitLabService
            if GitLabService.is_gitlab_url(repo_url):
                provider = 'gitlab'
            elif GitHubService.is_github_url(repo_url):
                provider = 'github'
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not determine repository provider."
                )
        
        # Use appropriate API based on provider
        logger.info(f"Getting diff for provider: {provider}, branch: {branch}")
        if provider == 'gitlab':
            gitlab_service = GitLabService()
            diff_data = await gitlab_service.get_latest_diff(repo_url, branch=branch)
            
            if not diff_data:
                logger.error("Failed to get diff via GitLab API")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get diff via GitLab API for test selection."
                )
            
            # Normalize keys (GitLab uses changed_files, but we want changedFiles for consistency)
            if 'changed_files' in diff_data and 'changedFiles' not in diff_data:
                diff_data['changedFiles'] = diff_data.pop('changed_files')
            
            logger.info(f"Got diff data: {len(diff_data.get('diff', ''))} chars, {len(diff_data.get('changedFiles', diff_data.get('changed_files', [])))} files")
            
        elif provider == 'github':
            github_service = GitHubService()
            diff_data = await github_service.get_latest_diff(repo_url, branch=branch)
            
            if not diff_data:
                logger.error("Failed to get diff via GitHub API")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get diff via GitHub API for test selection."
                )
            
            # Normalize keys (GitHub uses changed_files, but we want changedFiles for consistency)
            if 'changed_files' in diff_data and 'changedFiles' not in diff_data:
                diff_data['changedFiles'] = diff_data.pop('changed_files')
            
            logger.info(f"Got diff data: {len(diff_data.get('diff', ''))} chars, {len(diff_data.get('changedFiles', []))} files")
        else:
            raise HTTPException(
                status_code=501,
                detail=f"Test selection via API is not supported for provider: {provider}"
            )
        
        # Risk Analysis: Check if changed files exceed threshold
        # If risk_threshold is None, skip risk analysis and proceed with normal selection
        changed_files_count = len(diff_data.get('changedFiles', []))
        threshold_exceeded = False
        if risk_threshold is not None:
            threshold_exceeded = changed_files_count > risk_threshold
        
        if threshold_exceeded:
            logger.warning(f"Risk threshold exceeded: {changed_files_count} files changed (threshold: {risk_threshold})")
            
            # Get total test count from database
            # Try to get from bound test repositories first
            total_tests_in_db = 0
            try:
                from services.repository_db import get_test_repository_bindings
                bound_repos = get_test_repository_bindings(repo_id)
                if bound_repos:
                    from deterministic.db_connection import get_connection_with_schema
                    for repo in bound_repos:
                        schema_name = repo.get('schema_name')
                        if schema_name:
                            try:
                                with get_connection_with_schema(schema_name) as conn:
                                    with conn.cursor() as cursor:
                                        cursor.execute(f"SELECT COUNT(*) FROM {schema_name}.test_registry")
                                        count = cursor.fetchone()[0]
                                        total_tests_in_db += count
                                        logger.info(f"Threshold exceeded - Schema {schema_name} has {count} tests")
                            except Exception as e:
                                logger.warning(f"Failed to get test count from schema {schema_name}: {e}")
            except Exception as e:
                logger.warning(f"Failed to get bound test repositories: {e}")
            
            # Fallback to default schema if no bound repos or count is still 0
            if total_tests_in_db == 0:
                try:
                    from deterministic.db_connection import get_connection, DB_SCHEMA
                    with get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.test_registry")
                            total_tests_in_db = cursor.fetchone()[0]
                            logger.info(f"Threshold exceeded - Using default schema {DB_SCHEMA}, found {total_tests_in_db} tests")
                except Exception as e:
                    logger.error(f"Failed to get test count from default schema: {e}", exc_info=True)
            
            import time
            start_time = time.time()
            
            # Audit logging for threshold exceeded case
            try:
                from services.audit_service import log_selection_run
                execution_time_ms = int((time.time() - start_time) * 1000)
                log_selection_run(
                    repository_id=repo_id,
                    changed_files_count=changed_files_count,
                    selected_tests_count=total_tests_in_db,  # All tests will run
                    confidence_scores={'high': 0, 'medium': 0, 'low': 0},  # No selection made
                    llm_used=False,
                    execution_time_ms=execution_time_ms,
                    threshold_exceeded=True
                )
            except Exception as e:
                logger.warning(f"Failed to log audit entry for threshold exceeded case: {e}")
            
            # Return special response indicating all tests should run
            return SelectionResponse(
                totalTests=total_tests_in_db,
                totalTestsInDb=total_tests_in_db,  # Include total tests in database
                astMatches=0,
                semanticMatches=0,
                tests=[],  # Empty list - all tests will be executed
                semanticMatchDetails=[],
                astMatchDetails=[],
                overlapCount=0,
                embeddingStatus=None,
                semanticConfig=None,
                riskAnalysis={
                    "exceeded": True,
                    "changed_files": changed_files_count,
                    "threshold": risk_threshold,
                    "message": f"Threshold exceeded ({changed_files_count} files changed, threshold: {risk_threshold}) - All tests will be executed"
                },
                selectionDisabled=True
            )
        
        # Run selection with diff from API (normal flow, pass repo_id for audit logging)
        results = await selection_service.run_selection_with_diff(diff_data, repository_id=repo_id)
        
        # Extract total tests count from results
        total_tests_in_db = results.get("total_tests_in_db", 0)
        logger.info(f"Returning selection results: total_tests={results.get('total_tests', 0)}, total_tests_in_db={total_tests_in_db}, tests_count={len(results.get('tests', []))}")
        logger.info(f"Results keys: {list(results.keys())}")
        if results.get('tests'):
            logger.info(f"First test sample: {results['tests'][0]}")
        else:
            logger.warning("No tests in results!")
        
        # If total_tests_in_db is still 0, try to calculate it directly from bound repositories
        if total_tests_in_db == 0:
            logger.warning("total_tests_in_db is 0, attempting to calculate from bound repositories...")
            try:
                from services.repository_db import get_test_repository_bindings
                bound_repos = get_test_repository_bindings(repo_id)
                if bound_repos:
                    from deterministic.db_connection import get_connection_with_schema
                    for repo in bound_repos:
                        schema_name = repo.get('schema_name')
                        if schema_name:
                            try:
                                with get_connection_with_schema(schema_name) as conn:
                                    with conn.cursor() as cursor:
                                        cursor.execute(f"SELECT COUNT(*) FROM {schema_name}.test_registry")
                                        count = cursor.fetchone()[0]
                                        total_tests_in_db += count
                                        logger.info(f"Fallback calculation - Schema {schema_name} has {count} tests")
                            except Exception as e:
                                logger.warning(f"Fallback failed for schema {schema_name}: {e}")
            except Exception as e:
                logger.warning(f"Fallback calculation failed: {e}")
        
        response = SelectionResponse(
            totalTests=results.get("total_tests", 0),
            totalTestsInDb=total_tests_in_db,  # Add total tests in database
            astMatches=results.get("ast_matches", 0),
            semanticMatches=results.get("semantic_matches", 0),
            tests=results.get("tests", []),
            semanticMatchDetails=results.get("semantic_match_details", []),
            astMatchDetails=results.get("ast_match_details", []),
            overlapCount=results.get("overlap_count", 0),
            embeddingStatus=results.get("embedding_status"),
            semanticConfig=results.get("semantic_config"),
            riskAnalysis={
                "exceeded": False,
                "changed_files": changed_files_count,
                "threshold": risk_threshold
            },
            selectionDisabled=False,
            llmScores=results.get("llm_scores"),
            llmInputOutput=results.get("llm_input_output"),
            confidenceDistribution=results.get("confidence_distribution")
        )
        logger.info(f"SelectionResponse created: totalTests={response.totalTests}, totalTestsInDb={response.totalTestsInDb}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test selection failed: {str(e)}")


@router.get("/{repo_id}/results")
async def get_results(repo_id: str):
    """Get all results for a repository."""
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Returns selection results - analysis results are available via /api/analysis/{repo_id}/results
    return {"analysis": None, "selection": None}


@router.post("/{repo_id}/configure-semantic")
async def configure_semantic_search(repo_id: str, config: SemanticConfig):
    """Configure semantic search parameters for a repository."""
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    try:
        # Validate configuration
        if config.similarity_threshold is not None:
            if not (0.0 <= config.similarity_threshold <= 1.0):
                raise HTTPException(
                    status_code=400,
                    detail="Similarity threshold must be between 0.0 and 1.0"
                )
        
        if config.max_results < 1:
            raise HTTPException(
                status_code=400,
                detail="Max results must be at least 1"
            )
        
        if config.top_k is not None and config.top_k < 1:
            raise HTTPException(
                status_code=400,
                detail="Top K must be at least 1"
            )
        
        if config.top_p is not None:
            if not (0.0 <= config.top_p <= 1.0):
                raise HTTPException(
                    status_code=400,
                    detail="Top P must be between 0.0 and 1.0"
                )
        
        if hasattr(config, 'quality_threshold') and config.quality_threshold is not None:
            if not (0.0 <= config.quality_threshold <= 1.0):
                raise HTTPException(
                    status_code=400,
                    detail="Quality threshold must be between 0.0 and 1.0"
                )
        
        # Store configuration in database
        config_dict = config.dict()
        updated_repo = update_repository(repo_id, semantic_config=config_dict)
        
        if not updated_repo:
            raise HTTPException(
                status_code=500,
                detail="Failed to save semantic search configuration"
            )
        
        # Return configuration as confirmation
        return {
            "status": "success",
            "message": "Semantic search configuration updated",
            "config": config_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure semantic search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure semantic search: {str(e)}"
        )


@router.get("/{repo_id}/semantic-config")
async def get_semantic_config(repo_id: str):
    """Get semantic search configuration for a repository."""
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    semantic_config = repo.get("semantic_config")
    
    if semantic_config is None:
        # Return default configuration if none is saved
        return {
            "similarity_threshold": None,
            "max_results": 10000,
            "use_adaptive_thresholds": True,
            "use_multi_query": False,
            "top_k": None,
            "top_p": None
        }
    
    return semantic_config
