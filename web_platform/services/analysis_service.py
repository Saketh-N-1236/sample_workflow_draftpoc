"""Service for running test analysis pipeline."""

import sys
import subprocess
from pathlib import Path
from typing import Dict, Optional
import logging
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import new architecture components
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
        # Get project root
        web_platform_path = Path(__file__).parent.parent.parent
        if web_platform_path.name == "web_platform":
            self.project_root = web_platform_path.parent
        else:
            self.project_root = web_platform_path
        
        # Verify test_analysis exists
        if not (self.project_root / "test_analysis").exists():
            logger.warning(f"test_analysis directory not found at {self.project_root / 'test_analysis'}")
            alt_path = Path(__file__).parent.parent
            if (alt_path / "test_analysis").exists():
                self.project_root = alt_path
                logger.info(f"Using alternative project root: {self.project_root}")
        
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
            
            logger.info("Phase 1: DETECT - Detecting languages and frameworks")
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
            
            logger.info("Phase 2: DISPATCH - Running language analyzers")
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
            
            logger.info("Phase 3: MERGE - Merging analyzer results")
            merged_summary = merge_analyzer_results(analyzer_results, output_dir)
            
            # STEP 4: SCHEMA - Build dynamic schema
            if progress_callback:
                await progress_callback("Building database schema...")
            
            logger.info("Phase 4: SCHEMA - Building dynamic schema")
            schema_def = build_schema_for_detection(detection_report.to_dict())
            
            # Store schema definition in environment for table creation script
            import json
            schema_dict = schema_def.to_dict()
            os.environ['SCHEMA_DEFINITION'] = json.dumps(schema_dict)
            
            total_tables = len(schema_def.core_tables) + len(schema_def.java_tables) + len(schema_def.python_tables) + len(schema_def.js_tables)
            logger.info(f"Schema built: {total_tables} tables total ({len(schema_def.core_tables)} core + {len(schema_def.java_tables)} Java + {len(schema_def.python_tables)} Python + {len(schema_def.js_tables)} JS)")
            
            # STEP 5: LOAD - Load to database using existing deterministic scripts
            if progress_callback:
                await progress_callback("Loading data to database...")
            
            logger.info("Phase 5: LOAD - Loading data to database")
            await self._load_to_database(schema_name or os.getenv('TEST_REPO_SCHEMA'), progress_callback, schema_def)
            
            # STEP 6: Generate embeddings
            if progress_callback:
                await progress_callback("Generating embeddings...")
            
            logger.info("Phase 6: Generate embeddings")
            await self._generate_embeddings(test_repo_id, schema_name or os.getenv('TEST_REPO_SCHEMA'), progress_callback)
            
            # Read summary for results
            summary_path = output_dir / "08_summary_report.json"
            results = {
                "files_analyzed": 0,
                "functions_extracted": 0,
                "modules_identified": 0,
                "test_files": 0,
                "total_tests": 0,
            }
            
            if summary_path.exists():
                try:
                    import json
                    with open(summary_path, 'r') as f:
                        summary = json.load(f)
                        data = summary.get('data', summary)
                        test_overview = data.get('test_repository_overview', {})
                        test_inventory = data.get('test_inventory', {})
                        dependencies = data.get('dependencies', {})
                        structure = data.get('structure', {})
                        
                        results.update({
                            "files_analyzed": test_overview.get("total_test_files", 0),
                            "test_files": test_overview.get("total_test_files", 0),
                            "total_tests": test_inventory.get("total_tests", 0),
                            "total_test_classes": test_inventory.get("total_test_classes", 0),
                            "total_test_methods": test_inventory.get("total_tests", 0),
                            "functions_extracted": dependencies.get("total_dependency_mappings", 0),
                            "modules_identified": structure.get("package_count", 0) or len(structure.get("test_categories", [])),
                            "total_dependencies": dependencies.get("total_dependency_mappings", 0),
                            "total_production_classes": dependencies.get("total_production_classes_referenced", 0),
                            "framework": test_overview.get("test_framework", "unknown")
                        })
                except Exception as e:
                    logger.error(f"Failed to read summary file: {e}", exc_info=True)
            
            # Return results
            return {
                'success': True,
                'detection_report': detection_report.to_dict(),
                'analyzer_results': [r.to_dict() for r in analyzer_results],
                'merged_summary': merged_summary,
                'schema_definition': schema_def.to_dict(),
                'output_directory': str(output_dir),
                **results,  # Include summary statistics
            }
        
        except Exception as e:
            logger.error(f"Analysis pipeline failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
            }
    
    async def _load_to_database(self, schema_name: Optional[str] = None, progress_callback=None, schema_def=None):
        """
        Load analysis results to database using existing deterministic scripts.
        
        Args:
            schema_name: Optional schema name
            progress_callback: Optional progress callback
            schema_def: Optional SchemaDefinition object for language-specific tables
        """
        if schema_name:
            os.environ['TEST_REPO_SCHEMA'] = schema_name
        
        # Store schema definition for table creation script
        if schema_def:
            import json
            os.environ['SCHEMA_DEFINITION'] = json.dumps(schema_def.to_dict())
        
        scripts = [
            ("deterministic/01_create_tables.py", "Creating database tables..."),
            ("deterministic/02_load_test_registry.py", "Loading test registry..."),
            ("deterministic/03_load_dependencies.py", "Loading dependencies..."),
            ("deterministic/04_load_reverse_index.py", "Loading reverse index..."),
            ("deterministic/04b_load_function_mappings.py", "Loading function mappings..."),
            ("deterministic/05_load_metadata.py", "Loading metadata..."),
            ("deterministic/06_load_structure.py", "Loading structure..."),
            # Java-specific loaders
            ("deterministic/07_load_java_reflection.py", "Loading Java reflection calls..."),
            ("deterministic/08_load_java_di_fields.py", "Loading Java DI fields..."),
            ("deterministic/09_load_java_annotations.py", "Loading Java annotations..."),
            # Python-specific loaders
            ("deterministic/10_load_python_fixtures.py", "Loading Python fixtures..."),
            ("deterministic/11_load_python_decorators.py", "Loading Python decorators..."),
            ("deterministic/12_load_python_async_tests.py", "Loading Python async tests..."),
            # JavaScript-specific loaders
            ("deterministic/13_load_js_mocks.py", "Loading JavaScript mocks..."),
            ("deterministic/14_load_js_async_tests.py", "Loading JavaScript async tests..."),
        ]
        
        for script_name, script_message in scripts:
            script_path = self.project_root / script_name
            if not script_path.exists():
                logger.warning(f"Script not found: {script_path}")
                continue
            
            try:
                if progress_callback:
                    await progress_callback(f"  → {script_message}")
                logger.info(f"Running {script_name}...")
                
                # Pass schema name as argument for table creation script
                cmd = [sys.executable, str(script_path)]
                if script_name == "deterministic/01_create_tables.py" and schema_name:
                    cmd.append(schema_name)
                
                result = subprocess.run(
                    cmd,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env=os.environ.copy()
                )
                
                if result.returncode != 0:
                    error_msg = f"  ❌ {script_message} - Failed (exit code: {result.returncode})"
                    if progress_callback:
                        await progress_callback(error_msg)
                    logger.error(error_msg)
                    logger.error(f"Error output: {result.stderr}")
                else:
                    success_msg = f"  ✅ {script_message} - Completed"
                    if progress_callback:
                        await progress_callback(success_msg)
                    logger.info(success_msg)
            except subprocess.TimeoutExpired:
                error_msg = f"  ❌ {script_message} - Timeout"
                if progress_callback:
                    await progress_callback(error_msg)
                logger.error(error_msg)
            except Exception as e:
                error_msg = f"  ❌ {script_message} - Error: {e}"
                if progress_callback:
                    await progress_callback(error_msg)
                logger.error(error_msg)
    
    async def _generate_embeddings(self, test_repo_id: Optional[str] = None, schema_name: Optional[str] = None, progress_callback=None):
        """Generate and store embeddings in Pinecone for semantic search."""
        env = os.environ.copy()
        if test_repo_id:
            env['TEST_REPO_ID'] = test_repo_id
        if schema_name:
            env['TEST_REPO_SCHEMA'] = schema_name
        
        embedding_script = self.project_root / "semantic_retrieval" / "embedding_generator.py"
        if embedding_script.exists():
            try:
                if progress_callback:
                    await progress_callback("  → Generating embeddings using Ollama...")
                logger.info("Starting embedding generation...")
                
                result = subprocess.run(
                    [sys.executable, str(embedding_script)],
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=1800,  # Increased to 30 minutes for large repositories
                    env=env
                )
                
                if result.returncode == 0:
                    if progress_callback:
                        await progress_callback("  → Embeddings stored to Pinecone")
                    logger.info("Embedding generation completed")
                else:
                    error_msg = "  ❌ Embedding generation failed"
                    if progress_callback:
                        await progress_callback(error_msg)
                    logger.error(f"Embedding generation failed: {result.stderr}")
            except subprocess.TimeoutExpired:
                error_msg = "  ❌ Embedding generation timed out"
                if progress_callback:
                    await progress_callback(error_msg)
                logger.error(error_msg)
            except Exception as e:
                error_msg = f"  ❌ Failed to generate embeddings: {e}"
                if progress_callback:
                    await progress_callback(error_msg)
                logger.error(error_msg)
        else:
            logger.warning(f"Embedding script not found: {embedding_script}")
