"""Test selection routes."""

import sys
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from datetime import datetime

# Add backend/ to path: backend/api/routes/ -> parent.parent.parent = backend/
_backend_path = Path(__file__).parent.parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

from api.models.repository import SelectionResponse
from services.selection_service import SelectionService
from services.repository_db import get_repository_by_id
from services.repository_vcs import resolve_provider, effective_branch, normalize_diff_payload
from services.gitlab_service import GitLabService
from services.github_service import GitHubService

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
        provider = resolve_provider(repo_url, repo.get("provider"))
        branch = effective_branch(None, repo.get("selected_branch"), repo.get("default_branch"))
        default_hint = repo.get("default_branch")
        # Get risk threshold - preserve None if disabled, convert to int if set
        risk_threshold = repo.get("risk_threshold")
        if risk_threshold is not None:
            risk_threshold = int(risk_threshold)  # Ensure it's an integer
        # If risk_threshold is None, keep it as None (risk analysis disabled)
        
        logger.info(f"Getting diff for provider: {provider}, branch: {branch}")
        if provider == 'gitlab':
            gitlab_service = GitLabService()
            diff_data = await gitlab_service.get_latest_diff(
                repo_url, branch=branch, default_branch_hint=default_hint
            )
            
            if not diff_data:
                logger.error("Failed to get diff via GitLab API")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get diff via GitLab API for test selection."
                )
            
        elif provider == 'github':
            github_service = GitHubService()
            diff_data = await github_service.get_latest_diff(
                repo_url, branch=branch, default_branch_hint=default_hint
            )
            
            if not diff_data:
                logger.error("Failed to get diff via GitHub API")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get diff via GitHub API for test selection."
                )
        else:
            raise HTTPException(
                status_code=501,
                detail=f"Test selection via API is not supported for provider: {provider}"
            )

        diff_data = normalize_diff_payload(diff_data)
        logger.info(
            f"Got diff data: {len(diff_data.get('diff', ''))} chars, "
            f"{len(diff_data.get('changedFiles', []))} files"
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
        logger.info(
            "select-tests: total_tests=%s total_tests_in_db=%s returned=%s",
            results.get("total_tests", 0),
            total_tests_in_db,
            len(results.get("tests", [])),
        )
        logger.debug("Selection result keys: %s", list(results.keys()))
        if results.get("tests"):
            logger.debug("First test id=%s", results["tests"][0].get("test_id"))
        else:
            logger.warning("No tests in selection results")
        
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
            selectionFunnel=results.get("selection_funnel"),
            semanticSearchCandidates=results.get("semantic_search_candidates"),
            semanticVectorThreshold=results.get("semantic_vector_threshold"),
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
            confidenceDistribution=results.get("confidence_distribution"),
            coverageGaps=results.get("coverage_gaps"),
            breakageWarnings=results.get("breakage_warnings"),
            ragDiagnostics=results.get("rag_diagnostics"),
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


# Semantic search configuration is now handled automatically by the adaptive
# config engine (build_adaptive_semantic_config in process_diff_programmatic.py).
# Manual configuration endpoints have been removed — no user input required.
