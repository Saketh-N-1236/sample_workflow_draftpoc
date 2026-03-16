"""Test analysis routes."""

import sys
import os
import json
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from datetime import datetime

# Add backend/ to path to access all modules
# Path structure: sample_workflow/backend/api/routes/analysis.py
current_file = Path(__file__).resolve()
_backend_path = current_file.parent.parent.parent  # backend/

if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

from api.models.repository import AnalysisResponse
from services.analysis_service import AnalysisService
from services.repository_db import get_repository_by_id

# Router for repository-specific analysis
repo_router = APIRouter(prefix="/repositories", tags=["analysis"])

# Router for general analysis operations (not tied to a specific repository)
analysis_router = APIRouter(prefix="/analysis", tags=["analysis"])

analysis_service = AnalysisService()


@repo_router.post("/{repo_id}/analyze", response_model=AnalysisResponse)
async def run_analysis(repo_id: str):
    """Run test analysis pipeline on local test repository."""
    # Get repository from database
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Please connect the repository first.")
    
    try:
        # Analysis runs on LOCAL test repository, not the code repository
        # Get test repository path from config or use default
        # Import after path setup
        from test_analysis.utils.config import get_test_repo_path
        test_repo_path = get_test_repo_path()
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Running analysis on local test repository: {test_repo_path}")
        
        results = await analysis_service.run_pipeline(str(test_repo_path))
        
        return AnalysisResponse(
            status="completed",
            filesAnalyzed=results.get("files_analyzed", 0),
            testFiles=results.get("test_files", 0),
            totalTests=results.get("total_tests", 0),
            totalTestClasses=results.get("total_test_classes", 0),
            totalTestMethods=results.get("total_test_methods", 0),
            functionsExtracted=results.get("functions_extracted", 0),
            modulesIdentified=results.get("modules_identified", 0),
            totalDependencies=results.get("total_dependencies", 0),
            totalProductionClasses=results.get("total_production_classes", 0),
            testsWithDescriptions=results.get("tests_with_descriptions", 0),
            framework=results.get("framework"),
            message="Analysis completed successfully"
        )
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        error_detail = str(e)
        logger.error(f"Analysis failed: {error_detail}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {error_detail}")


@repo_router.get("/{repo_id}/analysis/status")
async def get_analysis_status(repo_id: str):
    """Get analysis progress status."""
    repo = get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Progress tracking is implemented via progress_callback in analysis_service
    return {"status": "idle", "progress": 0}


@analysis_router.get("/results")
async def get_analysis_results():
    """Get all analysis results from test_analysis outputs."""
    try:
        import json
        from test_analysis.utils.config import get_test_repo_path
        
        # backend/api/routes/ -> parent.parent.parent = backend/
        project_root = Path(__file__).parent.parent.parent
        outputs_dir = project_root / "test_analysis" / "outputs"
        
        results = {
            "test_files": None,
            "framework_detection": None,
            "test_registry": None,
            "static_dependencies": None,
            "function_calls": None,
            "test_metadata": None,
            "reverse_index": None,
            "test_structure": None,
            "summary_report": None,
            "last_updated": None
        }
        
        # Load all output files
        output_files = {
            "test_files": outputs_dir / "01_test_files.json",
            "framework_detection": outputs_dir / "02_framework_detection.json",
            "test_registry": outputs_dir / "03_test_registry.json",
            "static_dependencies": outputs_dir / "04_static_dependencies.json",
            "function_calls": outputs_dir / "04b_function_calls.json",
            "test_metadata": outputs_dir / "05_test_metadata.json",
            "reverse_index": outputs_dir / "06_reverse_index.json",
            "test_structure": outputs_dir / "07_test_structure.json",
            "summary_report": outputs_dir / "08_summary_report.json"
        }
        
        latest_mtime = 0
        
        for key, file_path in output_files.items():
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        file_data = data.get('data', data)
                        
                        # Transform data structures to match frontend expectations
                        if key == 'function_calls' and isinstance(file_data, dict):
                            # Map test_function_mappings to function_mappings
                            if 'test_function_mappings' in file_data and 'function_mappings' not in file_data:
                                file_data['function_mappings'] = file_data['test_function_mappings']
                        
                        elif key == 'static_dependencies' and isinstance(file_data, dict):
                            # Transform test_dependencies array to dependencies object
                            # Frontend expects: { test_id: [dependencies...] }
                            if 'test_dependencies' in file_data and 'dependencies' not in file_data:
                                dependencies_obj = {}
                                for test_dep in file_data.get('test_dependencies', []):
                                    test_id = test_dep.get('test_id')
                                    if test_id:
                                        # Use referenced_classes as the dependency list
                                        dependencies_obj[test_id] = test_dep.get('referenced_classes', [])
                                file_data['dependencies'] = dependencies_obj
                        
                        elif key == 'framework_detection' and isinstance(file_data, dict):
                            # Map primary_framework to detected_framework
                            if 'primary_framework' in file_data and 'detected_framework' not in file_data:
                                file_data['detected_framework'] = file_data['primary_framework']
                            # Map indicators to evidence if needed
                            if 'indicators' in file_data and 'evidence' not in file_data:
                                file_data['evidence'] = file_data.get('indicators', {})
                        
                        # Note: test_metadata and reverse_index already have correct structure
                        # test_metadata has 'test_metadata' key, reverse_index has 'reverse_index' key
                        # No transformation needed for these
                        
                        results[key] = file_data
                        # Track latest modification time
                        mtime = file_path.stat().st_mtime
                        if mtime > latest_mtime:
                            latest_mtime = mtime
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to load {key}: {e}")
        
        if latest_mtime > 0:
            from datetime import datetime
            results["last_updated"] = datetime.fromtimestamp(latest_mtime).isoformat()
        
        return results
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get analysis results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get analysis results: {str(e)}")


@analysis_router.post("/refresh")
async def refresh_analysis():
    """Refresh analysis by rerunning the pipeline on test repository with progress updates."""
    try:
        from test_analysis.utils.config import get_test_repo_path
        test_repo_path = get_test_repo_path()
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Refreshing analysis on test repository: {test_repo_path}")
        
        # Collect progress messages
        progress_messages = []
        
        def progress_callback(message: str):
            """Callback to capture progress messages."""
            progress_messages.append(message)
            # Don't print here - it's already printed in analysis_service
            logger.info(f"Progress: {message}")
        
        results = await analysis_service.run_pipeline(str(test_repo_path), progress_callback=progress_callback)
        
        return {
            "status": "completed",
            "message": "Analysis refreshed successfully",
            "results": results,
            "progress": progress_messages
        }
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        error_detail = str(e)
        logger.error(f"Analysis refresh failed: {error_detail}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Analysis refresh failed: {error_detail}")


@analysis_router.get("/embedding-status")
async def get_embedding_status(test_repo_id: Optional[str] = Query(None)):
    """
    Get status of embeddings in Pinecone.
    
    Args:
        test_repo_id: Optional test repository ID to filter embeddings by.
                     If provided, only counts embeddings for that test repository.
    """
    try:
        import os
        from datetime import datetime
        from semantic_retrieval.config import VECTOR_BACKEND
        from semantic_retrieval.backends import get_backend
        from deterministic.db_connection import get_connection
        from config.settings import get_settings
        from llm.factory import LLMFactory
        
        backend_name = VECTOR_BACKEND.lower()
        index_name = os.getenv('PINECONE_INDEX_NAME', 'test-embeddings')
        
        # Get actual embedding dimensions from the configured provider
        settings = get_settings()
        embedding_provider = LLMFactory.create_embedding_provider(settings)
        embedding_dimensions = embedding_provider.get_embedding_dimensions()
        if embedding_dimensions is None:
            # Fallback to default if provider doesn't specify
            embedding_dimensions = 768
        
        # Try to get backend and check status
        try:
            with get_connection() as conn:
                backend = get_backend(conn)
                
                # Get index stats if Pinecone
                total_embeddings = 0
                index_health = "unknown"
                
                if backend_name == "pinecone" and hasattr(backend, 'index'):
                    try:
                        if test_repo_id:
                            # Filter by test_repo_id using Pinecone metadata filter
                            # We need to query with a filter to count vectors for this test_repo_id
                            # Use a dummy query vector (all zeros) with filter
                            # Get actual index dimension from Pinecone
                            try:
                                index_stats = backend.index.describe_index_stats()
                                index_dimension = index_stats.get('dimension', embedding_dimensions)
                                # Use the actual index dimension for the dummy vector
                                dummy_vector = [0.0] * index_dimension
                            except Exception:
                                # Fallback to embedding_dimensions if we can't get index stats
                                dummy_vector = [0.0] * embedding_dimensions
                            
                            # Query vectors and count by checking both metadata and vector ID format
                            # Vectors are stored with format: {test_repo_id}_{test_id}
                            # We check both to handle old and new formats
                            try:
                                import logging
                                logger = logging.getLogger(__name__)
                                
                                # Try querying with metadata filter first
                                filter_dict = {"test_repo_id": {"$eq": str(test_repo_id)}}
                                query_result = backend.index.query(
                                    vector=dummy_vector,
                                    top_k=10000,
                                    filter=filter_dict,
                                    include_metadata=True
                                )
                                
                                # Count vectors that match test_repo_id in metadata OR vector ID format
                                matching_count = 0
                                metadata_matches = 0
                                vector_id_matches = 0
                                
                                for match in query_result.matches:
                                    metadata = match.metadata or {}
                                    metadata_repo_id = metadata.get('test_repo_id', '')
                                    vector_id = match.id
                                    
                                    # Check metadata match
                                    if metadata_repo_id and metadata_repo_id == str(test_repo_id):
                                        metadata_matches += 1
                                    
                                    # Check vector ID prefix match (new format: {test_repo_id}_{test_id})
                                    if vector_id.startswith(f"{test_repo_id}_"):
                                        vector_id_matches += 1
                                    
                                    # Count if either matches
                                    if (metadata_repo_id and metadata_repo_id == str(test_repo_id)) or vector_id.startswith(f"{test_repo_id}_"):
                                        matching_count += 1
                                
                                # If no matches found with filter, try querying without filter to check vector IDs
                                # This handles cases where metadata filter doesn't work but vector ID format is correct
                                if matching_count == 0:
                                    logger.info(f"No matches found with metadata filter for test_repo_id '{test_repo_id}'. Checking vector ID format...")
                                    
                                    # Get total vector count to determine query size
                                    try:
                                        stats = backend.index.describe_index_stats()
                                        total_vectors = stats.get('total_vector_count', 0)
                                        
                                        # Query without filter to check vector IDs
                                        # Limit to reasonable size to avoid performance issues
                                        query_size = min(10000, total_vectors) if total_vectors > 0 else 10000
                                        
                                        query_result_no_filter = backend.index.query(
                                            vector=dummy_vector,
                                            top_k=query_size,
                                            include_metadata=True
                                        )
                                        
                                        for match in query_result_no_filter.matches:
                                            vector_id = match.id
                                            if vector_id.startswith(f"{test_repo_id}_"):
                                                matching_count += 1
                                        
                                        if matching_count > 0:
                                            logger.info(
                                                f"Found {matching_count} vectors by vector ID prefix for test_repo_id '{test_repo_id}' "
                                                f"(queried {query_size} vectors from {total_vectors} total)"
                                            )
                                        else:
                                            logger.warning(
                                                f"No vectors found with test_repo_id '{test_repo_id}' prefix in vector IDs. "
                                                f"Queried {query_size} vectors from {total_vectors} total."
                                            )
                                    except Exception as sample_error:
                                        logger.warning(f"Failed to query vectors without filter: {sample_error}")
                                
                                total_embeddings = matching_count
                                
                                # Log matching details for debugging
                                if total_embeddings > 0:
                                    logger.debug(
                                        f"Found {total_embeddings} embeddings for test_repo_id '{test_repo_id}': "
                                        f"{metadata_matches} by metadata, {vector_id_matches} by vector ID"
                                    )
                                
                                # Log if filter returned results but none matched (might indicate filter issue)
                                if len(query_result.matches) > 0 and matching_count == 0:
                                    import logging
                                    logger = logging.getLogger(__name__)
                                    logger.warning(
                                        f"Pinecone filter returned {len(query_result.matches)} vectors, "
                                        f"but none matched test_repo_id '{test_repo_id}'. "
                                        f"This might indicate a filter issue or metadata mismatch."
                                    )
                                
                                # Log if no embeddings found but index has vectors
                                if total_embeddings == 0:
                                    try:
                                        stats = backend.index.describe_index_stats()
                                        total_in_index = stats.get('total_vector_count', 0)
                                        if total_in_index > 0:
                                            import logging
                                            logger = logging.getLogger(__name__)
                                            
                                            # Check if there are embeddings without test_repo_id metadata
                                            sample_query = backend.index.query(
                                                vector=dummy_vector,
                                                top_k=min(10, total_in_index),
                                                include_metadata=True
                                            )
                                            has_repo_id_metadata = False
                                            missing_repo_id_count = 0
                                            for match in sample_query.matches:
                                                metadata = match.metadata or {}
                                                if 'test_repo_id' in metadata and metadata.get('test_repo_id'):
                                                    has_repo_id_metadata = True
                                                else:
                                                    missing_repo_id_count += 1
                                            
                                            if missing_repo_id_count > 0:
                                                logger.warning(
                                                    f"Index has {total_in_index} total vectors but 0 for test_repo_id '{test_repo_id}'. "
                                                    f"Some embeddings may be missing test_repo_id metadata (old embeddings). "
                                                    f"Please regenerate embeddings for this repository."
                                                )
                                            else:
                                                logger.info(
                                                    f"Index has {total_in_index} total vectors but 0 for test_repo_id '{test_repo_id}'. "
                                                    f"This repository has no embeddings yet. Please generate embeddings."
                                                )
                                    except Exception:
                                        pass
                            except Exception as filter_error:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"Failed to filter embeddings by test_repo_id: {filter_error}")
                                # Don't fallback to total count - if filter fails, return 0
                                # This ensures we don't show embeddings from other repositories
                                total_embeddings = 0
                                logger.info(
                                    f"Filter query failed for test_repo_id '{test_repo_id}'. "
                                    f"Returning 0 to avoid showing embeddings from other repositories."
                                )
                        else:
                            # Get total index stats (no filter)
                            stats = backend.index.describe_index_stats()
                            total_embeddings = stats.get('total_vector_count', 0)
                        
                        index_health = "healthy" if total_embeddings > 0 else "empty"
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to get Pinecone stats: {e}")
                        index_health = "unhealthy"
                # Only Pinecone is supported - no pgvector handling needed
                
                # Try to get last generated time from analysis outputs
                last_generated = None
                try:
                    from pathlib import Path
                    # backend/api/routes/ -> parent.parent.parent = backend/
                    project_root = Path(__file__).parent.parent.parent
                    embedding_script = project_root / "semantic_retrieval" / "embedding_generator.py"
                    if embedding_script.exists():
                        mtime = embedding_script.stat().st_mtime
                        last_generated = datetime.fromtimestamp(mtime).isoformat()
                except Exception:
                    pass
                
                # Get actual index dimension from Pinecone if available
                actual_index_dimension = embedding_dimensions
                if backend_name == "pinecone" and hasattr(backend, 'index'):
                    try:
                        index_stats = backend.index.describe_index_stats()
                        actual_index_dimension = index_stats.get('dimension', embedding_dimensions)
                    except Exception:
                        pass
                
                return {
                    "total_embeddings": total_embeddings,
                    "last_generated": last_generated,
                    "index_health": index_health,
                    "embedding_dimensions": actual_index_dimension,  # Use actual index dimension
                    "backend": backend_name,
                    "index_name": index_name if backend_name == "pinecone" else None,
                    "test_repo_id": test_repo_id  # Include test_repo_id in response
                }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to get embedding status: {e}")
            return {
                "total_embeddings": 0,
                "last_generated": None,
                "index_health": "unknown",
                "embedding_dimensions": embedding_dimensions,  # Use provider dimensions
                "backend": backend_name,
                "index_name": index_name if backend_name == "pinecone" else None,
                "test_repo_id": test_repo_id,
                "error": str(e)
            }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get embedding status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get embedding status: {str(e)}")


@analysis_router.get("/total-tests")
async def get_total_tests_count():
    """Get total number of tests in the database."""
    try:
        from deterministic.db_connection import get_connection
        from deterministic.db_connection import DB_SCHEMA
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.test_registry")
            total_tests = cursor.fetchone()[0]
            cursor.close()
            
            return {
                "total_tests": total_tests
            }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get total tests count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get total tests count: {str(e)}")


@analysis_router.get("/all-tests")
async def get_all_tests():
    """Get all tests from the database with their details."""
    try:
        from deterministic.db_connection import get_connection
        from deterministic.db_connection import DB_SCHEMA
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT 
                    test_id,
                    method_name,
                    class_name,
                    test_type,
                    file_path
                FROM {DB_SCHEMA}.test_registry
                ORDER BY test_id
            """)
            
            rows = cursor.fetchall()
            tests = []
            for row in rows:
                tests.append({
                    'test_id': row[0],
                    'method_name': row[1] or '',
                    'class_name': row[2] or '',
                    'test_type': row[3] or 'unknown',
                    'test_file_path': row[4] or ''  # Map file_path to test_file_path for frontend
                })
            
            cursor.close()
            
            return {
                "tests": tests,
                "total": len(tests)
            }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get all tests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get all tests: {str(e)}")
