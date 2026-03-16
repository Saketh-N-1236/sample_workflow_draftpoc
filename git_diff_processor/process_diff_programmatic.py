"""
Programmatic interface for processing git diff and selecting tests.

This module provides functions that can be called from other services
without printing to console.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directory to path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Add git_diff_processor directory to path for relative imports
_git_diff_processor_dir = Path(__file__).parent
if str(_git_diff_processor_dir) not in sys.path:
    sys.path.insert(0, str(_git_diff_processor_dir))

from deterministic.db_connection import get_connection, get_connection_with_schema, DB_SCHEMA

# Import from utils (try absolute import first, then relative)
try:
    from git_diff_processor.utils.diff_parser import (
        parse_git_diff,
        build_search_queries,
    )
except ImportError:
    # Fallback: use relative import (git_diff_processor dir is already in path)
    from utils.diff_parser import (
        parse_git_diff,
        build_search_queries,
    )

# Import from main processor module (same directory)
# We need to import the functions directly
import importlib.util
processor_path = Path(__file__).parent / "git_diff_processor.py"

# Ensure paths are set before loading the module
# This is critical for the module's imports to work correctly
_git_diff_processor_dir = processor_path.parent
if str(_git_diff_processor_dir) not in sys.path:
    sys.path.insert(0, str(_git_diff_processor_dir))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

spec = importlib.util.spec_from_file_location("git_diff_processor_module", processor_path)
processor_module = importlib.util.module_from_spec(spec)

# Set __file__ and __name__ attributes before execution to help with imports
processor_module.__file__ = str(processor_path)
processor_module.__name__ = "git_diff_processor_module"
processor_module.__package__ = "git_diff_processor"

spec.loader.exec_module(processor_module)

find_affected_tests = processor_module.find_affected_tests
find_tests_ast_only = processor_module.find_tests_ast_only
find_tests_semantic_only = processor_module.find_tests_semantic_only


def build_adaptive_semantic_config(
    search_queries: Dict,
    ast_results: Dict,
    base_config: Optional[Dict] = None,
    num_changed_files: int = 0,
) -> Dict:
    """
    Build semantic search configuration dynamically based on:
      - What the diff contains (functions vs symbols vs file-only changes)
      - What AST already found (if AST is strong, semantic supplements;
        if AST found nothing, semantic must do all the work)
      - Number of changed files (complexity indicator)

    This makes the system accurate for ANY test repository structure —
    it does NOT rely on naming conventions like "standalone" or "cross-dependent".

    Priority rules (higher rule wins when multiple apply):
      1. AST found 0 tests        → lenient (semantic is the only signal)
      2. Function-level changes   → moderate (AST is strong, semantic supplements)
      3. Specific symbol changes  → moderate-lenient (symbol lookup precise, but
                                    semantic catches description-level matches too)
      4. Module-only changes      → lenient (broad AST match, semantic refines)
      5. Complex diff (>3 files)  → add extra query variations

    User-stored values are always respected UNLESS they exceed 0.4
    (values > 0.4 cause false negatives and are silently clamped).
    """
    import logging
    _logger = logging.getLogger(__name__)

    config = dict(base_config or {})

    ast_count = ast_results.get('total_tests', 0)
    has_functions  = bool(search_queries.get('changed_functions'))
    has_exact      = bool(search_queries.get('exact_matches'))   # specific symbols
    has_module     = bool(search_queries.get('module_matches'))

    # ── Determine adaptive defaults ────────────────────────────────────────────
    if ast_count == 0:
        # Semantic is the ONLY signal — must be very lenient and thorough
        adaptive_quality   = 0.2
        adaptive_variations = 5
        adaptive_top_k     = 100
        reason = "AST found 0 tests — semantic working alone"

    elif has_functions:
        # Function-level changes: AST via function_mapping is very precise.
        # Semantic supplements but quality bar can be moderate.
        # Use similarity_threshold=0.4 and quality_threshold=0.35 to filter low-quality noise.
        adaptive_quality   = 0.35
        adaptive_variations = 3
        adaptive_top_k     = 50
        config.setdefault('similarity_threshold', 0.4)
        reason = "function-level changes — AST strong, semantic supplements"

    elif has_exact:
        # Specific symbols (constants, enums, types) detected.
        # AST handles these via reverse_index; semantic catches description matches.
        # Use similarity_threshold=0.45 to avoid pulling in loosely-related regex tests
        # from the same repo (e.g. EMAIL_REGEX tests when PHONE_REGEX changed).
        adaptive_quality   = 0.35
        adaptive_variations = 3
        adaptive_top_k     = 75
        config.setdefault('similarity_threshold', 0.45)
        reason = "specific symbol changes — moderate quality threshold"

    elif has_module:
        # Only generic module matches (whole-file changes, no symbols/functions).
        # AST is coarse here; semantic needs more room to find relevant tests.
        adaptive_quality   = 0.2
        adaptive_variations = 4
        adaptive_top_k     = 75
        reason = "module-only changes — lenient for broad coverage"

    else:
        # Fallback: diff content but nothing parseable → semantic does it all
        adaptive_quality   = 0.2
        adaptive_variations = 4
        adaptive_top_k     = 75
        reason = "no structured matches — semantic fallback"

    # More changed files = more complex diff = more query variations
    if num_changed_files > 3:
        adaptive_variations = min(adaptive_variations + 1, 6)

    # ── Apply: respect user-stored values but clamp anything > 0.4 ────────────
    stored_quality = config.get('quality_threshold')
    if stored_quality is None:
        config['quality_threshold'] = adaptive_quality
    elif stored_quality > 0.4:
        # A threshold above 0.4 reliably causes false negatives — clamp it.
        _logger.info(
            f"Adaptive config: clamped quality_threshold "
            f"{stored_quality} → {adaptive_quality} ({reason})"
        )
        config['quality_threshold'] = adaptive_quality
    # else: stored value is already within safe range — keep it

    # Only fill in variations/top_k if not explicitly set by user
    if config.get('num_query_variations') is None:
        config['num_query_variations'] = adaptive_variations
    if config.get('rerank_top_k') is None:
        config['rerank_top_k'] = adaptive_top_k

    _logger.info(
        f"Adaptive semantic config | quality={config['quality_threshold']} "
        f"| variations={config['num_query_variations']} "
        f"| top_k={config['rerank_top_k']} "
        f"| reason={reason}"
    )
    return config


async def process_diff_and_select_tests(
    diff_content: str,
    project_root: Optional[Path] = None,
    use_semantic: bool = True,
    test_repo_path: Optional[str] = None,
    schema_name: Optional[str] = None,
    file_list: Optional[List[str]] = None,
    semantic_config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Process git diff content and return selected tests.
    
    This function works dynamically with any test repository by querying
    the database directly. The test repository path is optional and only
    used for module resolution if needed.
    
    Args:
        diff_content: Git diff content as string
        project_root: Optional project root path (for parsing, defaults to parent)
        use_semantic: Whether to use semantic search (default: True)
        test_repo_path: Optional test repository path (for module resolution)
        schema_name: Optional schema name for multi-repo support (defaults to DB_SCHEMA)
    
    Returns:
        Dictionary with test selection results:
        {
            'total_tests': int,
            'ast_matches': int,
            'semantic_matches': int,
            'tests': List[Dict],
            'parsed_diff': Dict,
            'search_queries': Dict
        }
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent
    
    # Initialize parser registry for multi-language support (dynamic)
    parser_registry = None
    config = {}
    try:
        from parsers.registry import initialize_registry, get_registry
        from config.config_loader import load_language_configs
        
        config_path = project_root / "config" / "language_configs.yaml"
        if config_path.exists():
            initialize_registry(config_path)
            config = load_language_configs(config_path)
        else:
            initialize_registry()
            config = {}
        
        parser_registry = get_registry()
    except Exception as e:
        # Fallback if parser registry not available - still works for basic parsing
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Parser registry not available: {e}, using basic parsing")
        parser_registry = None  # Explicitly set to None if initialization fails
    
    # Step 1: Parse git diff (works with any diff content)
    # Note: parse_git_diff doesn't need parser_registry - it's used in build_search_queries
    # Pass file_list for GitLab API diffs that don't include file headers
    parsed_diff = parse_git_diff(diff_content, file_list=file_list)
    
    # Step 2: Build search queries (dynamic - works with any file changes)
    # Use test_repo_path if provided, otherwise use project_root
    search_root = Path(test_repo_path) if test_repo_path else project_root
    
    search_queries = build_search_queries(
        parsed_diff['file_changes'],
        parser_registry=parser_registry,
        project_root=search_root,
        config=config,
        diff_content=diff_content
    )
    
    # Step 3: Query database for affected tests
    import logging
    logger = logging.getLogger(__name__)
    
    # Log what we're searching for (for debugging)
    logger.info(f"Processing diff with {len(parsed_diff.get('changed_files', []))} changed files")
    logger.info(f"Search queries - Exact matches: {len(search_queries.get('exact_matches', []))}")
    logger.info(f"Search queries - Module matches: {len(search_queries.get('module_matches', []))}")
    logger.info(f"Search queries - Function changes: {len(search_queries.get('changed_functions', []))}")
    logger.info(f"Search queries - Test file candidates: {len(search_queries.get('test_file_candidates', []))}")
    
    # Use schema-specific connection if schema_name is provided
    target_schema = schema_name or DB_SCHEMA
    connection_func = get_connection_with_schema(target_schema) if schema_name else get_connection()
    
    with connection_func as conn:
        # Debug: Verify schema has data
        with conn.cursor() as cursor:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {target_schema}.test_registry")
                test_count = cursor.fetchone()[0]
                cursor.execute(f"SELECT COUNT(*) FROM {target_schema}.reverse_index")
                reverse_count = cursor.fetchone()[0]
                cursor.execute(f"SELECT COUNT(*) FROM {target_schema}.test_function_mapping")
                func_count = cursor.fetchone()[0]
                logger.info(f"[{target_schema}] Database stats - Tests: {test_count}, Reverse index: {reverse_count}, Function mappings: {func_count}")
            except Exception as e:
                logger.warning(f"[{target_schema}] Could not query database stats: {e}")
        
        # Get AST-based results (this uses all strategies: function-level, direct files, exact, module patterns)
        logger.info(f"Running AST-based test selection (schema: {target_schema})...")
        logger.debug(f"Search queries: exact_matches={len(search_queries.get('exact_matches', []))}, "
                    f"module_matches={len(search_queries.get('module_matches', []))}, "
                    f"changed_functions={len(search_queries.get('changed_functions', []))}, "
                    f"test_file_candidates={len(search_queries.get('test_file_candidates', []))}")
        ast_results = find_tests_ast_only(conn, search_queries, parsed_diff.get('file_changes', []), schema=target_schema)
        logger.info(f"AST-based matching found {ast_results.get('total_tests', 0)} tests")
        
        # Debug: If no AST results, log what was searched
        if ast_results.get('total_tests', 0) == 0:
            logger.warning(f"[{target_schema}] No AST matches found. Search details:")
            if search_queries.get('exact_matches'):
                logger.warning(f"  Exact matches searched: {search_queries['exact_matches'][:5]}")
            if search_queries.get('changed_functions'):
                logger.warning(f"  Functions searched: {[f['module']+'.'+f['function'] for f in search_queries['changed_functions'][:5]]}")
            if search_queries.get('test_file_candidates'):
                logger.warning(f"  Test files searched: {search_queries['test_file_candidates'][:5]}")
        
        # ── Build adaptive semantic config AFTER AST results are known ──────────
        # This makes quality_threshold/num_variations dynamic — no test-category
        # naming convention required.  Works for any test repository structure.
        semantic_config = build_adaptive_semantic_config(
            search_queries=search_queries,
            ast_results=ast_results,
            base_config=semantic_config,
            num_changed_files=len(parsed_diff.get('changed_files', [])),
        )
        # ────────────────────────────────────────────────────────────────────────

        # Get semantic results if enabled
        semantic_results = {'total_tests': 0, 'tests': []}
        if use_semantic:
            try:
                logger.info("Running semantic search...")
                # Use async version since we're in an async context
                from git_diff_processor.git_diff_processor import find_tests_semantic_only_async
                # Resolve test_repo_id:
                # 1. From environment variable
                # 2. From database lookup using schema_name prefix
                # 3. Fall back to None (all repos, less precise)
                import os
                test_repo_id = os.getenv('TEST_REPO_ID')
                if not test_repo_id and schema_name:
                    # schema_name is like "test_repo_261b672a" → look up by ID prefix
                    schema_suffix = schema_name.replace('test_repo_', '')
                    try:
                        with conn.cursor() as _c:
                            _c.execute("""
                                SELECT id FROM planon1.test_repositories
                                WHERE id LIKE %s
                                LIMIT 1
                            """, (f"{schema_suffix}%",))
                            _row = _c.fetchone()
                            if _row:
                                test_repo_id = _row[0]
                                logger.info(f"Resolved test_repo_id from schema: {test_repo_id[:16]}...")
                    except Exception as _lookup_err:
                        logger.debug(f"Could not resolve test_repo_id from schema: {_lookup_err}")
                semantic_results = await find_tests_semantic_only_async(
                    conn, 
                    search_queries, 
                    parsed_diff.get('file_changes', []), 
                    schema=target_schema, 
                    test_repo_id=test_repo_id,
                    semantic_config=semantic_config,
                    diff_content=diff_content  # Pass diff content for Advanced RAG
                )
                logger.info(f"Semantic search found {semantic_results.get('total_tests', 0)} tests")
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}")
                semantic_results = {'total_tests': 0, 'tests': [], 'error': str(e)}
        
        # Use ast_results (from find_tests_ast_only) as the base for combined_results.
        # find_tests_ast_only already runs all AST strategies (0-4a), including the
        # new Strategy 4 (file stem-based sibling test lookup), so it produces a
        # richer result set than find_affected_tests (which lacks Strategy 4).
        # Reusing ast_results avoids a redundant second DB round-trip.
        logger.info("Using AST results as base for combining with semantic results...")
        # IMPORTANT: Save the AST count BEFORE combined_results gets mutated by semantic merge.
        # Since combined_results = ast_results (same dict reference), merging semantic into
        # combined_results would also update ast_results['total_tests'].
        ast_count_snapshot = ast_results.get('total_tests', 0)
        combined_results = ast_results
        logger.info(f"AST base results: {ast_count_snapshot} tests")
        
        # IMPORTANT: Preserve AST match information from match_details BEFORE any filtering
        # Store which tests came from AST (from match_details) so we can mark them correctly later
        ast_test_ids_from_match_details = set()
        combined_match_details = combined_results.get('match_details', {})
        for test_id, matches in combined_match_details.items():
            # Check if this test has any AST match types (not semantic)
            has_ast_match = any(
                m.get('type') in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'direct_test_file', 'module_pattern', 'integration']
                for m in matches
            )
            if has_ast_match:
                ast_test_ids_from_match_details.add(test_id)
        
        # Also preserve original AST test IDs from combined_results before filtering
        # These are tests that were found by AST BEFORE semantic merging
        original_ast_test_ids = {t.get('test_id') for t in combined_results.get('tests', [])}
        
        # Merge semantic results into combined results BEFORE applying threshold
        # This ensures we preserve AST information when merging
        semantic_tests_dict = {}
        # Track which tests were ORIGINALLY found by semantic search (before merging)
        original_semantic_test_ids = set()
        
        if semantic_results.get('tests'):
            logger.info(f"Merging {len(semantic_results.get('tests', []))} semantic results into combined results...")
            semantic_tests_dict = {t.get('test_id'): t for t in semantic_results.get('tests', [])}
            # Track original semantic test IDs (these are tests found by semantic search)
            original_semantic_test_ids = set(semantic_tests_dict.keys())
            combined_tests_dict = {t.get('test_id'): t for t in combined_results.get('tests', [])}
            
            # Add semantic tests that aren't already in combined results
            for test_id, sem_test in semantic_tests_dict.items():
                if test_id not in combined_tests_dict:
                    # New test from semantic only
                    # But check if it had AST matches in match_details (might have been filtered out)
                    has_ast_in_match_details = test_id in ast_test_ids_from_match_details
                    
                    combined_tests_dict[test_id] = sem_test
                    if test_id not in combined_match_details:
                        combined_match_details[test_id] = []
                    # Add semantic match
                    combined_match_details[test_id].append({
                        'type': 'semantic',
                        'similarity': sem_test.get('similarity', 0),
                        'confidence': 'medium'
                    })
                else:
                    # Test found by both - add semantic match detail AND update test object
                    existing_test = combined_tests_dict[test_id]
                    
                    # Update similarity on test object if not already set or if semantic has higher similarity
                    sem_similarity = sem_test.get('similarity', 0)
                    if sem_similarity > 0:
                        existing_similarity = existing_test.get('similarity', 0)
                        if sem_similarity > existing_similarity:
                            existing_test['similarity'] = sem_similarity
                    
                    # Add semantic match detail to match_details
                    if test_id not in combined_match_details:
                        combined_match_details[test_id] = []
                    # Check if semantic already in match_details
                    has_semantic = any(m.get('type') == 'semantic' for m in combined_match_details[test_id])
                    if not has_semantic:
                        combined_match_details[test_id].append({
                            'type': 'semantic',
                            'similarity': sem_similarity,
                            'confidence': 'medium'
                        })
                    else:
                        # Update similarity in existing semantic match if higher
                        for m in combined_match_details[test_id]:
                            if m.get('type') == 'semantic':
                                m['similarity'] = max(m.get('similarity', 0), sem_similarity)
                                break
            
            # Update combined_results with merged data
            combined_results['tests'] = list(combined_tests_dict.values())
            combined_results['match_details'] = combined_match_details
            combined_results['total_tests'] = len(combined_tests_dict)
        
        # LLM Reasoning Step (optional) - AFTER merging semantic results
        # This ensures LLM can assess all candidates (AST + semantic)
        llm_scores_map = {}
        try:
            # Check if LLM reasoning is enabled (can be configured via environment or parameter)
            import os
            use_llm_reasoning = os.getenv('USE_LLM_REASONING', 'true').lower() == 'true'
            
            if use_llm_reasoning:
                logger.info("Running LLM reasoning for top candidates...")
                # Import LLM reasoning service
                # Ensure project root is in path for web_platform imports
                project_root_path = Path(__file__).parent.parent
                if str(project_root_path) not in sys.path:
                    sys.path.insert(0, str(project_root_path))
                
                try:
                    from web_platform.services.llm_reasoning_service import LLMReasoningService
                    llm_service = LLMReasoningService()
                except ImportError as e:
                    logger.warning(f"Failed to import LLM reasoning service: {e}. LLM reasoning will be skipped.")
                    llm_service = None
                
                if llm_service:
                    # Get top 20 candidates by current confidence score (from merged results)
                    top_candidates = sorted(
                        combined_results.get('tests', []),
                        key=lambda t: t.get('confidence_score', 0),
                        reverse=True
                    )[:20]
                    
                    if top_candidates:
                        # Prepare test candidates with match reasons
                        test_candidates = []
                        match_details_dict = combined_results.get('match_details', {})
                        for test in top_candidates:
                            test_id = test.get('test_id')
                            match_reasons = []
                            if test_id in match_details_dict:
                                for match in match_details_dict[test_id]:
                                    match_type = match.get('type', '')
                                    if match_type:
                                        match_reasons.append(match_type)
                            
                            test_candidates.append({
                                'test_id': test_id,
                                'class_name': test.get('class_name'),
                                'method_name': test.get('method_name'),
                                'test_file_path': test.get('test_file_path') or test.get('file_path', ''),
                                'match_reasons': match_reasons
                            })
                        
                        # Build LLM prompt (input) for storage
                        llm_input_prompt = llm_service._build_relevance_prompt(diff_content, test_candidates)
                        
                        # Assess relevance with LLM
                        llm_results = await llm_service.assess_test_relevance(
                            diff_content=diff_content,
                            test_candidates=test_candidates,
                            top_n=20
                        )
                        
                        # Store LLM input and output
                        llm_raw_response = None
                        if llm_results and len(llm_results) > 0:
                            # Get raw response from first result (all have same raw_response)
                            llm_raw_response = llm_results[0].get('raw_response', '')
                        
                        llm_input_output = {
                            'input': llm_input_prompt,
                            'output': llm_raw_response or 'No response available',
                            'assessed_tests_count': len(llm_results)
                        }
                        
                        # Create map of test_id -> llm_score
                        for result in llm_results:
                            test_id = result.get('test_id')
                            if test_id:
                                llm_scores_map[test_id] = {
                                    'llm_score': result.get('llm_score', 0.0),
                                    'llm_explanation': result.get('llm_explanation', '')
                                }
                        
                        logger.info(f"LLM reasoning completed: assessed {len(llm_scores_map)} tests")
                    else:
                        logger.info("No test candidates for LLM reasoning")
                else:
                    logger.info("LLM service not available, skipping LLM reasoning")
            else:
                logger.info("LLM reasoning disabled (USE_LLM_REASONING=false)")
        except Exception as e:
            logger.warning(f"LLM reasoning failed: {e}. Continuing without LLM scores.", exc_info=True)
            llm_scores_map = {}
        
        # Recalculate confidence scores with LLM component and get breakdown
        if llm_scores_map:
            logger.info("Recalculating confidence scores with LLM component...")
            for test in combined_results.get('tests', []):
                test_id = test.get('test_id')
                matches = combined_results.get('match_details', {}).get(test_id, [])
                test_type = test.get('test_type')
                
                if test_id in llm_scores_map:
                    llm_data = llm_scores_map[test_id]
                    # Recalculate with LLM score and get breakdown
                    from git_diff_processor.git_diff_processor import calculate_confidence_score_with_breakdown
                    new_score, breakdown = calculate_confidence_score_with_breakdown(
                        matches,
                        test_type,
                        llm_score=llm_data['llm_score']
                    )
                    test['confidence_score'] = new_score
                    test['llm_score'] = llm_data['llm_score']
                    test['llm_explanation'] = llm_data['llm_explanation']
                    # Add breakdown to test
                    test['confidence_breakdown'] = breakdown
                else:
                    # No LLM score, but still calculate breakdown
                    from git_diff_processor.git_diff_processor import calculate_confidence_score_with_breakdown
                    new_score, breakdown = calculate_confidence_score_with_breakdown(
                        matches,
                        test_type,
                        llm_score=None
                    )
                    test['confidence_score'] = new_score
                    test['confidence_breakdown'] = breakdown
            
            # Re-sort by new confidence scores
            combined_results['tests'] = sorted(
                combined_results.get('tests', []),
                key=lambda t: t.get('confidence_score', 0),
                reverse=True
            )
        else:
            # No LLM scores, but still add breakdown for all tests
            from git_diff_processor.git_diff_processor import calculate_confidence_score_with_breakdown
            for test in combined_results.get('tests', []):
                test_id = test.get('test_id')
                matches = combined_results.get('match_details', {}).get(test_id, [])
                test_type = test.get('test_type')
                _, breakdown = calculate_confidence_score_with_breakdown(
                    matches,
                    test_type,
                    llm_score=None
                )
                test['confidence_breakdown'] = breakdown
        
        # Store LLM input/output in results if available
        try:
            if 'llm_input_output' in locals():
                combined_results['llm_input_output'] = llm_input_output
        except:
            pass
        
        # Apply minimum confidence threshold (0.40 = 40%) AFTER merging and LLM reasoning
        # This ensures we don't lose AST information when filtering
        MIN_CONFIDENCE_THRESHOLD = 0.40
        filtered_tests = []
        for test in combined_results.get('tests', []):
            test_id = test.get('test_id')
            confidence_score = test.get('confidence_score', 0)
            
            # Check if test has LLM score (LLM-assessed tests should be included)
            has_llm_score = test_id in llm_scores_map or test.get('llm_score') is not None
            
            # Check if test has semantic match
            # IMPORTANT: Only mark as semantic if it was ORIGINALLY found by semantic search
            # Don't rely on similarity value alone, as it might have been added during merging
            has_semantic = (
                test_id in original_semantic_test_ids or
                any(m.get('type') == 'semantic' for m in combined_match_details.get(test_id, []))
            )
            
            # Check if test has AST match (from match_details or was in original AST results)
            has_ast = (
                test_id in ast_test_ids_from_match_details or
                test_id in original_ast_test_ids or
                any(m.get('type') in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'direct_test_file', 'module_pattern', 'integration'] 
                    for m in combined_match_details.get(test_id, []))
            )
            
            # Include test if:
            # 1. Passes threshold, OR
            # 2. Has LLM score (LLM-assessed tests are high priority), OR
            # 3. Has semantic match (semantic matches are included regardless of AST score), OR
            # 4. Has AST match ONLY (AST-only tests should be included because they're direct matches with high confidence)
            passes_threshold = (confidence_score / 100.0) >= MIN_CONFIDENCE_THRESHOLD
            
            # AST-only tests should be included because they're direct matches (high confidence)
            # Even if weighted score is low due to no semantic component
            is_ast_only = has_ast and not has_semantic
            
            if passes_threshold or has_llm_score or has_semantic or is_ast_only:
                # Set explicit flags based on match_details and original sources
                test['is_ast_match'] = has_ast
                test['is_semantic_match'] = has_semantic
                filtered_tests.append(test)
        
        logger.info(f"Applied minimum threshold filter: {len(combined_results.get('tests', []))} -> {len(filtered_tests)} tests")
        
        # Log details about filtered tests for debugging
        if llm_scores_map:
            llm_filtered = [t for t in filtered_tests if t.get('test_id') in llm_scores_map]
            logger.info(f"Tests with LLM scores in filtered results: {len(llm_filtered)} out of {len(llm_scores_map)} assessed")
            if len(llm_filtered) < len(llm_scores_map):
                missing_llm_tests = set(llm_scores_map.keys()) - {t.get('test_id') for t in filtered_tests}
                logger.warning(f"LLM-assessed tests missing from filtered results: {len(missing_llm_tests)} tests")
                if missing_llm_tests:
                    logger.warning(f"Missing test IDs (first 5): {list(missing_llm_tests)[:5]}")
                    # Log why they were filtered out
                    for missing_id in list(missing_llm_tests)[:3]:
                        # Try to find the test in combined_results before filtering
                        missing_test = next((t for t in combined_results.get('tests', []) if t.get('test_id') == missing_id), None)
                        if missing_test:
                            logger.warning(f"  Test {missing_id}: confidence_score={missing_test.get('confidence_score', 0)}, has_ast={missing_test.get('is_ast_match', False)}, has_semantic={missing_test.get('is_semantic_match', False)}")
        
        combined_results['tests'] = filtered_tests
        combined_results['total_tests'] = len(filtered_tests)
        
        # Format results for API response
        all_tests = []
        seen_test_ids = set()
        
        # Add tests from combined results (already sorted by confidence score)
        for test in combined_results.get('tests', []):
            test_id = test.get('test_id')
            if test_id and test_id not in seen_test_ids:
                seen_test_ids.add(test_id)
                
                # Extract matched classes from match_details
                match_details = combined_results.get('match_details', {})
                test_matches = match_details.get(test_id, [])
                matched_classes = []
                similarity = None
                for match in test_matches:
                    if match.get('type') == 'exact':
                        matched_classes.append(match.get('class', ''))
                    elif match.get('type') == 'function_level':
                        matched_classes.append(f"{match.get('module', '')}.{match.get('function', '')}")
                    elif match.get('type') == 'semantic':
                        # Extract similarity for semantic matches
                        similarity = match.get('similarity', test.get('similarity'))
                
                # Determine match_type from flags and match_details
                is_ast = test.get('is_ast_match', False)
                is_semantic = test.get('is_semantic_match', False)
                
                # Determine match_type based on flags
                if is_ast and is_semantic:
                    match_type = 'Both'
                elif is_ast:
                    match_type = 'AST'
                elif is_semantic:
                    match_type = 'Semantic'
                else:
                    # Fallback: try to determine from match_details
                    has_ast_in_details = any(m.get('type') in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'direct_test_file', 'module_pattern', 'integration'] 
                                           for m in test_matches)
                    has_semantic_in_details = any(m.get('type') == 'semantic' for m in test_matches)
                    if has_ast_in_details and has_semantic_in_details:
                        match_type = 'Both'
                    elif has_ast_in_details:
                        match_type = 'AST'
                    elif has_semantic_in_details:
                        match_type = 'Semantic'
                    else:
                        match_type = test.get('match_type', 'unknown')
                
                test_dict = {
                    'test_id': test_id,
                    'class_name': test.get('class_name'),
                    'method_name': test.get('method_name'),
                    'test_file_path': test.get('test_file_path') or test.get('file_path', ''),
                    'test_type': test.get('test_type'),
                    'confidence': 'high' if test.get('confidence_score', 0) >= 70 else 'medium' if test.get('confidence_score', 0) >= 50 else 'low',
                    'confidence_score': test.get('confidence_score', 0),
                    'match_type': match_type,  # Use determined match_type
                    'matched_classes': matched_classes,
                    'similarity': similarity,  # Add similarity for semantic matches
                    'is_ast_match': is_ast,  # Preserve AST flag
                    'is_semantic_match': is_semantic,  # Preserve semantic flag
                }
                
                # Add confidence breakdown if available
                if test.get('confidence_breakdown'):
                    test_dict['confidence_breakdown'] = test.get('confidence_breakdown')
                
                # Add LLM scores if available
                if test.get('llm_score') is not None:
                    test_dict['llm_score'] = test.get('llm_score')
                    test_dict['llm_explanation'] = test.get('llm_explanation', '')
                
                all_tests.append(test_dict)
        
        # Build diagnostic information
        diagnostics = {
            'parsed_files': len(parsed_diff.get('changed_files', [])),
            'parsed_classes': len(parsed_diff.get('changed_classes', [])),
            'parsed_methods': len(parsed_diff.get('changed_methods', [])),
            'search_exact_matches': len(search_queries.get('exact_matches', [])),
            'search_module_matches': len(search_queries.get('module_matches', [])),
            'search_function_changes': len(search_queries.get('changed_functions', [])),
            'search_test_candidates': len(search_queries.get('test_file_candidates', [])),
        }
        
        # Check database status
        try:
            with conn.cursor() as cursor:
                # Use target_schema if available, otherwise DB_SCHEMA
                target_schema = schema_name or DB_SCHEMA
                cursor.execute(f"SELECT COUNT(*) FROM {target_schema}.reverse_index")
                diagnostics['db_reverse_index_count'] = cursor.fetchone()[0]
                cursor.execute(f"SELECT COUNT(*) FROM {target_schema}.test_registry")
                diagnostics['db_test_registry_count'] = cursor.fetchone()[0]
                cursor.execute(f"SELECT COUNT(*) FROM {target_schema}.test_function_mapping")
                diagnostics['db_function_mapping_count'] = cursor.fetchone()[0]
        except Exception as e:
            logger.warning(f"Could not get database diagnostics: {e}")
        
        # Group tests by test suite (optional, for UI organization)
        def group_by_test_suite(tests: List[Dict]) -> Dict[str, List[Dict]]:
            """Group tests by test suite based on file path directory structure."""
            grouped = {}
            for test in tests:
                file_path = test.get('test_file_path', '')
                if file_path:
                    # Extract suite from directory path (e.g., "tests/unit" -> "unit")
                    parts = file_path.replace('\\', '/').split('/')
                    # Find common test directory patterns
                    suite_name = 'other'
                    for i, part in enumerate(parts):
                        if part in ['test', 'tests'] and i + 1 < len(parts):
                            suite_name = parts[i + 1] if parts[i + 1] else 'root'
                            break
                        elif part in ['unit', 'integration', 'e2e', 'functional']:
                            suite_name = part
                            break
                    if suite_name not in grouped:
                        grouped[suite_name] = []
                    grouped[suite_name].append(test)
                else:
                    if 'other' not in grouped:
                        grouped['other'] = []
                    grouped['other'].append(test)
            return grouped
        
        test_suites = group_by_test_suite(all_tests)
        
        # Calculate confidence distribution
        confidence_distribution = {'high': 0, 'medium': 0, 'low': 0}
        for test in all_tests:
            score = test.get('confidence_score', 0)
            if score >= 70:
                confidence_distribution['high'] += 1
            elif score >= 50:
                confidence_distribution['medium'] += 1
            else:
                confidence_distribution['low'] += 1
        
        # Extract LLM scores for response
        llm_scores_list = []
        for test in all_tests:
            if test.get('llm_score') is not None:
                llm_scores_list.append({
                    'test_id': test.get('test_id'),
                    'llm_score': test.get('llm_score'),
                    'llm_explanation': test.get('llm_explanation', '')
                })
        
        return {
            'total_tests': len(all_tests),
            'ast_matches': ast_count_snapshot,  # Saved before semantic merge mutated combined_results
            'semantic_matches': semantic_results.get('total_tests', 0),
            'tests': all_tests,
            'semantic_results': semantic_results,  # Include semantic results for enhancement
            'match_details': combined_results.get('match_details', {}),  # Include match_details for better match type detection
            'llm_scores': llm_scores_list if llm_scores_list else None,  # LLM scores if available
            'llm_input_output': combined_results.get('llm_input_output'),  # LLM input prompt and output
            'confidence_distribution': confidence_distribution,  # Confidence score distribution
            'test_suites': test_suites,  # Tests grouped by suite (optional, for UI organization)
            'parsed_diff': {
                'changed_files': parsed_diff.get('changed_files', []),
                'changed_classes': parsed_diff.get('changed_classes', []),
                'changed_methods': parsed_diff.get('changed_methods', [])[:20],  # Limit for response
            },
            'search_queries': {
                'exact_matches': search_queries.get('exact_matches', [])[:10],  # Limit for response
                'module_matches': search_queries.get('module_matches', [])[:10],
                'changed_functions': [f"{f.get('module', '')}.{f.get('function', '')}" for f in search_queries.get('changed_functions', [])[:10]],
            },
            'diagnostics': diagnostics
        }
