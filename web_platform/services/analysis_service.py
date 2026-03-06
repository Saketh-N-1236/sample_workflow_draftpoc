"""Service for running test analysis pipeline."""

import sys
import subprocess
from pathlib import Path
from typing import Dict


class AnalysisService:
    """Service for executing test analysis pipeline."""
    
    def __init__(self):
        """Initialize analysis service."""
        # Get project root - web_platform is in the project root
        # Path structure: project_root/web_platform/services/analysis_service.py
        web_platform_path = Path(__file__).parent.parent.parent
        # If web_platform_path ends with "web_platform", go up one level to project root
        if web_platform_path.name == "web_platform":
            self.project_root = web_platform_path.parent
        else:
            self.project_root = web_platform_path
        
        # Verify test_analysis exists
        if not (self.project_root / "test_analysis").exists():
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"test_analysis directory not found at {self.project_root / 'test_analysis'}")
            # Try alternative path
            alt_path = Path(__file__).parent.parent
            if (alt_path / "test_analysis").exists():
                self.project_root = alt_path
                logger.info(f"Using alternative project root: {self.project_root}")
        
        # Add project root to sys.path to ensure imports work
        import sys
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
    
    async def run_pipeline(self, repo_path: str, progress_callback=None) -> Dict:
        """
        Run the 8-step test analysis pipeline.
        
        Args:
            repo_path: Path to the repository (test repository)
            
        Returns:
            Dictionary with analysis results
        """
        # Set TEST_REPO_PATH environment variable
        import os
        import logging
        logger = logging.getLogger(__name__)
        
        # Ensure absolute path
        repo_path_obj = Path(repo_path).resolve()
        os.environ['TEST_REPO_PATH'] = str(repo_path_obj)
        
        logger.info(f"Setting TEST_REPO_PATH to: {repo_path_obj}")
        logger.info(f"Repository exists: {repo_path_obj.exists()}")
        
        # Verify the path exists
        if not repo_path_obj.exists():
            raise Exception(f"Repository path does not exist: {repo_path_obj}")
        
        # Log some directory contents for debugging
        try:
            dir_contents = list(repo_path_obj.iterdir())[:10]
            logger.info(f"Repository contents (first 10): {[str(p.name) for p in dir_contents]}")
        except Exception as e:
            logger.warning(f"Could not list repository contents: {e}")
        
        # Run each step of the pipeline
        steps = [
            ("01_scan_test_files.py", "Scanning test files..."),
            ("02_detect_framework.py", "Detecting test framework..."),
            ("03_build_test_registry.py", "Building test registry..."),
            ("04_extract_static_dependencies.py", "Extracting static dependencies..."),
            ("04b_extract_function_calls.py", "Extracting function calls..."),
            ("05_extract_test_metadata.py", "Extracting test metadata..."),
            ("06_build_reverse_index.py", "Building reverse index..."),
            ("07_map_test_structure.py", "Mapping test structure..."),
            ("08_generate_summary.py", "Generating summary report...")
        ]
        
        results = {
            "files_analyzed": 0,
            "functions_extracted": 0,
            "modules_identified": 0,
            "test_files": 0
        }
        
        import logging
        logger = logging.getLogger(__name__)
        
        start_msg = "🔍 Starting test analysis pipeline..."
        if progress_callback:
            progress_callback(start_msg)
        print(start_msg)
        logger.info("Starting test analysis pipeline...")
        
        for step_file, step_message in steps:
            script_path = self.project_root / "test_analysis" / step_file
            if script_path.exists():
                try:
                    if progress_callback:
                        progress_callback(step_message)
                    print(step_message)
                    logger.info(f"Running step: {step_file} - {step_message}")
                    
                    # Run the script
                    result = subprocess.run(
                        [sys.executable, str(script_path)],
                        cwd=str(self.project_root),
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout per step
                    )
                    
                    if result.returncode != 0:
                        error_msg = f"❌ {step_message} - Failed"
                        if progress_callback:
                            progress_callback(error_msg)
                        print(error_msg)
                        logger.error(f"Step {step_file} returned non-zero exit code: {result.returncode}")
                        logger.error(f"STDOUT: {result.stdout}")
                        logger.error(f"STDERR: {result.stderr}")
                    else:
                        success_msg = f"✅ {step_message} - Completed"
                        if progress_callback:
                            progress_callback(success_msg)
                        print(success_msg)
                        logger.info(f"Step {step_file} completed successfully")
                        if result.stdout:
                            logger.debug(f"STDOUT: {result.stdout[:500]}")  # First 500 chars
                except subprocess.TimeoutExpired:
                    error_msg = f"❌ {step_message} - Timed out"
                    if progress_callback:
                        progress_callback(error_msg)
                    print(error_msg)
                    logger.error(f"Step {step_file} timed out after 300 seconds")
                except Exception as e:
                    error_msg = f"❌ {step_message} - Error: {str(e)}"
                    if progress_callback:
                        progress_callback(error_msg)
                    print(error_msg)
                    logger.error(f"Error running {step_file}: {e}", exc_info=True)
            else:
                warning_msg = f"⚠️ Step script not found: {step_file}"
                if progress_callback:
                    progress_callback(warning_msg)
                print(warning_msg)
                logger.warning(f"Step script not found: {script_path}")
        
        # Load database (deterministic scripts)
        db_msg = "💾 Storing data to PostgreSQL database..."
        if progress_callback:
            progress_callback(db_msg)
        print(db_msg)
        logger.info("Loading data to PostgreSQL database...")
        await self._load_to_database(progress_callback)
        
        db_success_msg = "✅ Data stored to PostgreSQL successfully"
        if progress_callback:
            progress_callback(db_success_msg)
        print(db_success_msg)
        
        # Generate and store embeddings in Pinecone
        embedding_msg = "🔮 Generating embeddings..."
        if progress_callback:
            progress_callback(embedding_msg)
        print(embedding_msg)
        logger.info("Generating embeddings...")
        await self._generate_embeddings(progress_callback)
        
        pinecone_msg = "✅ Embeddings stored to Pinecone successfully"
        if progress_callback:
            progress_callback(pinecone_msg)
        print(pinecone_msg)
        
        # Read summary to get actual counts
        summary_path = self.project_root / "test_analysis" / "outputs" / "08_summary_report.json"
        import logging
        logger = logging.getLogger(__name__)
        
        if summary_path.exists():
            try:
                import json
                with open(summary_path, 'r') as f:
                    summary = json.load(f)
                    # Summary structure: summary is the root, not summary['data']
                    data = summary if 'data' not in summary else summary.get('data', summary)
                    
                    # Extract detailed statistics from summary
                    test_overview = data.get('test_repository_overview', {})
                    test_inventory = data.get('test_inventory', {})
                    dependencies = data.get('dependencies', {})
                    metadata = data.get('metadata', {})
                    structure = data.get('structure', {})
                    
                    results.update({
                        "files_analyzed": test_overview.get("total_test_files", 0),
                        "test_files": test_overview.get("total_test_files", 0),
                        "total_tests": test_inventory.get("total_tests", 0),
                        "total_test_classes": test_inventory.get("total_test_classes", 0),
                        "total_test_methods": test_inventory.get("total_tests", 0),  # Usually same as total_tests
                        "functions_extracted": dependencies.get("total_dependency_mappings", 0),  # Total function mappings
                        "modules_identified": structure.get("package_count", 0) or len(structure.get("test_categories", [])),
                        "total_dependencies": dependencies.get("total_dependency_mappings", 0),
                        "total_production_classes": dependencies.get("total_production_classes_referenced", 0),
                        "tests_with_descriptions": metadata.get("tests_with_descriptions", 0),
                        "framework": test_overview.get("test_framework", "unknown")
                    })
                logger.info(f"Summary loaded: {results}")
            except Exception as e:
                logger.error(f"Failed to read summary file: {e}", exc_info=True)
        else:
            logger.warning(f"Summary file not found at {summary_path}")
            # Try to read from step 1 output as fallback
            step1_path = self.project_root / "test_analysis" / "outputs" / "01_test_files.json"
            if step1_path.exists():
                try:
                    import json
                    with open(step1_path, 'r') as f:
                        step1_data = json.load(f)
                        test_files = step1_data.get('test_files', [])
                        results.update({
                            "files_analyzed": len(test_files),
                            "test_files": len(test_files)
                        })
                    logger.info(f"Fallback: Loaded from step 1 output: {results}")
                except Exception as e:
                    logger.error(f"Failed to read step 1 output: {e}")
        
        return results
    
    async def _load_to_database(self, progress_callback=None):
        """Load test analysis results into PostgreSQL."""
        import subprocess
        import sys
        
        db_scripts = [
            ("01_create_tables.py", "Creating database tables..."),
            ("02_load_test_registry.py", "Loading test registry..."),
            ("03_load_dependencies.py", "Loading dependencies..."),
            ("04_load_reverse_index.py", "Loading reverse index..."),
            ("04b_load_function_mappings.py", "Loading function mappings..."),
            ("05_load_metadata.py", "Loading test metadata..."),
            ("06_load_structure.py", "Loading test structure...")
        ]
        
        for script, script_message in db_scripts:
            script_path = self.project_root / "deterministic" / script
            if script_path.exists():
                try:
                    if progress_callback:
                        progress_callback(f"  → {script_message}")
                    print(f"  → {script_message}")
                    subprocess.run(
                        [sys.executable, str(script_path)],
                        cwd=str(self.project_root),
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                except Exception as e:
                    error_msg = f"  ❌ Failed to run {script}: {e}"
                    if progress_callback:
                        progress_callback(error_msg)
                    print(error_msg)
    
    async def _generate_embeddings(self, progress_callback=None):
        """Generate and store embeddings in Pinecone for semantic search."""
        import subprocess
        import sys
        import logging
        logger = logging.getLogger(__name__)
        
        embedding_script = self.project_root / "semantic_retrieval" / "embedding_generator.py"
        if embedding_script.exists():
            try:
                if progress_callback:
                    progress_callback("  → Generating embeddings using Ollama...")
                print("  → Generating embeddings using Ollama...")
                logger.info("Starting embedding generation and storage in Pinecone...")
                
                result = subprocess.run(
                    [sys.executable, str(embedding_script)],
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
                
                if result.returncode == 0:
                    if progress_callback:
                        progress_callback("  → Storing embeddings to Pinecone...")
                    print("  → Storing embeddings to Pinecone...")
                    logger.info("Embedding generation completed successfully")
                    if result.stdout:
                        logger.debug(f"Embedding output: {result.stdout[:500]}")
                else:
                    error_msg = f"  ❌ Embedding generation failed"
                    if progress_callback:
                        progress_callback(error_msg)
                    print(error_msg)
                    logger.error(f"Embedding generation failed with exit code {result.returncode}")
                    logger.error(f"STDOUT: {result.stdout}")
                    logger.error(f"STDERR: {result.stderr}")
            except subprocess.TimeoutExpired:
                error_msg = "  ❌ Embedding generation timed out"
                if progress_callback:
                    progress_callback(error_msg)
                print(error_msg)
                logger.error("Embedding generation timed out after 600 seconds")
            except Exception as e:
                error_msg = f"  ❌ Failed to generate embeddings: {e}"
                if progress_callback:
                    progress_callback(error_msg)
                print(error_msg)
                logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
        else:
            warning_msg = f"  ⚠️ Embedding script not found"
            if progress_callback:
                progress_callback(warning_msg)
            print(warning_msg)
            logger.warning(f"Embedding script not found at {embedding_script}")
