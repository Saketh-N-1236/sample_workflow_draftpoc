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

from deterministic.db_connection import get_connection, DB_SCHEMA

from deterministic.parsing.diff_parser import parse_git_diff, build_search_queries

from git_diff_processor.selection_engine import (
    find_affected_tests,
    find_tests_ast_only,
    find_tests_semantic_only,
)


def _resolve_schema_list(
    schema_name: Optional[str],
    schema_names: Optional[List[str]],
) -> List[str]:
    """Ordered list of DB schema qualifiers for test analysis tables."""
    if schema_names:
        out = [s.strip() for s in schema_names if s and str(s).strip()]
        if out:
            return out
    if schema_name and str(schema_name).strip():
        return [schema_name.strip()]
    return [DB_SCHEMA]


def _merge_ast_results(
    base: Optional[Dict[str, Any]],
    part: Dict[str, Any],
    sch: str,
) -> Dict[str, Any]:
    """Merge find_tests_ast_only output across schemas (dedupe by test_id, merge match_details)."""
    if not part.get("tests"):
        if base is None:
            return {"tests": [], "match_details": {}, "total_tests": 0}
        return base

    if base is None:
        tests_by_id: Dict[str, Dict[str, Any]] = {}
        md: Dict[str, List[Any]] = {}
        for t in part["tests"]:
            tid = t.get("test_id")
            if not tid:
                continue
            nt = dict(t)
            nt["source_schema"] = sch
            tests_by_id[tid] = nt
            md[tid] = list(part.get("match_details", {}).get(tid, []))
        return {
            "tests": list(tests_by_id.values()),
            "match_details": md,
            "total_tests": len(tests_by_id),
        }

    tests_by_id = {t["test_id"]: dict(t) for t in base["tests"] if t.get("test_id")}
    md = {k: list(v) for k, v in (base.get("match_details") or {}).items()}
    for t in part.get("tests", []):
        tid = t.get("test_id")
        if not tid:
            continue
        new_md = part.get("match_details", {}).get(tid, [])
        if tid not in tests_by_id:
            nt = dict(t)
            nt["source_schema"] = sch
            tests_by_id[tid] = nt
            md[tid] = list(new_md)
        else:
            md.setdefault(tid, []).extend(new_md)
    sorted_tests = sorted(
        tests_by_id.values(),
        key=lambda x: x.get("confidence_score", 0),
        reverse=True,
    )
    return {
        "tests": sorted_tests,
        "match_details": md,
        "total_tests": len(tests_by_id),
    }


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
      1. AST found 0 tests + specific symbols → moderate 0.40 (semantic fills DB gap)
         AST found 0 tests, no symbols        → strict 0.50 (avoid vocabulary noise)
      2. Function-level changes   → moderate (AST is strong, semantic supplements)
      3. Specific symbol changes  → moderate-lenient (symbol lookup precise, but
                                    semantic catches description-level matches too)
      4. Module-only changes      → lenient (broad AST match, semantic refines)
      5. Complex diff (>3 files)  → add extra query variations

    User-stored values are always respected UNLESS they exceed 0.45
    (values > 0.45 cause false negatives and are silently clamped).
    """
    import logging
    _logger = logging.getLogger(__name__)

    config = dict(base_config or {})

    ast_count = ast_results.get('total_tests', 0)
    has_functions  = bool(search_queries.get('changed_functions'))
    has_exact      = bool(search_queries.get('exact_matches'))   # specific symbols
    has_module     = bool(search_queries.get('module_matches'))

    # ── Determine adaptive defaults ───────────────────────────────────────────────
    # Thresholds raised from 0.4 → 0.45 baseline: vocabulary overlap (e.g. regex literals
    # in a diff causing regex-constant tests to score 35–44%) is cut by the higher floor.
    if ast_count == 0:
        adaptive_variations = 5
        if has_exact:
            # Specific named symbols in the query (e.g. paymentReducer, checkWhiteSpace).
            # The DB has no linkage for this file, so semantic is the only path.
            # Use a moderate threshold (0.40) so tests sharing the named symbol
            # score high enough to surface — e.g. "updateUserCards dispatched into
            # paymentReducer" shares paymentReducer with the diff but not the new
            # RESETPAYMENT action specifically.  The strict 0.50 fallback was
            # causing a dead zone for this common "new action added" scenario.
            config.setdefault('similarity_threshold', 0.40)
            reason = "AST 0 + exact symbols present — semantic moderate threshold (0.40)"
        else:
            # Only module/pattern queries — stay strict to avoid vocabulary noise.
            config.setdefault('similarity_threshold', 0.50)
            reason = "AST 0, no exact symbols — semantic strict threshold (0.50)"
    elif has_functions:
        adaptive_variations = 3
        config.setdefault('similarity_threshold', 0.45)
        reason = "function-level changes — AST strong, semantic supplements (0.45)"
    elif has_exact:
        adaptive_variations = 3
        config.setdefault('similarity_threshold', 0.45)
        reason = "specific symbol changes (0.45)"
    elif has_module:
        adaptive_variations = 4
        config.setdefault('similarity_threshold', 0.45)
        reason = "module-only changes — lenient for broad coverage (0.45)"
    else:
        adaptive_variations = 4
        config.setdefault('similarity_threshold', 0.45)
        reason = "no structured matches — semantic fallback (0.45)"

    if num_changed_files > 3:
        adaptive_variations = min(adaptive_variations + 1, 6)

    if config.get('num_query_variations') is None:
        config['num_query_variations'] = adaptive_variations

    _logger.info(
        f"Adaptive semantic config | variations={config['num_query_variations']} | reason={reason}"
    )
    return config


async def process_diff_and_select_tests(
    diff_content: str,
    project_root: Optional[Path] = None,
    use_semantic: bool = True,
    test_repo_path: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_names: Optional[List[str]] = None,
    test_repo_id: Optional[str] = None,
    file_list: Optional[List[str]] = None,
    semantic_config: Optional[Dict] = None,
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
        schema_names: If set, AST/dead-zone/cochange run on every listed schema and merge
        test_repo_id: Vector namespace for semantic search (preferred over process env)

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
    
    from parsers.registry import initialize_registry, get_registry
    from config.config_loader import load_language_configs

    config_path_yaml = project_root / "config" / "language_configs.yaml"
    if config_path_yaml.exists():
        initialize_registry(config_path_yaml)
        config = load_language_configs(config_path_yaml)
    else:
        initialize_registry()
        config = {}

    parser_registry = get_registry()
    
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
    
    logger.info(
        f"[DIFF] {len(parsed_diff.get('changed_files', []))} changed file(s) - "
        f"exact: {len(search_queries.get('exact_matches', []))}, "
        f"module: {len(search_queries.get('module_matches', []))}, "
        f"functions: {len(search_queries.get('changed_functions', []))}"
    )
    
    schemas_resolved = _resolve_schema_list(schema_name, schema_names)
    target_schema = schemas_resolved[0]

    with get_connection() as conn:
        _dz_result: Dict[str, Any] = {}
        # Debug: Verify schema(s) have data (qualified table names — no search_path required)
        with conn.cursor() as cursor:
            for _sch in schemas_resolved:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {_sch}.test_registry")
                    test_count = cursor.fetchone()[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {_sch}.reverse_index")
                    reverse_count = cursor.fetchone()[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {_sch}.test_function_mapping")
                    func_count = cursor.fetchone()[0]
                    logger.info(
                        f"[{_sch}] Database stats - Tests: {test_count}, "
                        f"Reverse index: {reverse_count}, Function mappings: {func_count}"
                    )
                except Exception as e:
                    logger.warning(f"[{_sch}] Could not query database stats: {e}")

        # AST-based matching across all bound schemas, merged
        logger.info(
            f"[AST] Running AST-based test selection on schema(s): {schemas_resolved}"
        )
        ast_results: Optional[Dict[str, Any]] = None
        for _sch in schemas_resolved:
            partial = find_tests_ast_only(
                conn,
                search_queries,
                parsed_diff.get("file_changes", []),
                schema=_sch,
            )
            ast_results = _merge_ast_results(ast_results, partial, _sch)
        assert ast_results is not None
        logger.info(f"[AST] Found {ast_results.get('total_tests', 0)} test(s) (merged)")
        if ast_results.get("total_tests", 0) == 0:
            logger.warning(f"[AST] No matches in any of {schemas_resolved}")

        # ── Dead zone diagnostics (informational; does not skip semantic) ─────────────
        # AST and semantic both run when use_semantic=True. Flag warns when DB has no
        # linkage for changed files — semantic-only suggestions need extra review.
        try:
            from git_diff_processor.diff_scenario_analysis import (
                check_dead_zone_for_files,
                check_dead_zone_for_files_multi,
            )

            if len(schemas_resolved) == 1:
                _dz_result = check_dead_zone_for_files(
                    conn,
                    schemas_resolved[0],
                    parsed_diff.get("changed_files", []),
                    search_queries,
                )
            else:
                _dz_result = check_dead_zone_for_files_multi(
                    conn,
                    schemas_resolved,
                    parsed_diff.get("changed_files", []),
                    search_queries,
                )
            if _dz_result.get("is_complete_dead_zone"):
                logger.warning(
                    "[DEAD_ZONE] Complete dead zone (no DB file coverage) — "
                    "semantic pipeline still runs. Review semantic-only hits. Files: %s",
                    [d["file"] for d in _dz_result.get("dead_files", [])],
                )
        except Exception as _dz_err:
            logger.debug("[DEAD_ZONE] check failed (non-fatal): %s", _dz_err)
        # ─────────────────────────────────────────────────────────────────────────────

        # ── Build adaptive semantic config AFTER AST results are known ──────────
        # This makes quality_threshold/num_variations dynamic — no test-category
        # naming convention required.  Works for any test repository structure.
        semantic_config = build_adaptive_semantic_config(
            search_queries=search_queries,
            ast_results=ast_results,
            base_config=semantic_config,
            num_changed_files=len(parsed_diff.get('changed_files', [])),
        )
        # Optional: lower vector threshold to experiment (FP ↑, FN ↓)
        #   SEMANTIC_VECTOR_THRESHOLD=0.22
        # Presets if env number not set: lenient | moderate | strict
        import os as _os_sem
        from semantic.config import DEFAULT_SIMILARITY_THRESHOLD as _DEF_VEC_TH

        _th_src = "adaptive_or_default"
        _env_th = _os_sem.getenv("SEMANTIC_VECTOR_THRESHOLD", "").strip()
        if _env_th:
            try:
                _v = float(_env_th)
                semantic_config["similarity_threshold"] = max(0.05, min(0.92, _v))
                _th_src = f"SEMANTIC_VECTOR_THRESHOLD={semantic_config['similarity_threshold']}"
                logger.info("[SEMANTIC] %s", _th_src)
            except ValueError:
                logger.warning(
                    "[SEMANTIC] Ignoring invalid SEMANTIC_VECTOR_THRESHOLD=%r", _env_th
                )
        else:
            _preset = _os_sem.getenv("SEMANTIC_VECTOR_THRESHOLD_PRESET", "").strip().lower()
            if _preset == "lenient":
                semantic_config["similarity_threshold"] = 0.22
                _th_src = "preset:lenient (0.22)"
            elif _preset == "moderate":
                semantic_config["similarity_threshold"] = 0.32
                _th_src = "preset:moderate (0.32)"
            elif _preset == "strict":
                semantic_config["similarity_threshold"] = 0.5
                _th_src = "preset:strict (0.50)"
            if _preset in ("lenient", "moderate", "strict"):
                logger.info("[SEMANTIC] Vector threshold %s", _th_src)

        vector_threshold_applied = float(
            semantic_config.get("similarity_threshold") or _DEF_VEC_TH
        )
        semantic_config["_vector_threshold_effective"] = vector_threshold_applied
        semantic_config["_vector_threshold_source_note"] = _th_src
        # ────────────────────────────────────────────────────────────────────────

        # Get semantic results if enabled
        semantic_results = {'total_tests': 0, 'tests': []}
        if use_semantic:
            try:
                logger.info("[SEMANTIC] Running semantic search...")
                # Use async version since we're in an async context
                from git_diff_processor.selection_engine import find_tests_semantic_only_async
                # Request-scoped id preferred; env TEST_REPO_ID only for CLI/scripts.
                import os

                _resolved_tr = (test_repo_id or "").strip() or None
                if not _resolved_tr:
                    _resolved_tr = (os.getenv("TEST_REPO_ID") or "").strip() or None
                if _resolved_tr:
                    logger.debug("[SEMANTIC] test_repo_id=%s…", _resolved_tr[:16])
                else:
                    logger.debug(
                        "[SEMANTIC] test_repo_id unset — vector filter may span repos"
                    )
                semantic_results = await find_tests_semantic_only_async(
                    conn,
                    search_queries,
                    parsed_diff.get("file_changes", []),
                    schema=target_schema,
                    test_repo_id=_resolved_tr,
                    semantic_config=semantic_config,
                    diff_content=diff_content,
                )
                logger.info(f"[SEMANTIC] Found {semantic_results.get('total_tests', 0)} test(s)")
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
        logger.info(f"[MERGE] AST base: {ast_count_snapshot} test(s)")

        # IMPORTANT: Preserve AST match information from match_details BEFORE any filtering
        # Store which tests came from AST (from match_details) so we can mark them correctly later
        ast_test_ids_from_match_details = set()
        combined_match_details = combined_results.get('match_details', {})
        for test_id, matches in combined_match_details.items():
            # Check if this test has any AST match types (not semantic)
            has_ast_match = any(
                m.get('type') in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'direct_test_file', 'module_pattern', 'integration', 'cochanged_test_suite']
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
        original_semantic_test_ids = set()
        if semantic_results.get('tests'):
            logger.info(f"[MERGE] Adding {len(semantic_results.get('tests', []))} semantic result(s) to combined set")
            semantic_tests_dict = {t.get('test_id'): t for t in semantic_results.get('tests', [])}
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

        # ── Semantic co-location expansion ────────────────────────────────────
        # When semantic search finds tests in a file with high confidence
        # (similarity >= 0.50), also include ALL other tests in that file.
        # Rationale: if any test in a file is strongly confirmed by the vector
        # search, the whole file likely covers the changed production code —
        # sibling tests (e.g. isUserLoggedIn co-located with capitalizeFirstLetter
        # tests) are relevant even if their individual descriptions don't surface
        # through vector search.
        #
        # Guard: only expand from hits with similarity >= 0.50 to avoid pulling
        # in siblings from borderline false-positive matches.
        _SEM_COLOC_MIN_SIM = 0.50
        _sem_confirmed_file_paths: set = set()
        for _sem_t in semantic_results.get('tests', []):
            if (_sem_t.get('similarity') or 0) >= _SEM_COLOC_MIN_SIM:
                _fp = _sem_t.get('test_file_path') or _sem_t.get('file_path', '')
                if _fp:
                    _sem_confirmed_file_paths.add(_fp)

        # Build a lowercase set of "relevant" class-name tokens from the diff.
        # Co-located tests whose describe label (class_name) has NO token overlap
        # with this set are skipped — they test a different domain in the same
        # cross-test file (e.g. 'profileReducer' in payment-state.cross.test.js
        # when the diff only changes paymentReducer/paymentActions).
        _diff_class_tokens: set = set()
        for _ec in search_queries.get('exact_matches', []):
            _diff_class_tokens.update(_ec.lower().split('.'))
        for _fc in parsed_diff.get('changed_classes', []):
            if _fc:
                _diff_class_tokens.add(_fc.lower())
        for _mf in parsed_diff.get('changed_methods', []):
            if _mf:
                _diff_class_tokens.add(_mf.lower())
        # Also add the file stem(s) of changed production files.
        for _chf in parsed_diff.get('changed_files', []):
            from pathlib import Path as _PPath
            _diff_class_tokens.add(_PPath(_chf).stem.lower())

        def _coloc_class_is_relevant(class_name: Optional[str]) -> bool:
            """True if the test's describe label shares at least one token with the diff."""
            if not class_name:
                return True  # unknown describe → keep (benefit of the doubt)
            _cn_lower = class_name.lower()
            # Direct substring match against any diff token
            return any(tok and tok in _cn_lower for tok in _diff_class_tokens)

        if _sem_confirmed_file_paths:
            _coloc_added = 0
            _coloc_skipped = 0
            for _sch in schemas_resolved:
                with conn.cursor() as _cursor:
                    for _fpath in _sem_confirmed_file_paths:
                        try:
                            _cursor.execute(f"""
                                SELECT DISTINCT test_id, class_name, method_name, file_path, test_type
                                FROM {_sch}.test_registry
                                WHERE file_path = %s
                                ORDER BY test_id
                            """, (_fpath,))
                            for _row in _cursor.fetchall():
                                _tid = _row[0]
                                _cls = _row[1]
                                # Skip co-located tests whose describe label has no
                                # overlap with the diff's changed classes/symbols.
                                if _tid not in original_semantic_test_ids:
                                    if not _coloc_class_is_relevant(_cls):
                                        _coloc_skipped += 1
                                        logger.debug(
                                            "[SEM-COLOC] Skipped unrelated co-located test "
                                            "%s (class=%s) — no token overlap with diff",
                                            _tid, _cls,
                                        )
                                        continue
                                if _tid not in combined_tests_dict:
                                    combined_tests_dict[_tid] = {
                                        'test_id': _tid,
                                        'class_name': _cls,
                                        'method_name': _row[2],
                                        'test_file_path': _row[3],
                                        'test_type': _row[4],
                                        'match_type': 'colocated_from_semantic',
                                    }
                                    combined_match_details[_tid] = []
                                    _coloc_added += 1
                                # Only annotate tests not already directly found by semantic
                                if _tid not in original_semantic_test_ids:
                                    _already = any(
                                        m.get('match_strategy') == 'semantic_colocated_file'
                                        for m in combined_match_details.get(_tid, [])
                                    )
                                    if not _already:
                                        combined_match_details.setdefault(_tid, []).append({
                                            'type': 'direct_file',
                                            'test_file': _fpath,
                                            'match_strategy': 'semantic_colocated_file',
                                            'confidence': 'medium',
                                        })
                        except Exception as _e:
                            logger.debug(f"[SEM-COLOC] file lookup error ({_sch}): {_e}")
            if _coloc_skipped:
                logger.info(
                    "[SEM-COLOC] Skipped %s co-located test(s) — describe label has no diff-token overlap",
                    _coloc_skipped,
                )

            if _coloc_added:
                combined_results['tests'] = list(combined_tests_dict.values())
                combined_results['match_details'] = combined_match_details
                combined_results['total_tests'] = len(combined_tests_dict)
                logger.info(
                    "[SEM-COLOC] Added %s co-located test(s) from %s semantically-confirmed file(s)",
                    _coloc_added,
                    len(_sem_confirmed_file_paths),
                )
        # ──────────────────────────────────────────────────────────────────────

        # Prod + test file in same diff → keep only tests in modified test file(s)
        # (stops semantic false positives e.g. ApiConstants change + co-updated suite)
        cochange_meta = None
        try:
            from git_diff_processor.cochange_tight_suite import apply_tight_cochanged_suite

            combined_results, cochange_meta = apply_tight_cochanged_suite(
                conn,
                target_schema,
                parsed_diff.get("changed_files", []),
                combined_results,
                schemas=schemas_resolved if len(schemas_resolved) > 1 else None,
            )
            if cochange_meta:
                combined_results["cochange_selection"] = cochange_meta
                combined_tests_dict = {t.get("test_id"): t for t in combined_results["tests"]}
                combined_match_details = combined_results.get("match_details", {})
        except Exception as _co_err:
            logger.warning(f"[COCHANGE] Tight suite step skipped: {_co_err}")

        # LLM Reasoning Step (optional) - AFTER merging semantic results
        # This ensures LLM can assess all candidates (AST + semantic)
        llm_scores_map = {}
        try:
            # Check if LLM reasoning is enabled (can be configured via environment or parameter)
            import os
            use_llm_reasoning = os.getenv('USE_LLM_REASONING', 'true').lower() == 'true'
            
            if use_llm_reasoning:
                logger.info("[LLM] Running LLM reasoning on top candidates...")
                # Import LLM reasoning service
                # backend/git_diff_processor/ -> parent = backend/
                _backend = Path(__file__).parent.parent
                if str(_backend) not in sys.path:
                    sys.path.insert(0, str(_backend))
                
                try:
                    from services.llm_reasoning_service import LLMReasoningService
                    llm_service = LLMReasoningService()
                except ImportError as e:
                    logger.warning(f"Failed to import LLM reasoning service: {e}. LLM reasoning will be skipped.")
                    llm_service = None
                
                if llm_service:
                    _llm_top = 40
                    try:
                        _llm_top = int(os.getenv("LLM_ASSESS_TOP_N", "40"))
                    except ValueError:
                        logger.warning(
                            "Ignoring invalid LLM_ASSESS_TOP_N; using default 40"
                        )
                    _llm_top = max(20, min(80, _llm_top))
                    # Widen pool vs legacy 20 so borderline AST hits below the fold get scored
                    top_candidates = sorted(
                        combined_results.get("tests", []),
                        key=lambda t: t.get("confidence_score", 0),
                        reverse=True,
                    )[:_llm_top]
                    
                    if top_candidates:
                        # Prepare test candidates with match reasons
                        test_candidates = []
                        match_details_dict = combined_results.get('match_details', {})
                        def _match_reason_hint(m: Dict) -> str:
                            """Compact hint for LLM: type + key fields (semantic gets similarity)."""
                            mt = m.get("type", "") or "unknown"
                            if mt == "semantic":
                                sim = m.get("similarity")
                                if sim is not None:
                                    return f"semantic(sim={float(sim):.3f})"
                                return "semantic"
                            for key in (
                                "symbol",
                                "reference",
                                "module",
                                "file",
                                "file_path",
                                "pattern",
                            ):
                                v = m.get(key)
                                if v:
                                    return f"{mt}({key}={v})"
                            return mt

                        for test in top_candidates:
                            test_id = test.get('test_id')
                            match_reasons = []
                            if test_id in match_details_dict:
                                for match in match_details_dict[test_id][:6]:
                                    match_reasons.append(_match_reason_hint(match))
                            
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
                            top_n=_llm_top,
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
                        
                        logger.info(f"[LLM] Assessed {len(llm_scores_map)} test(s)")
                    else:
                        logger.info("[LLM] No candidates to assess")
                else:
                    logger.info("[LLM] Service not available, skipping")
            else:
                logger.info("[LLM] Reasoning disabled via USE_LLM_REASONING=false")
        except Exception as e:
            logger.warning(f"LLM reasoning failed: {e}. Continuing without LLM scores.", exc_info=True)
            llm_scores_map = {}
        
        # Recalculate confidence scores with LLM component and get breakdown
        if llm_scores_map:
            logger.info("[SCORE] Recalculating confidence scores with LLM component")
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
            # No LLM scores — recalculate composite score for all tests using the
            # weighted formula (50% AST + 35% Vector + 10% LLM + 5% Speed).
            # IMPORTANT: previously the score returned by calculate_confidence_score_with_breakdown
            # was discarded ("_") and only the breakdown dict was stored.  That left
            # confidence_score as int(similarity * 60) from rag_pipeline.py (line 131),
            # which at 41–43% similarity equals 24–26 — slightly below or near 40.
            # Storing the proper composite score ensures the filter works correctly.
            from git_diff_processor.git_diff_processor import calculate_confidence_score_with_breakdown
            for test in combined_results.get('tests', []):
                test_id = test.get('test_id')
                matches = combined_results.get('match_details', {}).get(test_id, [])
                test_type = test.get('test_type')
                new_score, breakdown = calculate_confidence_score_with_breakdown(
                    matches,
                    test_type,
                    llm_score=None
                )
                test['confidence_score'] = new_score   # ← actually persist the score
                test['confidence_breakdown'] = breakdown
        
        # Store LLM input/output in results if available
        try:
            if 'llm_input_output' in locals():
                combined_results['llm_input_output'] = llm_input_output
        except:
            pass
        
        # Confidence filter (default: on — composite gate MIN_CONFIDENCE_THRESHOLD, default 42%).
        # Set SELECTION_APPLY_CONFIDENCE_FILTER=false to disable and return full merged set.
        import os as _os_filt
        _conf_env = _os_filt.getenv("SELECTION_APPLY_CONFIDENCE_FILTER", "true").strip().lower()
        _apply_conf_filter = _conf_env not in ("0", "false", "no", "off")
        # 42% drops exact-match barrel imports that sit at ~40.5% composite
        # (AST=80 × 50% + speed) while keeping direct_file–floored tests at 45%.
        MIN_CONFIDENCE_THRESHOLD = 0.42
        filtered_tests: List[Dict[str, Any]] = []
        if not _apply_conf_filter:
            for test in combined_results.get("tests", []):
                test_id = test.get("test_id")
                if not test_id:
                    continue
                has_semantic = (
                    test_id in original_semantic_test_ids
                    or any(
                        m.get("type") == "semantic"
                        for m in combined_match_details.get(test_id, [])
                    )
                )
                has_ast = (
                    test_id in ast_test_ids_from_match_details
                    or test_id in original_ast_test_ids
                    or any(
                        m.get("type")
                        in [
                            "exact",
                            "module",
                            "function_level",
                            "direct_file",
                            "direct_file_match",
                            "direct_test_file",
                            "module_pattern",
                            "integration",
                            "cochanged_test_suite",
                        ]
                        for m in combined_match_details.get(test_id, [])
                    )
                )
                test["is_ast_match"] = has_ast
                test["is_semantic_match"] = has_semantic
                filtered_tests.append(test)
            logger.info(
                "[FILTER] Confidence filter disabled (SELECTION_APPLY_CONFIDENCE_FILTER=false); "
                "returning %s merged candidate(s) unfiltered",
                len(filtered_tests),
            )
        for test in combined_results.get('tests', []) if _apply_conf_filter else []:
            test_id = test.get('test_id')
            confidence_score = test.get('confidence_score', 0)
            
            # LLM score checks — two thresholds:
            #
            # has_llm_score        (score > 0)    : LLM evaluated and gave any positive
            #                                       verdict.  Used as a pass bypass for
            #                                       Both-match tests where the composite
            #                                       needs a small LLM nudge.
            #
            # has_strong_llm_score (score > 0.30) : LLM gave a MEANINGFUL positive verdict.
            #                                       Required for SEMANTIC-ONLY tests.
            #                                       Reason: semantic-only tests at 55-60%
            #                                       similarity that share only vocabulary
            #                                       (e.g. "reducer", "state") can get a
            #                                       tiny LLM score (0.05-0.15) that pushes
            #                                       the composite above the gate.  A 0.30
            #                                       floor (≈ "weak but meaningful") weeds
            #                                       out profileReducer/userDetailsReducer
            #                                       false positives without affecting tests
            #                                       the LLM genuinely confirms (0.6-0.9).
            _llm_score_val = test.get('llm_score')
            _llm_score_in_map = llm_scores_map.get(test_id, {}).get('llm_score', 0) if test_id in llm_scores_map else 0
            _effective_llm = max(
                _llm_score_val if _llm_score_val is not None else 0,
                _llm_score_in_map,
            )
            has_llm_score = _effective_llm > 0
            has_strong_llm_score = _effective_llm > 0.30
            
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
                any(m.get('type') in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'direct_test_file', 'module_pattern', 'integration', 'cochanged_test_suite'] 
                    for m in combined_match_details.get(test_id, []))
            )
            
            # ── Pass conditions ────────────────────────────────────────────────
            # A test is kept when ANY of these is True:
            #
            # 1. passes_threshold     composite score >= MIN_CONFIDENCE_THRESHOLD (42 %)
            #                         Drops barrel exact-matches at ~40.5 %.
            #
            # 2. is_ast_any           AST-matched (DB-confirmed) with adaptive floor:
            #
            #    • 30 % floor when the test ALSO has semantic confirmation (Both).
            #      Lower floor keeps legitimate AST+semantic "Both" siblings (e.g.
            #      checkArray/getProgressWidth) that sit at 33-37 % because the
            #      composite weights-down a high-similarity semantic signal.
            #
            #    • MIN_CONFIDENCE_THRESHOLD when AST-ONLY, no semantic, weak LLM.
            #
            #    • AST-only but strong LLM — lenient 30 % floor.
            #
            # 3. llm_bypass
            #    • Semantic-only: strong LLM (> 0.30).
            #    • AST-only:      strong LLM only — tiny scores must not rescue
            #      borderline barrel matches that fail passes_threshold.
            #    • Both:          any positive LLM (edge cases).
            passes_threshold = (confidence_score / 100.0) >= MIN_CONFIDENCE_THRESHOLD

            _composite_ratio = confidence_score / 100.0
            if has_ast and has_semantic:
                # "Both" — use lenient 30 % floor (semantic already vouches for it).
                is_ast_any = _composite_ratio >= 0.30
            elif has_ast and not has_semantic and not has_strong_llm_score:
                is_ast_any = _composite_ratio >= MIN_CONFIDENCE_THRESHOLD
            else:
                # AST-only but LLM confirmed (> 0.30) — trust the LLM; use 30 %.
                is_ast_any = has_ast and _composite_ratio >= 0.30

            if has_semantic and not has_ast:
                llm_bypass = has_strong_llm_score
            elif has_ast and not has_semantic:
                llm_bypass = has_strong_llm_score
            else:
                llm_bypass = has_llm_score

            # ── Co-location-only gate ─────────────────────────────────────────
            # Two co-location strategies exist:
            #   • 'colocated_in_same_file'  — AST-driven (Strategy 4a): test
            #     included because it shares a file with an AST-exact match.
            #     This is the WEAKEST signal and causes false positives when the
            #     anchor test itself was over-broad (e.g. module-level match).
            #   • 'semantic_colocated_file' — Semantic-driven (expansion above):
            #     test included because it shares a file with a STRONG semantic
            #     hit (similarity >= 0.50).  This is intentionally kept — if any
            #     test in a file was confirmed with high confidence the siblings
            #     are almost certainly relevant (same test suite, same imports).
            #
            # Rule: drop only if EVERY non-semantic match is 'colocated_in_same_file'
            # (pure AST co-location with no other evidence) AND the test has no
            # semantic match of its own.
            # Tests that carry a 'semantic_colocated_file' annotation are kept —
            # they were added because a sibling had >= 50 % semantic similarity.
            _ast_only_matches = [
                m for m in combined_match_details.get(test_id, [])
                if m.get('type') != 'semantic'
            ]
            _is_ast_coloc_only = (
                len(_ast_only_matches) > 0 and
                all(
                    m.get('match_strategy') == 'colocated_in_same_file'
                    for m in _ast_only_matches
                )
            )
            _has_sem_coloc = any(
                m.get('match_strategy') == 'semantic_colocated_file'
                for m in _ast_only_matches
            )
            if _is_ast_coloc_only and not has_semantic and not _has_sem_coloc:
                # Pure AST co-location with no semantic confirmation — drop.
                logger.debug(
                    "[FILTER] Dropped AST-colocated-only (no semantic): %s", test_id
                )
                continue
            # ─────────────────────────────────────────────────────────────────

            if passes_threshold or llm_bypass or is_ast_any:
                # Set explicit flags based on match_details and original sources
                test['is_ast_match'] = has_ast
                test['is_semantic_match'] = has_semantic
                filtered_tests.append(test)
        
        if _apply_conf_filter:
            logger.info(
                "[FILTER] Threshold pass: %s -> %s test(s)",
                len(combined_results.get("tests", [])),
                len(filtered_tests),
            )

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
                    has_ast_in_details = any(m.get('type') in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'direct_test_file', 'module_pattern', 'integration', 'cochanged_test_suite'] 
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
                
                # Flag semantic-only tests with no file/symbol overlap (possible false positives)
                semantic_only_no_overlap = False
                if is_semantic and not is_ast:
                    changed_stems = {Path(f).stem for f in parsed_diff.get('changed_files', [])}
                    test_path = (test.get('test_file_path') or test.get('file_path') or '')
                    overlap = any(stem and stem in test_path for stem in changed_stems)
                    if not overlap:
                        semantic_only_no_overlap = True
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
                    'semantic_only_no_overlap': semantic_only_no_overlap,  # True if semantic-only and no changed-file overlap
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
            'schemas_searched': list(schemas_resolved),
        }
        
        # Check database status (aggregate across schemas_searched)
        try:
            with conn.cursor() as cursor:
                ri_sum = tr_sum = tf_sum = 0
                for _sch in schemas_resolved:
                    cursor.execute(f"SELECT COUNT(*) FROM {_sch}.reverse_index")
                    ri_sum += int(cursor.fetchone()[0] or 0)
                    cursor.execute(f"SELECT COUNT(*) FROM {_sch}.test_registry")
                    tr_sum += int(cursor.fetchone()[0] or 0)
                    cursor.execute(f"SELECT COUNT(*) FROM {_sch}.test_function_mapping")
                    tf_sum += int(cursor.fetchone()[0] or 0)
                diagnostics['db_reverse_index_count'] = ri_sum
                diagnostics['db_test_registry_count'] = tr_sum
                diagnostics['db_function_mapping_count'] = tf_sum
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
        
        # Diff impact: coverage_gaps, breakage_warnings, per-test will_fail_reason
        coverage_gaps = []
        breakage_warnings = []
        try:
            from git_diff_processor.selection_engine import compute_diff_impact
            coverage_gaps, breakage_warnings, test_breakage_map = compute_diff_impact(
                conn,
                target_schema,
                search_queries,
                all_tests,
                combined_results.get("match_details", {}),
            )
            for test in all_tests:
                tid = test.get('test_id')
                if tid and tid in test_breakage_map:
                    test['will_fail_reason'] = test_breakage_map[tid]
        except Exception as e:
            logger.warning(f"Diff impact step failed: {e}")

        if _dz_result.get("is_complete_dead_zone"):
            for _df in _dz_result.get("dead_files", []):
                coverage_gaps.append({
                    "type": "COMPLETELY_UNTESTED_FILE",
                    "file": _df["file"],
                    "severity": "HIGH",
                    "reason": _df["reason"],
                    "action_required": (
                        f"Add tests that reference '{_df['stem']}' and update "
                        f"your test manifest / sources[] so the DB index covers it."
                    ),
                })
            for _sym in search_queries.get("exact_matches", []):
                coverage_gaps.append({
                    "type": "COMPLETELY_UNTESTED_SYMBOL",
                    "symbol": _sym,
                    "severity": "HIGH",
                    "reason": f"Symbol '{_sym}' has no test coverage in the DB.",
                    "action_required": f"Write tests that exercise '{_sym}'.",
                })

        # Impact intelligence: scenarios, dead zones, linkage, FP/FN transparency
        impact_intelligence: Dict[str, Any] = {}
        try:
            from git_diff_processor.diff_scenario_analysis import (
                build_impact_intelligence,
                merge_per_test_intelligence,
            )

            impact_intelligence = build_impact_intelligence(
                conn,
                target_schema,
                parsed_diff,
                search_queries,
                diff_content or "",
                all_tests,
                combined_results.get("match_details", {}),
            )
            merge_per_test_intelligence(all_tests, impact_intelligence)
            # Per-test fields already on each test; omit bulk map from JSON
            impact_intelligence = {
                k: v
                for k, v in impact_intelligence.items()
                if k != "per_test_intelligence"
            }
        except Exception as e:
            logger.warning(f"Impact intelligence step failed: {e}")

        # ── Summary counts that match the table (not raw pipeline totals) ─────
        vector_search_total = int(
            semantic_results.get('total_tests')
            or len(semantic_results.get('tests') or [])
            or 0
        )
        final_ids = {t.get("test_id") for t in all_tests if t.get("test_id")}
        ast_in_final = sum(1 for t in all_tests if t.get("is_ast_match"))
        semantic_in_final = sum(1 for t in all_tests if t.get("is_semantic_match"))
        ast_only_final = sum(
            1
            for t in all_tests
            if t.get("is_ast_match") and not t.get("is_semantic_match")
        )
        semantic_only_final = sum(
            1
            for t in all_tests
            if t.get("is_semantic_match") and not t.get("is_ast_match")
        )
        both_final = sum(
            1
            for t in all_tests
            if t.get("is_ast_match") and t.get("is_semantic_match")
        )
        vector_ids_in_final = original_semantic_test_ids & final_ids
        vector_dropped = vector_search_total - len(vector_ids_in_final)

        _co = combined_results.get("cochange_selection") or {}
        _funnel_lines = [
            "Step 1 — AST/database: {} test(s) matched before semantic search.".format(
                ast_count_snapshot
            ),
            "Step 2 — Vector search: {} candidate test(s) retrieved from embeddings (not all will be shown).".format(
                vector_search_total
            ),
        ]
        if _co.get("mode") == "tight_cochanged_suite":
            _funnel_lines.append(
                "Step 3 — Tight co-change: only tests in the modified test file(s) {} are kept; "
                "{} vector candidate(s) were dropped because they live in other files.".format(
                    _co.get("suite_file_basenames", []),
                    max(0, vector_dropped),
                )
            )
        _funnel_lines.append(
            "Final table — {} test(s): {} AST-only, {} semantic-only, {} both.".format(
                len(all_tests),
                ast_only_final,
                semantic_only_final,
                both_final,
            )
        )
        _sem_coloc_count_in_final = sum(
            1 for t in all_tests
            if not t.get("is_semantic_match")
            and any(
                m.get("match_strategy") == "semantic_colocated_file"
                for m in combined_results.get("match_details", {}).get(t.get("test_id", ""), [])
            )
        )
        selection_funnel = {
            "ast_database_hits_initial": ast_count_snapshot,
            "vector_search_candidates": vector_search_total,
            "vector_hits_in_final_selection": len(vector_ids_in_final),
            "vector_hits_not_shown": max(0, vector_dropped),
            "semantic_colocation_additions": _sem_coloc_count_in_final,
            "final_total": len(all_tests),
            "final_ast_linked": ast_in_final,
            "final_semantic_linked": semantic_in_final,
            "final_breakdown": {
                "ast_only": ast_only_final,
                "semantic_only": semantic_only_final,
                "both": both_final,
            },
            "why_vector_count_differs": (
                "The big number is how many tests the vector index returned as *similar*. "
                "Your table only lists tests we *selected* after rules (e.g. same modified test file). "
                "So 15 explored ≠ 15 shown."
            ),
            "steps_plain_english": _funnel_lines,
        }
        from semantic.config import DEFAULT_SIMILARITY_THRESHOLD as _dst_fallback

        _vte = float((semantic_config or {}).get("_vector_threshold_effective", _dst_fallback))
        _vts = (semantic_config or {}).get("_vector_threshold_source_note", "default")
        selection_funnel["vector_similarity_threshold_used"] = float(_vte)
        selection_funnel["vector_threshold_source"] = str(_vts)
        selection_funnel["tuning_false_positive_vs_false_negative"] = {
            "lower_threshold": (
                "More tests pass the vector filter → fewer missed relevant tests (false negatives ↓), "
                "but more unrelated tests appear (false positives ↑)."
            ),
            "higher_threshold": (
                "Fewer weak matches → cleaner list (false positives ↓), "
                "but you may miss borderline-relevant tests (false negatives ↑)."
            ),
            "how_to_try": (
                "Windows PowerShell: $env:SEMANTIC_VECTOR_THRESHOLD='0.22'; restart uvicorn. "
                "Or SEMANTIC_VECTOR_THRESHOLD_PRESET=lenient|moderate|strict. "
                "Compare vector_search_candidates in selectionFunnel between runs."
            ),
        }
        if _dz_result.get("is_complete_dead_zone"):
            selection_funnel["complete_dead_zone"] = True
            selection_funnel["dead_zone_note"] = (
                "All changed files lack DB test linkage; vector search still ran — "
                "treat semantic-only rows with extra scrutiny."
            )

        return {
            'total_tests': len(all_tests),
            'ast_matches': ast_in_final,
            'semantic_matches': semantic_in_final,
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
            'diagnostics': diagnostics,
            'coverage_gaps': coverage_gaps,
            'breakage_warnings': breakage_warnings,
            'impact_intelligence': impact_intelligence,
            'cochange_selection': combined_results.get('cochange_selection'),
            'selection_funnel': selection_funnel,
            'semantic_search_candidates': vector_search_total,
            'semantic_vector_threshold': _vte,
            'semantic_threshold_source': _vts,
            'rag_diagnostics': (semantic_results or {}).get('rag_diagnostics'),
            'dead_zone_result': _dz_result,
        }
