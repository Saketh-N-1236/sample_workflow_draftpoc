"""Test repository management API routes."""

import sys
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

# Add web_platform to path
web_platform_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(web_platform_path))

from api.models.test_repository import (
    TestRepositoryResponse,
    TestRepositoryCreate,
    TestRepositoryUpdate,
    BindTestRepositoryRequest,
    TestRepositoryAnalysisResponse
)
from services.test_repo_service import (
    create_test_repository,
    get_test_repository,
    list_test_repositories,
    delete_test_repository,
    bind_test_repository_to_repo,
    unbind_test_repository_from_repo,
    get_bound_test_repositories,
    update_test_repository_status
)
from services.analysis_service import AnalysisService
from services.repository_db import get_repository_by_id

router = APIRouter(prefix="/api/test-repositories", tags=["test-repositories"])
logger = logging.getLogger(__name__)
analysis_service = AnalysisService()


@router.post("/upload", response_model=TestRepositoryResponse)
async def upload_test_repository(
    file: UploadFile = File(...),
    name: str = Form(...)
):
    """
    Upload a test repository as a zip file.
    
    Args:
        file: Zip file containing the test repository
        name: Name for the test repository
        
    Returns:
        Test repository information
    """
    try:
        import tempfile
        import os
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Create test repository
            test_repo_id, schema_name, extracted_path = create_test_repository(
                name=name,
                zip_file_path=tmp_path,
                zip_filename=file.filename
            )
            
            # Get test repository details
            test_repo = get_test_repository(test_repo_id)
            if not test_repo:
                raise HTTPException(status_code=500, detail="Failed to retrieve created test repository")
            
            return TestRepositoryResponse(
                id=test_repo['id'],
                name=test_repo['name'],
                zip_filename=test_repo['zip_filename'],
                extracted_path=test_repo['extracted_path'],
                hash=test_repo['hash'],
                uploaded_at=test_repo['uploaded_at'],
                last_analyzed_at=test_repo['last_analyzed_at'],
                status=test_repo['status'],
                metadata=test_repo['metadata'],
                schema_name=test_repo['schema_name']
            )
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Failed to upload test repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload test repository: {str(e)}")


@router.get("", response_model=List[TestRepositoryResponse])
async def list_all_test_repositories():
    """List all test repositories."""
    try:
        repos = list_test_repositories()
        return [
            TestRepositoryResponse(
                id=repo['id'],
                name=repo['name'],
                zip_filename=repo['zip_filename'],
                extracted_path=repo['extracted_path'],
                hash=repo['hash'],
                uploaded_at=repo['uploaded_at'],
                last_analyzed_at=repo['last_analyzed_at'],
                status=repo['status'],
                metadata=repo['metadata'],
                schema_name=repo['schema_name']
            )
            for repo in repos
        ]
    except Exception as e:
        logger.error(f"Failed to list test repositories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list test repositories: {str(e)}")


@router.get("/{test_repo_id}", response_model=TestRepositoryResponse)
async def get_test_repo(test_repo_id: str):
    """Get test repository by ID."""
    try:
        repo = get_test_repository(test_repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Test repository not found")
        
        return TestRepositoryResponse(
            id=repo['id'],
            name=repo['name'],
            zip_filename=repo['zip_filename'],
            extracted_path=repo['extracted_path'],
            hash=repo['hash'],
            uploaded_at=repo['uploaded_at'],
            last_analyzed_at=repo['last_analyzed_at'],
            status=repo['status'],
            metadata=repo['metadata'],
            schema_name=repo['schema_name']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get test repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get test repository: {str(e)}")


@router.delete("/{test_repo_id}")
async def delete_test_repo(test_repo_id: str):
    """Delete a test repository."""
    try:
        success = delete_test_repository(test_repo_id)
        if not success:
            raise HTTPException(status_code=404, detail="Test repository not found")
        
        return {"message": "Test repository deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete test repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete test repository: {str(e)}")


@router.get("/{test_repo_id}/analysis")
async def get_test_repository_analysis(test_repo_id: str):
    """
    Get analysis results for a specific test repository.
    
    Returns analysis data from the test repository's schema by querying the database.
    """
    try:
        # Get test repository
        test_repo = get_test_repository(test_repo_id)
        if not test_repo:
            raise HTTPException(status_code=404, detail="Test repository not found")
        
        schema_name = test_repo.get('schema_name')
        if not schema_name:
            raise HTTPException(status_code=400, detail="Test repository has no schema. Please run analysis first.")
        
        # Import database connection with schema support
        import sys
        project_root = Path(__file__).parent.parent.parent.parent
        deterministic_path = project_root / "deterministic"
        if str(deterministic_path) not in sys.path:
            sys.path.insert(0, str(deterministic_path))
        
        from db_connection import get_connection_with_schema
        
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
            "last_updated": None,
            "test_repository": {
                "id": test_repo.get('id'),
                "name": test_repo.get('name'),
                "schema_name": schema_name,
                "status": test_repo.get('status')
            },
            # Summary statistics for frontend
            "totalTests": 0,
            "testFiles": 0,
            "totalTestClasses": 0,
            "totalTestMethods": 0,
            "functionsExtracted": 0,
            "modulesIdentified": 0,
            "totalDependencies": 0,
            "totalProductionClasses": 0,
            "framework": "unknown"
        }
        
        # Query database using the test repository's schema
        with get_connection_with_schema(schema_name) as conn:
            cursor = conn.cursor()
            
            # Get test registry
            try:
                cursor.execute(f"""
                    SELECT test_id, method_name, class_name, file_path, test_type, line_number, language
                    FROM {schema_name}.test_registry
                    ORDER BY test_id
                """)
                rows = cursor.fetchall()
                tests = []
                for row in rows:
                    tests.append({
                        'test_id': row[0],
                        'method_name': row[1] or '',
                        'class_name': row[2] or '',
                        'file_path': row[3] or '',
                        'test_type': row[4] or 'unknown',
                        'line_number': row[5],
                        'language': row[6] or 'python'
                    })
                # Add statistics to test registry
                total_tests = len(tests)
                total_classes = len(set(t['class_name'] for t in tests if t.get('class_name')))
                results['test_registry'] = {
                    'tests': tests,
                    'total_tests': total_tests,
                    'total_classes': total_classes,
                    'total_files': len(set(t['file_path'] for t in tests if t.get('file_path')))
                }
            except Exception as e:
                logger.warning(f"Failed to load test_registry: {e}")
                logger.exception(e)
            
            # Get test metadata (join with test_registry to get file_path)
            try:
                cursor.execute(f"""
                    SELECT 
                        tm.test_id, 
                        tm.description, 
                        tm.markers, 
                        tm.is_async, 
                        tm.is_parameterized,
                        tr.file_path
                    FROM {schema_name}.test_metadata tm
                    LEFT JOIN {schema_name}.test_registry tr ON tm.test_id = tr.test_id
                    ORDER BY tm.test_id
                """)
                rows = cursor.fetchall()
                metadata = []
                for row in rows:
                    metadata.append({
                        'test_id': row[0],
                        'description': row[1] or '',
                        'markers': row[2] if row[2] else [],
                        'is_async': row[3] or False,
                        'is_parameterized': row[4] or False,
                        'file_path': row[5] or ''
                    })
                results['test_metadata'] = {'test_metadata': metadata}
            except Exception as e:
                logger.warning(f"Failed to load test_metadata: {e}")
            
            # Get static dependencies
            try:
                cursor.execute(f"""
                    SELECT test_id, referenced_class
                    FROM {schema_name}.test_dependencies
                    ORDER BY test_id
                """)
                rows = cursor.fetchall()
                dependencies_obj = {}
                for row in rows:
                    test_id = row[0]
                    ref_class = row[1]
                    if test_id not in dependencies_obj:
                        dependencies_obj[test_id] = []
                    if ref_class:
                        dependencies_obj[test_id].append(ref_class)
                results['static_dependencies'] = {'dependencies': dependencies_obj}
            except Exception as e:
                logger.warning(f"Failed to load static_dependencies: {e}")
            
            # Get reverse index
            try:
                cursor.execute(f"""
                    SELECT production_class, test_id, reference_type
                    FROM {schema_name}.reverse_index
                    ORDER BY production_class, test_id
                """)
                rows = cursor.fetchall()
                reverse_index_obj = {}
                for row in rows:
                    prod_class = row[0]
                    test_id = row[1]
                    if prod_class not in reverse_index_obj:
                        reverse_index_obj[prod_class] = []
                    if test_id:
                        reverse_index_obj[prod_class].append(test_id)
                # Add statistics to reverse index
                total_production_classes = len(reverse_index_obj)
                total_mappings = sum(len(tests) for tests in reverse_index_obj.values())
                results['reverse_index'] = {
                    'reverse_index': reverse_index_obj,
                    'total_production_classes': total_production_classes,
                    'total_mappings': total_mappings
                }
            except Exception as e:
                logger.warning(f"Failed to load reverse_index: {e}")
                logger.exception(e)
            
            # Get function mappings (join with test_registry to get file_path)
            try:
                cursor.execute(f"""
                    SELECT 
                        tfm.test_id, 
                        tfm.module_name, 
                        tfm.function_name,
                        tr.file_path
                    FROM {schema_name}.test_function_mapping tfm
                    LEFT JOIN {schema_name}.test_registry tr ON tfm.test_id = tr.test_id
                    ORDER BY tfm.test_id
                """)
                rows = cursor.fetchall()
                function_mappings = []
                for row in rows:
                    function_mappings.append({
                        'test_id': row[0],
                        'module_name': row[1] or '',
                        'function_name': row[2] or '',
                        'file_path': row[3] or '',
                        'functions_tested': [f"{row[1]}.{row[2]}" if row[1] and row[2] else row[2] or '']
                    })
                results['function_calls'] = {'function_mappings': function_mappings}
            except Exception as e:
                logger.warning(f"Failed to load function_calls: {e}")
            
            # Get test structure
            try:
                # Check if test_count column exists
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = %s 
                    AND table_name = 'test_structure'
                    AND column_name = 'test_count'
                """, (schema_name,))
                has_test_count = cursor.fetchone() is not None
                
                if has_test_count:
                    cursor.execute(f"""
                        SELECT category, directory_path, test_count
                        FROM {schema_name}.test_structure
                        ORDER BY category, directory_path
                    """)
                else:
                    # Fallback: use 0 for test_count if column doesn't exist
                    cursor.execute(f"""
                        SELECT category, directory_path, 0 as test_count
                        FROM {schema_name}.test_structure
                        ORDER BY category, directory_path
                    """)
                
                rows = cursor.fetchall()
                structure = {
                    'categories': [],
                    'test_categories': []
                }
                for row in rows:
                    structure['test_categories'].append({
                        'category': row[0] or '',
                        'directory_path': row[1] or '',
                        'test_count': row[2] if len(row) > 2 else 0
                    })
                results['test_structure'] = structure
            except Exception as e:
                logger.warning(f"Failed to load test_structure: {e}")
            
            cursor.close()
        
        # Calculate summary statistics from loaded data
        if results.get('test_registry'):
            results['totalTests'] = results['test_registry'].get('total_tests', len(results['test_registry'].get('tests', [])))
            results['totalTestClasses'] = results['test_registry'].get('total_classes', 0)
            results['totalTestMethods'] = results['totalTests']
        
        if results.get('test_files'):
            test_files_data = results['test_files']
            results['testFiles'] = test_files_data.get('total_files', 0)
        
        # Calculate modules from test registry (unique packages)
        if results.get('test_registry'):
            tests = results['test_registry'].get('tests', [])
            # Count unique packages/modules
            packages = set()
            for test in tests:
                pkg = test.get('package', '')
                if pkg:
                    packages.add(pkg)
            results['modulesIdentified'] = len(packages)
        
        if results.get('static_dependencies'):
            deps = results['static_dependencies'].get('dependencies', {})
            # Use total_imports if available (actual imports), otherwise use total_references
            if 'total_imports' in results['static_dependencies']:
                results['totalDependencies'] = results['static_dependencies']['total_imports']
            elif 'total_references' in results['static_dependencies']:
                # For backward compatibility, but prefer actual imports
                results['totalDependencies'] = results['static_dependencies']['total_references']
            else:
                # Count only actual imports from test_dependencies array if available
                if 'test_dependencies' in results.get('static_dependencies', {}):
                    test_deps = results['static_dependencies']['test_dependencies']
                    # Count only tests with actual imports (import_count > 0)
                    results['totalDependencies'] = sum(
                        test_dep.get('import_count', 0) 
                        for test_dep in test_deps
                    )
                else:
                    # Fallback: count from dependencies object (may include inferred)
                    results['totalDependencies'] = sum(len(refs) for refs in deps.values())
        
        # Calculate production classes from actual imports only (not inferred)
        if results.get('static_dependencies'):
            # Count unique production classes from actual imports only
            production_classes = set()
            # Check if we have test_dependencies array (from JSON)
            if 'test_dependencies' in results.get('static_dependencies', {}):
                test_deps = results['static_dependencies']['test_dependencies']
                for test_dep in test_deps:
                    # Only count classes from actual imports (import_count > 0)
                    # and exclude inferred references
                    if test_dep.get('import_count', 0) > 0:
                        # Only count classes that are in reference_types (actual imports)
                        ref_types = test_dep.get('reference_types', {})
                        for ref_class in test_dep.get('referenced_classes', []):
                            # Only include if it's marked as direct_import (actual import)
                            if ref_types.get(ref_class) == 'direct_import':
                                production_classes.add(ref_class)
            else:
                # Fallback: count from dependencies object
                deps = results['static_dependencies'].get('dependencies', {})
                for test_id, refs in deps.items():
                    production_classes.update(refs)
            results['totalProductionClasses'] = len(production_classes)
        elif results.get('reverse_index'):
            # Fallback: use reverse_index but note it may include inferred
            results['totalProductionClasses'] = results['reverse_index'].get('total_production_classes', 0)
        
        if results.get('function_calls'):
            # Use total_mappings from JSON if available, otherwise count function mappings
            if 'total_mappings' in results['function_calls']:
                results['functionsExtracted'] = results['function_calls']['total_mappings']
            else:
                results['functionsExtracted'] = len(results['function_calls'].get('function_mappings', []))
        
        if results.get('framework_detection'):
            results['framework'] = results['framework_detection'].get('framework') or \
                                 results['framework_detection'].get('primary_framework') or \
                                 results['framework_detection'].get('detected_framework', 'unknown')
        
        # Try to load summary report from JSON file (if available)
        # Use schema-specific output directory
        try:
            import json
            project_root = Path(__file__).parent.parent.parent.parent
            # Try schema-specific directory first, then fallback to default
            output_dirs = [
                project_root / "test_analysis" / "outputs" / schema_name,
                project_root / "test_analysis" / "outputs"
            ]
            
            summary_path = None
            for output_dir in output_dirs:
                candidate = output_dir / "08_summary_report.json"
                if candidate.exists():
                    summary_path = candidate
                    break
            
            if summary_path and summary_path.exists():
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                    results['summary_report'] = summary_data.get('data', summary_data)
                    # Set last_updated from file mtime
                    from datetime import datetime
                    results["last_updated"] = datetime.fromtimestamp(summary_path.stat().st_mtime).isoformat()
        except Exception as e:
            logger.warning(f"Failed to load summary_report from file: {e}")
        
        # Try to load framework detection from JSON file (if available)
        try:
            framework_path = None
            for output_dir in output_dirs:
                candidate = output_dir / "02_framework_detection.json"
                if candidate.exists():
                    framework_path = candidate
                    break
            
            if framework_path and framework_path.exists():
                with open(framework_path, 'r', encoding='utf-8') as f:
                    framework_data = json.load(f)
                    framework_file_data = framework_data.get('data', framework_data)
                    if 'primary_framework' in framework_file_data and 'detected_framework' not in framework_file_data:
                        framework_file_data['detected_framework'] = framework_file_data['primary_framework']
                    if 'indicators' in framework_file_data and 'evidence' not in framework_file_data:
                        framework_file_data['evidence'] = framework_file_data.get('indicators', {})
                    results['framework_detection'] = framework_file_data
        except Exception as e:
            logger.warning(f"Failed to load framework_detection from file: {e}")
        
        # Try to load test files from JSON file (if available)
        try:
            test_files_path = None
            for output_dir in output_dirs:
                candidate = output_dir / "01_test_files.json"
                if candidate.exists():
                    test_files_path = candidate
                    break
            
            if test_files_path and test_files_path.exists():
                with open(test_files_path, 'r', encoding='utf-8') as f:
                    test_files_data = json.load(f)
                    test_files_content = test_files_data.get('data', test_files_data)
                    
                    # Transform line_count to lines for frontend compatibility
                    if 'files' in test_files_content and isinstance(test_files_content['files'], list):
                        for file_entry in test_files_content['files']:
                            if 'line_count' in file_entry and 'lines' not in file_entry:
                                file_entry['lines'] = file_entry['line_count']
                    
                    results['test_files'] = test_files_content
        except Exception as e:
            logger.warning(f"Failed to load test_files from file: {e}")
        
        # Always load static dependencies from JSON to get import_count and total_imports
        # (Database doesn't store import_count, so we need JSON for accurate metrics)
        try:
            deps_path = None
            for output_dir in output_dirs:
                candidate = output_dir / "04_static_dependencies.json"
                if candidate.exists():
                    deps_path = candidate
                    break
            
            if deps_path and deps_path.exists():
                with open(deps_path, 'r', encoding='utf-8') as f:
                    deps_data = json.load(f).get('data', {})
                    # Convert test_dependencies array to dependencies object format
                    deps_obj = {}
                    total_imports = 0
                    for test_dep in deps_data.get('test_dependencies', []):
                        test_id = test_dep.get('test_id')
                        ref_classes = test_dep.get('referenced_classes', [])
                        if test_id:
                            deps_obj[test_id] = ref_classes
                            total_imports += test_dep.get('import_count', 0)
                    
                    # Merge with existing database data or replace it
                    if results.get('static_dependencies'):
                        # Merge: keep database dependencies, but add JSON metadata
                        results['static_dependencies'].update({
                            'total_tests': deps_data.get('total_tests', 0),
                            'tests_with_dependencies': deps_data.get('tests_with_dependencies', 0),
                            'total_references': deps_data.get('total_references', 0),  # Actual imports only
                            'total_imports': total_imports,
                            'test_dependencies': deps_data.get('test_dependencies', []),  # Keep for production class calculation
                        })
                    else:
                        # No database data, use JSON data
                        results['static_dependencies'] = {
                            'dependencies': deps_obj,
                            'total_tests': deps_data.get('total_tests', 0),
                            'tests_with_dependencies': deps_data.get('tests_with_dependencies', 0),
                            'total_references': deps_data.get('total_references', 0),  # Actual imports only
                            'total_imports': total_imports,
                            'test_dependencies': deps_data.get('test_dependencies', []),  # Keep for production class calculation
                        }
        except Exception as e:
            logger.warning(f"Failed to load static_dependencies from file: {e}")
        
        # Load function calls from JSON if database is empty
        if not results.get('function_calls') or not results.get('function_calls', {}).get('function_mappings'):
            try:
                func_path = None
                for output_dir in output_dirs:
                    candidate = output_dir / "04b_function_calls.json"
                    if candidate.exists():
                        func_path = candidate
                        break
                
                if func_path and func_path.exists():
                    with open(func_path, 'r', encoding='utf-8') as f:
                        func_data = json.load(f).get('data', {})
                        results['function_calls'] = {
                            'function_mappings': func_data.get('test_function_mappings', []),
                            'total_tests': func_data.get('total_tests', 0),
                            'tests_with_function_calls': func_data.get('tests_with_function_calls', 0),
                            'total_mappings': func_data.get('total_mappings', 0)
                        }
            except Exception as e:
                logger.warning(f"Failed to load function_calls from file: {e}")
        
        # Load reverse index from JSON if database is empty
        if not results.get('reverse_index') or not results.get('reverse_index', {}).get('reverse_index'):
            try:
                rev_path = None
                for output_dir in output_dirs:
                    candidate = output_dir / "06_reverse_index.json"
                    if candidate.exists():
                        rev_path = candidate
                        break
                
                if rev_path and rev_path.exists():
                    with open(rev_path, 'r', encoding='utf-8') as f:
                        rev_data = json.load(f).get('data', {})
                        results['reverse_index'] = {
                            'reverse_index': rev_data.get('reverse_index', {}),
                            'total_production_classes': rev_data.get('total_production_classes', 0),
                            'total_mappings': rev_data.get('total_mappings', 0)
                        }
            except Exception as e:
                logger.warning(f"Failed to load reverse_index from file: {e}")
        
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get test repository analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get test repository analysis: {str(e)}")


@router.post("/{test_repo_id}/analyze", response_model=TestRepositoryAnalysisResponse)
async def analyze_test_repository(test_repo_id: str):
    """
    Run test analysis on a specific test repository.
    
    This will:
    1. Create tables in the test repository's schema
    2. Run the analysis pipeline
    3. Store results in the schema
    """
    try:
        # Get test repository
        test_repo = get_test_repository(test_repo_id)
        if not test_repo:
            raise HTTPException(status_code=404, detail="Test repository not found")
        
        extracted_path = test_repo.get('extracted_path')
        schema_name = test_repo.get('schema_name')
        
        if not extracted_path:
            raise HTTPException(status_code=400, detail="Test repository has no extracted path")
        
        if not Path(extracted_path).exists():
            raise HTTPException(status_code=400, detail=f"Extracted path does not exist: {extracted_path}")
        
        # Update status to analyzing
        update_test_repository_status(test_repo_id, 'analyzing')
        
        try:
            # Create tables in schema if needed
            if schema_name:
                import sys
                # Add deterministic to path
                project_root = Path(__file__).parent.parent.parent.parent
                deterministic_path = project_root / "deterministic"
                if str(deterministic_path) not in sys.path:
                    sys.path.insert(0, str(deterministic_path))
                
                from db_connection import get_connection, create_schema_if_not_exists
                # Import create_all_tables_in_schema from 01_create_tables
                import importlib.util
                create_tables_path = deterministic_path / "01_create_tables.py"
                spec = importlib.util.spec_from_file_location("create_tables", create_tables_path)
                create_tables_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(create_tables_module)
                create_all_tables_in_schema = create_tables_module.create_all_tables_in_schema
                
                # Create schema if it doesn't exist
                create_schema_if_not_exists(schema_name)
                
                # Create all tables in the schema (without schema_def - will be created later in analysis)
                with get_connection() as conn:
                    create_all_tables_in_schema(conn, schema_name, None)
            
            # Run analysis pipeline
            results = await analysis_service.run_pipeline(
                repo_path=extracted_path,
                test_repo_id=test_repo_id,
                schema_name=schema_name
            )
            
            # Update status to ready
            update_test_repository_status(test_repo_id, 'ready')
            
            return TestRepositoryAnalysisResponse(
                status="completed",
                test_repository_id=test_repo_id,
                schema_name=schema_name or "",
                files_analyzed=results.get("files_analyzed", 0),
                test_files=results.get("test_files", 0),
                total_tests=results.get("total_tests", 0),
                message="Analysis completed successfully"
            )
        except Exception as e:
            # Update status to error
            update_test_repository_status(test_repo_id, 'error')
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze test repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze test repository: {str(e)}")


@router.post("/{test_repo_id}/regenerate-embeddings")
async def regenerate_embeddings(test_repo_id: str):
    """
    Regenerate embeddings for a specific test repository.
    
    This will:
    1. Load test data from the existing analysis
    2. Generate embeddings using the configured embedding provider
    3. Store embeddings in Pinecone
    
    NOTE: This does NOT run the full analysis pipeline (no table creation, data loading, etc.)
    """
    try:
        # Get test repository
        test_repo = get_test_repository(test_repo_id)
        if not test_repo:
            raise HTTPException(status_code=404, detail="Test repository not found")
        
        extracted_path = test_repo.get('extracted_path')
        schema_name = test_repo.get('schema_name')
        
        if not extracted_path:
            raise HTTPException(status_code=400, detail="Test repository has no extracted path")
        
        if not Path(extracted_path).exists():
            raise HTTPException(status_code=400, detail=f"Extracted path does not exist: {extracted_path}")
        
        if not schema_name:
            raise HTTPException(status_code=400, detail="Test repository has no schema. Please run analysis first.")
        
        # Check if analysis output files exist (required for embedding generation)
        project_root = Path(__file__).parent.parent.parent.parent
        output_dir = project_root / "test_analysis" / "outputs" / schema_name
        registry_json = output_dir / "03_test_registry.json"
        metadata_json = output_dir / "05_test_metadata.json"
        
        if not registry_json.exists() or not metadata_json.exists():
            raise HTTPException(
                status_code=400,
                detail="Analysis output files not found. Please run analysis first before regenerating embeddings."
            )
        
        # Set environment variables for embedding generation
        import os
        env = os.environ.copy()
        env['TEST_REPO_ID'] = test_repo_id
        env['TEST_REPO_SCHEMA'] = schema_name
        
        # Run only embedding generation (not full analysis)
        embedding_script = project_root / "semantic_retrieval" / "embedding_generator.py"
        if not embedding_script.exists():
            raise HTTPException(status_code=500, detail="Embedding generator script not found")
        
        import subprocess
        import sys
        
        logger.info(f"Regenerating embeddings for test repository: {test_repo_id}")
        
        result = subprocess.run(
            [sys.executable, str(embedding_script)],
            cwd=str(embedding_script.parent.parent),
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes timeout
            env=env
        )
        
        if result.returncode == 0:
            # Check output for warnings about no embeddings stored
            output_text = result.stdout + result.stderr
            if "No embeddings were stored" in output_text or "WARNING: No embeddings were stored" in output_text:
                logger.warning("Embedding generation completed but no embeddings were stored")
                return {
                    "status": "completed_with_warnings",
                    "message": "Embedding generation completed but no embeddings were stored. Check logs for details.",
                    "output": output_text
                }
            else:
                logger.info("Embedding generation completed successfully")
                return {
                    "status": "completed",
                    "message": "Embeddings regenerated successfully"
                }
        else:
            error_msg = f"Embedding generation failed (exit code {result.returncode})"
            logger.error(f"{error_msg}: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"{error_msg}. Check server logs for details."
            )
            
    except subprocess.TimeoutExpired:
        logger.error("Embedding generation timed out")
        raise HTTPException(status_code=500, detail="Embedding generation timed out after 30 minutes")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate embeddings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to regenerate embeddings: {str(e)}")


@router.post("/repositories/{repo_id}/bind-test-repo")
async def bind_test_repo_to_repo(
    repo_id: str,
    request: BindTestRepositoryRequest
):
    """Bind a test repository to a code repository."""
    try:
        # Verify repository exists
        repo = get_repository_by_id(repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Verify test repository exists
        test_repo = get_test_repository(request.test_repository_id)
        if not test_repo:
            raise HTTPException(status_code=404, detail="Test repository not found")
        
        # Bind
        success = bind_test_repository_to_repo(
            repository_id=repo_id,
            test_repository_id=request.test_repository_id,
            is_primary=request.is_primary or False
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to bind test repository")
        
        return {"message": "Test repository bound successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bind test repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to bind test repository: {str(e)}")


@router.delete("/repositories/{repo_id}/unbind-test-repo/{test_repo_id}")
async def unbind_test_repo_from_repo(repo_id: str, test_repo_id: str):
    """Unbind a test repository from a code repository."""
    try:
        success = unbind_test_repository_from_repo(repo_id, test_repo_id)
        if not success:
            raise HTTPException(status_code=404, detail="Binding not found")
        
        return {"message": "Test repository unbound successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unbind test repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to unbind test repository: {str(e)}")


@router.get("/repositories/{repo_id}/test-repositories", response_model=List[TestRepositoryResponse])
async def get_repo_test_repositories(repo_id: str):
    """Get all test repositories bound to a code repository."""
    try:
        bound_repos = get_bound_test_repositories(repo_id)
        return [
            TestRepositoryResponse(
                id=repo['id'],
                name=repo['name'],
                zip_filename=repo['zip_filename'],
                extracted_path=repo['extracted_path'],
                hash=repo['hash'],
                uploaded_at=repo['uploaded_at'],
                last_analyzed_at=repo['last_analyzed_at'],
                status=repo['status'],
                metadata=repo['metadata'],
                schema_name=repo['schema_name'],
                bound_repositories=None  # Not applicable here
            )
            for repo in bound_repos
        ]
    except Exception as e:
        logger.error(f"Failed to get bound test repositories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get bound test repositories: {str(e)}")


@router.put("/repositories/{repo_id}/primary-test-repo/{test_repo_id}")
async def set_primary_test_repo(repo_id: str, test_repo_id: str):
    """Set a test repository as primary for a code repository."""
    try:
        success = bind_test_repository_to_repo(
            repository_id=repo_id,
            test_repository_id=test_repo_id,
            is_primary=True
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to set primary test repository")
        
        return {"message": "Primary test repository set successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set primary test repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to set primary test repository: {str(e)}")
