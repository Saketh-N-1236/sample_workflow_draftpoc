"""Service for running test analysis pipeline."""

import sys
import subprocess
from pathlib import Path
from typing import Dict, Optional
import logging
import os

# Add backend/ to path so all sub-packages are importable
# Path: backend/services/analysis_service.py -> parent.parent = backend/
_backend_path = Path(__file__).parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

# New unified pipeline components
from test_analysis.engine.repo_analyzer import RepoAnalyzer
from deterministic.loader import load_to_db
from deterministic.db_connection import get_connection_with_schema

# Legacy imports kept for backward-compat (detection_report, merge summary)
from test_analysis.core.detection import create_detection_report
from test_analysis.core.analyzers import BaseAnalyzer
from test_analysis.core.analyzers import JavaAnalyzer, PythonAnalyzer, JavaScriptAnalyzer, TreeSitterFallbackAnalyzer
from test_analysis.core.schema import build_schema_for_detection
from test_analysis.core.merger import merge_analyzer_results
from test_analysis.utils.config import get_output_dir

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for executing test analysis pipeline using new detection-first architecture."""
    
    def __init__(self):
        """Initialize analysis service."""
        # Get backend path: backend/services/analysis_service.py -> parent.parent = backend/
        self.project_root = Path(__file__).parent.parent
        
        # Verify test_analysis exists under backend/
        if not (self.project_root / "test_analysis").exists():
            logger.warning(f"test_analysis directory not found at {self.project_root / 'test_analysis'}")
        
        # Add project root to sys.path
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
        
        # Initialize analyzers
        self._analyzers = {
            'java': JavaAnalyzer(),
            'python': PythonAnalyzer(),
            'javascript': JavaScriptAnalyzer(),
            'typescript': JavaScriptAnalyzer(),  # Use JS analyzer for TS
        }
        self._fallback_analyzer = TreeSitterFallbackAnalyzer()
    
    def _get_analyzer_for_language(self, language: str) -> Optional[BaseAnalyzer]:
        """Get analyzer for a language."""
        return self._analyzers.get(language)
    
    async def run_pipeline(
        self,
        repo_path: str,
        test_repo_id: str = None,
        schema_name: str = None,
        progress_callback=None
    ) -> Dict:
        """
        Run the test analysis pipeline using new detection-first architecture.
        
        Flow:
        1. DETECT - Scan repository, identify languages and frameworks
        2. DISPATCH - For each language, call appropriate analyzer
        3. MERGE - Combine outputs from all analyzers
        4. SCHEMA - Build dynamic schema based on detection
        5. LOAD - Load results to database (existing deterministic scripts)
        
        Args:
            repo_path: Path to the repository (test repository)
            test_repo_id: Optional test repository ID (for multi-repo support)
            schema_name: Optional schema name to use (for multi-repo support)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with analysis results
        """
        import os
        
        # Set environment variables
        repo_path_obj = Path(repo_path).resolve()
        os.environ['TEST_REPO_PATH'] = str(repo_path_obj)
        
        if test_repo_id:
            os.environ['TEST_REPO_ID'] = test_repo_id
        
        if schema_name:
            os.environ['TEST_REPO_SCHEMA'] = schema_name
        elif test_repo_id:
            # Try to get schema name from database
            try:
                from services.test_repo_service import get_test_repository
                test_repo = get_test_repository(test_repo_id)
                if test_repo and test_repo.get('schema_name'):
                    os.environ['TEST_REPO_SCHEMA'] = test_repo['schema_name']
            except Exception as e:
                logger.warning(f"Failed to get schema name for test_repo_id {test_repo_id}: {e}")
        
        logger.info(f"Starting analysis pipeline for: {repo_path_obj}")
        
        if not repo_path_obj.exists():
            raise Exception(f"Repository path does not exist: {repo_path_obj}")
        
        # Get output directory
        output_dir = get_output_dir()
        
        try:
            # STEP 1: DETECT - Language and framework detection
            if progress_callback:
                await progress_callback("Detecting languages and frameworks...")
            
            logger.info("[PHASE 1] DETECT - Detecting languages and frameworks")
            detection_report = create_detection_report(
                repo_path_obj,
                include_test_files_only=True,
                framework_sample_size=50
            )
            
            detected_languages = detection_report.get_languages()
            logger.info(f"Detected languages: {detected_languages}")
            
            if not detected_languages:
                logger.warning("No languages detected in repository")
                return {
                    'error': 'No languages detected',
                    'detection_report': detection_report.to_dict(),
                }
            
            # STEP 2: DISPATCH - Run analyzers for each detected language
            if progress_callback:
                await progress_callback("Running language analyzers...")
            
            logger.info("[PHASE 2] DISPATCH - Running language analyzers")
            analyzer_results = []
            
            for language in detected_languages:
                logger.info(f"Analyzing {language} files...")
                
                # Get analyzer for language
                analyzer = self._get_analyzer_for_language(language)
                
                if analyzer:
                    # Use language-specific analyzer
                    try:
                        # Create language-specific output directory
                        lang_output_dir = output_dir / f"_{language}"
                        lang_output_dir.mkdir(parents=True, exist_ok=True)
                        
                        result = analyzer.analyze(repo_path_obj, lang_output_dir)
                        analyzer_results.append(result)
                        logger.info(f"{language} analysis complete: {result.tests_found} tests found")
                    except Exception as e:
                        logger.error(f"Error running {language} analyzer: {e}", exc_info=True)
                else:
                    # Fallback to Tree-sitter generic parser
                    logger.info(f"No specific analyzer for {language}, using Tree-sitter fallback")
                    try:
                        lang_output_dir = output_dir / f"_{language}"
                        lang_output_dir.mkdir(parents=True, exist_ok=True)
                        
                        result = self._fallback_analyzer.analyze(repo_path_obj, lang_output_dir)
                        analyzer_results.append(result)
                    except Exception as e:
                        logger.error(f"Error running fallback analyzer for {language}: {e}", exc_info=True)
            
            if not analyzer_results:
                logger.error("No analyzers completed successfully")
                return {
                    'error': 'No analyzers completed',
                    'detection_report': detection_report.to_dict(),
                }
            
            # STEP 3: MERGE - Combine outputs from all analyzers
            if progress_callback:
                await progress_callback("Merging analysis results...")
            
            logger.info("[PHASE 3] MERGE - Merging analyzer results")
            merged_summary = merge_analyzer_results(analyzer_results, output_dir)
            
            # STEP 4: SCHEMA - Build dynamic schema
            if progress_callback:
                await progress_callback("Building database schema...")
            
            logger.info("[PHASE 4] SCHEMA - Building dynamic schema")
            schema_def = build_schema_for_detection(detection_report.to_dict())
            
            # Store schema definition in environment for table creation script
            import json
            schema_dict = schema_def.to_dict()
            os.environ['SCHEMA_DEFINITION'] = json.dumps(schema_dict)
            
            total_tables = len(schema_def.core_tables) + len(schema_def.java_tables) + len(schema_def.python_tables) + len(schema_def.js_tables)
            logger.info(f"Schema built: {total_tables} tables total ({len(schema_def.core_tables)} core + {len(schema_def.java_tables)} Java + {len(schema_def.python_tables)} Python + {len(schema_def.js_tables)} JS)")
            
            # STEP 5: LOAD — in-process loader (replaces 14 subprocesses)
            if progress_callback:
                await progress_callback("Loading data to database...")
            
            logger.info("[PHASE 5] LOAD - Loading data to database (in-process)")
            effective_schema = schema_name or os.getenv('TEST_REPO_SCHEMA', 'planon1')

            analysis_result = RepoAnalyzer().analyze(
                repo_path_obj,
                schema_name=effective_schema,
                repo_id=test_repo_id or "",
                progress_callback=(
                    (lambda msg: None)  # sync wrapper — progress from engine goes to logger
                    if progress_callback is None
                    else None
                ),
            )

            try:
                with get_connection_with_schema(effective_schema) as conn:
                    load_stats = load_to_db(conn, analysis_result, effective_schema)
                if progress_callback:
                    await progress_callback(f"  [OK] Loaded {analysis_result.total_tests} tests into DB")
                logger.info(f"[PHASE 5] Load complete. Stats: {load_stats}")
            except Exception as load_err:
                logger.error(f"[PHASE 5] In-process load failed: {load_err}", exc_info=True)
                if progress_callback:
                    await progress_callback(f"  [ERROR] DB load failed: {load_err}")
            
            # STEP 6: Generate embeddings
            if progress_callback:
                await progress_callback("Generating embeddings...")
            
            logger.info("[PHASE 6] EMBED - Generating embeddings (NEW: Direct file loading)")
            await self._generate_embeddings(
                test_repo_id=test_repo_id, 
                schema_name=effective_schema, 
                progress_callback=progress_callback,
                repo_path=str(repo_path_obj)  # Pass repo path for direct file loading
            )
            
            # Build results summary from AnalysisResult (no JSON file needed)
            results = {
                "files_analyzed": sum(
                    lr.files_analyzed for lr in analysis_result.languages.values()
                ),
                "test_files": sum(
                    lr.files_analyzed for lr in analysis_result.languages.values()
                ),
                "total_tests": analysis_result.total_tests,
                "total_test_classes": len({t.describe for t in analysis_result.all_tests if t.describe}),
                "total_test_methods": analysis_result.total_tests,
                "functions_extracted": len(analysis_result.function_mappings),
                "modules_identified": len(analysis_result.reverse_index),
                "total_dependencies": len(analysis_result.dependencies),
                "total_production_classes": len(analysis_result.reverse_index),
                "framework": analysis_result.framework,
            }

            # Optionally write consolidated analysis.json for debugging
            if os.environ.get('DEBUG_WRITE_JSON', '').lower() in ('1', 'true', 'yes'):
                analysis_result.write_consolidated_json(output_dir)

            return {
                'success': True,
                'detection_report': detection_report.to_dict(),
                'analyzer_results': [r.to_dict() for r in analyzer_results],
                'merged_summary': merged_summary,
                'schema_definition': schema_def.to_dict(),
                'output_directory': str(output_dir),
                **results,
            }
        
        except Exception as e:
            logger.error(f"Analysis pipeline failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
            }
    
    async def _load_to_database(self, schema_name: Optional[str] = None, progress_callback=None, schema_def=None):
        """
        DEPRECATED — replaced by deterministic/loader.py load_to_db() called directly
        from run_pipeline().  This stub exists only to avoid AttributeError if any
        external code still calls it.
        """
        logger.warning(
            "[DEPRECATED] _load_to_database() is no longer used. "
            "Loading is now handled in-process by deterministic/loader.py."
        )
    
    async def _generate_embeddings(self, test_repo_id: Optional[str] = None, schema_name: Optional[str] = None, progress_callback=None, repo_path: Optional[str] = None):
        """
        Generate and store embeddings in Pinecone for semantic search.
        
        NEW APPROACH: Uses direct file loading from test repository (no JSON/database dependency).
        """
        env = os.environ.copy()
        if test_repo_id:
            env['TEST_REPO_ID'] = test_repo_id
        if schema_name:
            env['TEST_REPO_SCHEMA'] = schema_name
        
        # NEW APPROACH: Pass test repository path for direct file loading
        if repo_path:
            env['TEST_REPO_PATH'] = repo_path
            logger.info(f"[EMBED] Using NEW approach: Direct file loading from {repo_path}")
        else:
            logger.warning("[EMBED] TEST_REPO_PATH not set, falling back to legacy JSON approach")
        
        embedding_script = self.project_root / "semantic" / "embedding_generation" / "embedding_generator.py"
        if embedding_script.exists():
            try:
                if progress_callback:
                    await progress_callback("  [RUN] Generating embeddings...")
                logger.info("[EMBED] Starting embedding generation")
                
                result = subprocess.run(
                    [sys.executable, str(embedding_script)],
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=1800,  # Increased to 30 minutes for large repositories
                    env=env
                )
                
                if result.returncode == 0:
                    # Check output for warnings about no embeddings stored
                    output_text = result.stdout + result.stderr
                    if "No embeddings were stored" in output_text or "WARNING: No embeddings were stored" in output_text:
                        error_msg = "  [WARN] Embedding generation completed - no embeddings stored (possible dimension mismatch)"
                        if progress_callback:
                            await progress_callback(error_msg)
                        logger.warning("Embedding generation completed but no embeddings were stored")
                    else:
                        if progress_callback:
                            await progress_callback("  [OK] Embeddings stored to Pinecone")
                        logger.info("[EMBED] Embedding generation complete")
                else:
                    error_msg = "  [FAILED] Embedding generation"
                    if progress_callback:
                        await progress_callback(error_msg)
                    logger.error(f"[EMBED] Embedding generation failed (exit code {result.returncode})")
                    logger.error(f"STDOUT: {result.stdout}")
                    logger.error(f"STDERR: {result.stderr}")
            except subprocess.TimeoutExpired:
                error_msg = "  [TIMEOUT] Embedding generation"
                if progress_callback:
                    await progress_callback(error_msg)
                logger.error("[EMBED] Embedding generation timed out")
            except Exception as e:
                error_msg = f"  [ERROR] Embedding generation: {e}"
                if progress_callback:
                    await progress_callback(error_msg)
                logger.error(f"[EMBED] Embedding generation error: {e}")
        else:
            logger.warning(f"Embedding script not found: {embedding_script}")
