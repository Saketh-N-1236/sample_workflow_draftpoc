"""Service for running test selection."""

import sys
from pathlib import Path
from typing import Dict, Optional
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class SelectionService:
    """Service for executing test selection."""
    
    def __init__(self):
        """Initialize selection service."""
        # Get project root (parent of web_platform)
        self.project_root = Path(__file__).parent.parent.parent
        if not (self.project_root / "test_analysis").exists():
            # Try alternative path
            self.project_root = Path(__file__).parent.parent
        
        # Verify git_diff_processor exists
        processor_module = self.project_root / "git_diff_processor" / "process_diff_programmatic.py"
        if not processor_module.exists():
            logger.warning(f"Git diff processor module not found: {processor_module}")
    
    async def run_selection_with_diff(self, diff_data: Dict, repository_id: Optional[str] = None) -> Dict:
        """
        Run test selection based on git diff data (from API).
        
        Args:
            diff_data: Dictionary with diff content, changed_files, and stats
            repository_id: Optional repository ID for audit logging
            
        Returns:
            Dictionary with test selection results
        """
        import time
        start_time = time.time()
        
        try:
            diff_content = diff_data.get("diff", "")
            
            if not diff_content:
                logger.warning("Empty diff content provided")
                return {
                    "total_tests": 0,
                    "ast_matches": 0,
                    "semantic_matches": 0,
                    "tests": [],
                    "error": "No diff content provided"
                }
            
            # Import the programmatic processor
            try:
                from git_diff_processor.process_diff_programmatic import process_diff_and_select_tests
            except ImportError as e:
                logger.error(f"Failed to import git_diff_processor: {e}")
                # Fallback: try importing from the main module
                sys.path.insert(0, str(self.project_root))
                from git_diff_processor.process_diff_programmatic import process_diff_and_select_tests
            
            # Get test repository path from environment (dynamic)
            test_repo_path = None
            try:
                import os
                test_repo_path = os.getenv('TEST_REPO_PATH')
                if test_repo_path:
                    logger.info(f"Using test repository path from environment: {test_repo_path}")
            except Exception:
                pass
            
            # Process the diff and get test selection results (works dynamically with any repository)
            logger.info("Processing git diff for test selection...")
            logger.info(f"Diff content length: {len(diff_content)} characters")
            logger.info(f"Changed files in diff: {len(diff_content.split('diff --git')) - 1}")
            
            results = await process_diff_and_select_tests(
                diff_content=diff_content,
                project_root=self.project_root,
                use_semantic=True,
                test_repo_path=test_repo_path  # Optional - works without it too
            )
            
            logger.info(f"Test selection completed: {results.get('total_tests', 0)} tests selected")
            logger.info(f"  - AST matches: {results.get('ast_matches', 0)}")
            logger.info(f"  - Semantic matches: {results.get('semantic_matches', 0)}")
            logger.info(f"  - Tests list length: {len(results.get('tests', []))}")
            if results.get('tests'):
                logger.info(f"  - First test: {results['tests'][0]}")
            
            # Enhance results with semantic-specific details
            enhanced_results = self._enhance_selection_results(results)
            logger.info(f"Enhanced results - total_tests: {enhanced_results.get('total_tests', 0)}")
            logger.info(f"Enhanced results - tests list length: {len(enhanced_results.get('tests', []))}")
            
            # Include LLM scores, confidence distribution, test suites, and LLM input/output from results
            if results.get('llm_scores'):
                enhanced_results['llm_scores'] = results.get('llm_scores')
            if results.get('confidence_distribution'):
                enhanced_results['confidence_distribution'] = results.get('confidence_distribution')
            if results.get('test_suites'):
                enhanced_results['test_suites'] = results.get('test_suites')
            if results.get('llm_input_output'):
                enhanced_results['llm_input_output'] = results.get('llm_input_output')
            
            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Audit logging
            if repository_id:
                try:
                    from services.audit_service import log_selection_run
                    
                    changed_files_count = len(diff_data.get('changedFiles', []))
                    selected_tests_count = enhanced_results.get('total_tests', 0)
                    # Get confidence distribution from results or calculate it
                    confidence_distribution = enhanced_results.get('confidence_distribution')
                    if not confidence_distribution:
                        # Calculate if not provided
                        confidence_distribution = {'high': 0, 'medium': 0, 'low': 0}
                        for test in enhanced_results.get('tests', []):
                            score = test.get('confidence_score', 0)
                            if score >= 70:
                                confidence_distribution['high'] += 1
                            elif score >= 50:
                                confidence_distribution['medium'] += 1
                            else:
                                confidence_distribution['low'] += 1
                    llm_used = bool(enhanced_results.get('llm_scores'))
                    threshold_exceeded = False  # Threshold exceeded is handled in API route before calling this
                    
                    log_selection_run(
                        repository_id=repository_id,
                        changed_files_count=changed_files_count,
                        selected_tests_count=selected_tests_count,
                        confidence_scores=confidence_distribution,
                        llm_used=llm_used,
                        execution_time_ms=execution_time_ms,
                        threshold_exceeded=threshold_exceeded
                    )
                except Exception as e:
                    logger.warning(f"Failed to log audit entry: {e}")
            
            # Log diagnostics if available
            if enhanced_results.get('diagnostics'):
                diag = enhanced_results['diagnostics']
                logger.info(f"Diagnostics:")
                logger.info(f"  - Parsed files: {diag.get('parsed_files', 0)}")
                logger.info(f"  - Parsed classes: {diag.get('parsed_classes', 0)}")
                logger.info(f"  - Search exact matches: {diag.get('search_exact_matches', 0)}")
                logger.info(f"  - DB reverse_index: {diag.get('db_reverse_index_count', 0)}")
                logger.info(f"  - DB test_registry: {diag.get('db_test_registry_count', 0)}")
            
            return enhanced_results
            
        except Exception as e:
            logger.error(f"Test selection failed: {e}", exc_info=True)
            return {
                "total_tests": 0,
                "ast_matches": 0,
                "semantic_matches": 0,
                "tests": [],
                "semantic_match_details": [],
                "ast_match_details": [],
                "overlap_count": 0,
                "error": str(e)
            }
    
    def _enhance_selection_results(self, results: Dict) -> Dict:
        """
        Enhance selection results with semantic-specific details.
        
        Separates AST and semantic matches, calculates overlap, and formats
        match details for the enhanced response model.
        """
        from api.models.repository import SemanticMatch
        
        # Extract semantic and AST match details
        semantic_match_details = []
        ast_match_details = []
        ast_test_ids = set()
        semantic_test_ids = set()
        
        # Process tests to identify match types
        # Also check if we have semantic_results separately (from process_diff_programmatic)
        semantic_results_tests = {}
        if 'semantic_results' in results:
            for sem_test in results.get('semantic_results', {}).get('tests', []):
                test_id = sem_test.get('test_id')
                if test_id:
                    semantic_results_tests[test_id] = {
                        'similarity': sem_test.get('similarity', 0.0),
                        'test': sem_test
                    }
        
        # Get match_details from results if available
        match_details_dict = results.get('match_details', {})
        
        for test in results.get('tests', []):
            test_id = test.get('test_id')
            if not test_id:
                continue
                
            match_type = test.get('match_type', 'unknown')
            confidence_score = test.get('confidence_score', 0)
            
            # Check if this test has similarity score (from semantic search)
            similarity = test.get('similarity')
            if similarity is None and test_id in semantic_results_tests:
                similarity = semantic_results_tests[test_id]['similarity']
            
            # First check if flags are already set (from process_diff_programmatic)
            # These are the most reliable indicators
            is_ast = test.get('is_ast_match', False)
            is_semantic = test.get('is_semantic_match', False)
            
            # If flags not set, determine from match_details and test properties
            if not (is_ast or is_semantic):
                # Check match_details to determine match types more accurately
                # Look for semantic matches in match_details
                has_semantic_in_details = False
                has_ast_in_details = False
                
                # Get match_details for this test
                test_match_details = match_details_dict.get(test_id, [])
                if isinstance(test_match_details, list):
                    for match_detail in test_match_details:
                        match_detail_type = match_detail.get('type', '')
                        if match_detail_type == 'semantic':
                            has_semantic_in_details = True
                            # Extract similarity if available
                            if similarity is None:
                                similarity = match_detail.get('similarity')
                        elif match_detail_type in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'direct_test_file', 'module_pattern', 'integration']:
                            has_ast_in_details = True
                
                # Check if test has semantic match indicators
                # IMPORTANT: Only mark as semantic if it was ORIGINALLY found by semantic search
                # Don't rely on similarity value alone, as it might have been added during merging
                is_semantic = (
                    has_semantic_in_details or
                    test_id in semantic_results_tests or
                    'semantic' in str(match_type).lower()
                )
                
                # Check if test has AST match indicators
                # More comprehensive AST detection
                is_ast = (
                    has_ast_in_details or
                    match_type in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'module_pattern'] or
                    test.get('matched_classes') and len(test.get('matched_classes', [])) > 0 or
                    (confidence_score >= 70 and match_type != 'semantic') or
                    (match_type not in ['semantic', 'unknown'] and match_type != '')
                )
            
            # Ensure flags are set on test object (update if not already set or if we detected differently)
            test['is_ast_match'] = is_ast
            test['is_semantic_match'] = is_semantic
            
            if is_semantic:
                # Use similarity from test, semantic_results, or default
                final_similarity = 0.0
                if similarity is not None and isinstance(similarity, (int, float)):
                    final_similarity = float(similarity)
                elif test_id in semantic_results_tests:
                    final_similarity = float(semantic_results_tests[test_id]['similarity'])
                
                if final_similarity > 0:
                    semantic_match_details.append(
                        SemanticMatch(
                            test_id=test_id,
                            similarity=final_similarity,
                            confidence='high' if final_similarity >= 0.6 else 'medium' if final_similarity >= 0.4 else 'low',
                            query_used=None  # Could be extracted from match_details if available
                        )
                    )
                    semantic_test_ids.add(test_id)
            
            if is_ast:
                # Add to AST matches (even if also semantic - we'll calculate overlap separately)
                if test_id not in ast_test_ids:
                    ast_match_details.append({
                        'test_id': test_id,
                        'match_type': match_type if match_type != 'unknown' else 'ast_match',
                        'confidence_score': confidence_score,
                        'matched_classes': test.get('matched_classes', [])
                    })
                    ast_test_ids.add(test_id)
        
        # Calculate overlap (tests found by both)
        overlap_count = len(ast_test_ids & semantic_test_ids)
        
        # Get embedding status (simplified - could be enhanced)
        embedding_status = None
        try:
            import os
            from semantic_retrieval.config import VECTOR_BACKEND
            embedding_status = {
                'backend': VECTOR_BACKEND.lower(),
                'available': True
            }
        except Exception:
            embedding_status = {'available': False}
        
        # Get semantic config (from environment or defaults)
        semantic_config = {
            'use_semantic': True,
            'similarity_threshold': None,  # Uses adaptive thresholds
            'max_results': 10000  # Removed limit - use high value
        }
        
        # Enhance results
        enhanced = results.copy()
        enhanced['semantic_match_details'] = [m.dict() for m in semantic_match_details]
        enhanced['ast_match_details'] = ast_match_details
        enhanced['overlap_count'] = overlap_count
        enhanced['embedding_status'] = embedding_status
        enhanced['semantic_config'] = semantic_config
        
        return enhanced