"""
Programmatic interface for processing git diff and selecting tests.

This module provides functions that can be called from other services
without printing to console.
"""

import re
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

from deterministic.db_connection import get_connection, DB_SCHEMA, validate_schema_name

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
                    validate_schema_name(_sch)
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
                except ValueError as e:
                    logger.error("[SQL] Rejecting schema %r: %s", _sch, e)
                    continue
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
        if ast_results is None:
            logger.error(
                "[AST] _merge_ast_results returned None for schemas %s — using empty result",
                schemas_resolved,
            )
            ast_results = {"tests": [], "match_details": {}, "total_tests": 0}
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

        # Prepare shared LLM service handle (reused across classification and post-merge reasoning)
        llm_service = None

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

                # ── New: LLM classification of semantic results (Critical|High|NonRelevant) ──
                # Classify and prune NonRelevant BEFORE merging with AST. No numeric thresholds.
                # Snapshot lets us restore rows for tests AST already matched (structural truth).
                _sem_pre_classify = {
                    str(t.get("test_id")): dict(t)
                    for t in (semantic_results.get("tests") or [])
                    if t.get("test_id") is not None
                }
                try:
                    from services.llm_reasoning_service import LLMReasoningService
                    if llm_service is None:
                        llm_service = LLMReasoningService()
                    sem_tests = list(semantic_results.get("tests") or [])
                    if sem_tests:
                        classifications = await llm_service.classify_semantic_candidates(
                            diff_content or "",
                            sem_tests,
                        )
                        if classifications:
                            by_id = {
                                str(c["test_id"]): c
                                for c in classifications
                                if c.get("test_id") is not None
                            }
                            kept, dropped = 0, 0
                            pruned_tests = []
                            for t in sem_tests:
                                tid = t.get("test_id")
                                c = by_id.get(str(tid)) if tid is not None else None
                                if not c:
                                    # If missing classification, fail open: keep
                                    pruned_tests.append(t)
                                    continue
                                label = c.get("label")
                                reason = c.get("reason", "")
                                if label == "NonRelevant":
                                    dropped += 1
                                    continue
                                # Keep Critical/High and annotate
                                t["semanticLabel"] = label
                                t["semanticReason"] = reason
                                pruned_tests.append(t)
                                kept += 1
                            if dropped > 0 or kept > 0:
                                logger.info("[SEMANTIC] Classification kept=%s dropped=%s", kept, dropped)
                            # Do not drop vector evidence for tests AST already selected.
                            _ast_ids_class = {
                                str(t.get("test_id"))
                                for t in ast_results.get("tests", [])
                                if t.get("test_id") is not None
                            }
                            _pruned_ids = {
                                str(t.get("test_id"))
                                for t in pruned_tests
                                if t.get("test_id") is not None
                            }
                            _restored = 0
                            for _sid, row in _sem_pre_classify.items():
                                if _sid in _ast_ids_class and _sid not in _pruned_ids:
                                    pruned_tests.append(row)
                                    _restored += 1
                            if _restored:
                                logger.info(
                                    "[SEMANTIC] Restored %s AST-linked vector hit(s) "
                                    "the classifier had marked NonRelevant",
                                    _restored,
                                )
                            semantic_results["tests"] = pruned_tests
                            semantic_results["total_tests"] = len(pruned_tests)
                except Exception as _cls_err:
                    logger.warning("Semantic classification step skipped (error): %s", _cls_err)

                # ── AST–semantic supplement: cosine(diff query, test vector) without global threshold ──
                # When AST is strong, adaptive threshold (e.g. 0.45) hides moderate similarity for
                # tests AST already found; LLM relevance can still be high. Score those tests here.
                try:
                    from semantic.retrieval.ast_semantic_supplement import (
                        merge_supplement_into_semantic_results,
                        supplement_semantic_hits_for_ast_tests,
                    )

                    _diag = (semantic_config or {}).get("_rag_diagnostics") or {}
                    _qlist = _diag.get("queries_used_strings") or []
                    _primary_q = (_qlist[0] or "").strip() if _qlist else ""
                    _prim_emb = _diag.get("primary_query_embedding")
                    if _primary_q and ast_results.get("tests"):
                        _sup_map = await supplement_semantic_hits_for_ast_tests(
                            conn,
                            ast_results,
                            _primary_q,
                            _resolved_tr,
                            precomputed_query_embedding=_prim_emb,
                        )
                        if isinstance(semantic_config, dict):
                            semantic_config["_ast_semantic_supplement_scores"] = _sup_map
                        merge_supplement_into_semantic_results(
                            semantic_results,
                            ast_results,
                            _sup_map,
                        )
                        logger.info(
                            "[SEMANTIC] After AST supplement, semantic candidate count=%s",
                            semantic_results.get("total_tests", 0),
                        )
                except Exception as _sup_err:
                    logger.warning("[SEMANTIC] AST supplement step skipped: %s", _sup_err)
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}")
                semantic_results = {'total_tests': 0, 'tests': [], 'error': str(e)}
        
        # Use ast_results (from find_tests_ast_only) as the base for combined_results.
        # find_tests_ast_only already runs all AST strategies (0-4a), including the
        # new Strategy 4 (file stem-based sibling test lookup), so it produces a
        # richer result set than find_affected_tests (which lacks Strategy 4).
        # Bug 4 fix: copy instead of alias so mutations to combined_results do not
        # silently mutate ast_results (the supplement step above still reads the
        # original ast_results safely because this copy is made after that step).
        ast_count_snapshot = ast_results.get('total_tests', 0)
        combined_results = dict(ast_results)
        combined_results['tests'] = list(ast_results.get('tests', []))
        combined_results['match_details'] = dict(ast_results.get('match_details', {}))

        _sem_rows = semantic_results.get('tests') or []
        _ast_ids_pre = {t.get('test_id') for t in combined_results.get('tests', []) if t.get('test_id')}
        _sem_ids_pre = {t.get('test_id') for t in _sem_rows if t.get('test_id')}
        _overlap_pre = len(_ast_ids_pre & _sem_ids_pre)
        _semantic_only_pre = len(_sem_ids_pre - _ast_ids_pre)
        if not _sem_rows:
            logger.info(
                "[MERGE] Single combined result set: %s test_id(s) from AST only (no semantic rows).",
                ast_count_snapshot,
            )
        else:
            logger.info(
                "[MERGE] Single combined result set (not additive): AST base %s test_id(s); "
                "merging %s semantic retrieval row(s) → %s test_id(s) overlap AST (enriched), "
                "%s test_id(s) semantic-only — final count is not %s+%s.",
                ast_count_snapshot,
                len(_sem_rows),
                _overlap_pre,
                _semantic_only_pre,
                ast_count_snapshot,
                len(_sem_rows),
            )

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
        # When a test file has been confirmed by semantic OR AST search, expand
        # to include other tests in the same file whose describe label shares at
        # least one whole-word token with the changed symbols.
        #
        # Two sources seed the confirmed-file set:
        #   A) Semantic results with similarity >= _SEM_COLOC_MIN_SIM
        #   B) AST-matched test file paths — important for cross-dependent files
        #      where AST finds some tests (via reverse_index) but not siblings
        #      in the same file that are equally relevant (e.g. generateCardNumber
        #      in auth-storage.cross.test.js alongside validateEmailOrUsername).
        #
        # The whole-word token filter (_coloc_class_is_relevant) then acts as the
        # quality gate: it keeps only tests whose describe label contains at least
        # one symbol-level token from the diff (e.g. "card", "regex"), preventing
        # unrelated describes in the same file from being pulled in.
        _SEM_COLOC_MIN_SIM = 0.45
        _sem_confirmed_file_paths: set = set()

        # Source A: semantic hits
        for _sem_t in semantic_results.get('tests', []):
            if (_sem_t.get('similarity') or 0) >= _SEM_COLOC_MIN_SIM:
                _fp = _sem_t.get('test_file_path') or _sem_t.get('file_path', '')
                if _fp:
                    _sem_confirmed_file_paths.add(_fp)

        # Source B: AST-matched test file paths already in combined_tests_dict
        for _ast_t in combined_tests_dict.values():
            _fp = _ast_t.get('test_file_path') or _ast_t.get('file_path', '')
            if _fp:
                _sem_confirmed_file_paths.add(_fp)

        # ── Build the allowed token set from the diff (changed symbols / files) ──
        # Sources: exact symbol names, module-level patterns, changed class/method names,
        # and the FIRST SEGMENT of dotted class names of confirmed tests (see below).
        #
        # Deliberately excluded:
        #   - File stems (e.g. "MyFavourites" → "favourites"): too generic; causes
        #     unrelated reducer suites named "favouritesReducer" to pass the filter.
        #   - Full class name tokens of confirmed tests: prose-style describes like
        #     "action creators — wishlist and favourites" contribute generic words
        #     ("action", "creators") that match every other "action creators — X"
        #     describe group in the same file, flooding results with unrelated tests.
        _diff_class_tokens: set = set()

        def _tokenise_symbol(text: str) -> set:
            """Split a symbol/name into lowercase whole-word tokens (min 3 chars)."""
            s = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
            s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
            return {p.lower() for p in re.split(r"[^a-zA-Z0-9]+", s) if len(p) >= 3}

        def _tokenise_symbol4(text: str) -> set:
            """Same as _tokenise_symbol but requires min 4 chars.

            Used for the semantic-only precision filter: short tokens like 'api',
            'get', 'all' appear in almost every API test and cause false matches
            against unrelated files that also happen to mention APIs.
            """
            s = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
            s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
            return {p.lower() for p in re.split(r"[^a-zA-Z0-9]+", s) if len(p) >= 4}

        # Use 4-char minimum to keep the token set discriminating.
        # 3-char tokens like 'api', 'get', 'add' appear in almost every test file
        # (e.g. "watchlistApi" contains "api") and cause false co-location matches
        # when the diff touches any API-related file.  4-char minimum is consistent
        # with _specific_diff_tokens4 and the existing semantic-only precision gate.
        for _ec in search_queries.get('exact_matches', []):
            _diff_class_tokens |= _tokenise_symbol4(_ec)
        for _ec in search_queries.get('module_matches', []):
            _diff_class_tokens |= _tokenise_symbol4(_ec.rstrip('.*'))
        for _fc in parsed_diff.get('changed_classes', []):
            if _fc:
                _diff_class_tokens |= _tokenise_symbol4(_fc)
        for _mf in parsed_diff.get('changed_methods', []):
            if _mf:
                _diff_class_tokens |= _tokenise_symbol4(_mf)

        # ── Specific-symbol tokens (4-char minimum) — used to filter semantic-only
        # results that have no AST match. Restricted to identifiers that actually
        # changed (classes, methods, added/deleted symbols) — NOT module names like
        # "ApiEndPoints" or "services" that are too generic to be discriminating.
        _specific_diff_tokens4: set = set()
        for _fc in parsed_diff.get('changed_classes', []):
            if _fc:
                _specific_diff_tokens4 |= _tokenise_symbol4(_fc)
        for _mf in parsed_diff.get('changed_methods', []):
            if _mf:
                _specific_diff_tokens4 |= _tokenise_symbol4(_mf)
        for _sym in search_queries.get('added_symbols', []):
            if _sym:
                _specific_diff_tokens4 |= _tokenise_symbol4(_sym)
        for _sym in search_queries.get('deleted_symbols', []):
            if _sym:
                _specific_diff_tokens4 |= _tokenise_symbol4(_sym)

        # Seed the FIRST SEGMENT of dotted class names from confirmed tests.
        # Only dotted names are considered — prevents prose-style describes like
        # "action creators — wishlist and favourites" from contributing generic
        # words such as "action" or "creators".  Use 4-char minimum consistent
        # with the rest of _diff_class_tokens.
        for _ct in combined_tests_dict.values():
            _cls = (_ct.get('class_name') or '').strip()
            if _cls and '.' in _cls:
                _first_seg = _cls.split('.')[0].strip()
                if len(_first_seg) >= 4:
                    _diff_class_tokens |= _tokenise_symbol4(_first_seg)

        def _coloc_class_is_relevant(class_name: Optional[str]) -> bool:
            """True when the describe label shares at least one whole-word token with the diff.

            Uses 4-char minimum tokens (same as _specific_diff_tokens4) so generic
            3-char words like 'api', 'get', 'add' that appear in virtually every
            test file cannot accidentally match the co-location filter.
            """
            if not class_name:
                return True  # unknown describe → keep (benefit of the doubt)
            _cn_tokens = _tokenise_symbol4(class_name)
            return bool(_cn_tokens & _diff_class_tokens)

        def _sem_only_is_relevant(class_name: Optional[str]) -> bool:
            """Precision gate for semantic-only results (no AST confirmation).

            Two-tier check (either tier suffices):

            Tier 1 — Specific symbols: does the test's describe label share ≥1
              4-char token with changed methods / added symbols / deleted symbols?
              Example: "FAQ fallback logic — resolveFaqItems" matches
              "resolveFaqItems" → tokens {resolve, items} → pass.

            Tier 2 — Module-level tokens: does the label share ≥1 4-char token
              with the broader diff token set (which includes module/file names)?
              This catches tests that describe DATA or STRUCTURE aspects of a
              changed file rather than a specific function name.
              Example: "FAQDataList — size" → {data, list, size} overlaps with
              {data, list} from 'FAQDataList' module name → pass.
              The secondary tier still blocks unrelated tests because their class
              names contain domain words absent from _diff_class_tokens.

            Generic tokens < 4 chars (e.g. 'api', 'get', 'all') are always
            excluded to prevent universal API-file false positives.

            Returns True (keep) when:
            - class_name is unknown (benefit of the doubt)
            - Tier 1 overlap found
            - Tier 2 overlap found
            """
            if not class_name:
                return True
            _cn_tokens4 = _tokenise_symbol4(class_name)
            # Tier 1: specific changed symbols (most discriminating)
            if _specific_diff_tokens4 and (_cn_tokens4 & _specific_diff_tokens4):
                return True
            # Tier 2: broader module-level diff tokens (catches data/structure tests
            # for the same changed file whose describe labels don't echo the function)
            if _cn_tokens4 & _diff_class_tokens:
                return True
            return False

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
                                            'type': 'semantic_colocation',
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

        # Recalculate confidence scores (AST + Semantic only — no LLM scoring step)
        from git_diff_processor.git_diff_processor import calculate_confidence_score_with_breakdown
        for test in combined_results.get('tests', []):
            test_id = test.get('test_id')
            matches = combined_results.get('match_details', {}).get(test_id, [])
            test_type = test.get('test_type')
            new_score, _ = calculate_confidence_score_with_breakdown(
                matches,
                test_type,
                llm_score=None
            )
            test['confidence_score'] = new_score
        
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
            
            # Check if test has semantic match
            # IMPORTANT: Only mark as semantic if it was ORIGINALLY found by semantic search
            # Don't rely on similarity value alone, as it might have been added during merging.
            # 'semantic_colocation' is also a semantic signal — tests pulled in because a
            # sibling in the same file had a high vector hit.
            has_semantic = (
                test_id in original_semantic_test_ids or
                any(
                    m.get('type') in ('semantic', 'semantic_colocation')
                    for m in combined_match_details.get(test_id, [])
                )
            )
            
            # Check if test has AST match (from match_details or was in original AST results)
            has_ast = (
                test_id in ast_test_ids_from_match_details or
                test_id in original_ast_test_ids or
                any(m.get('type') in ['exact', 'module', 'function_level', 'direct_file', 'direct_file_match', 'direct_test_file', 'module_pattern', 'integration', 'cochanged_test_suite'] 
                    for m in combined_match_details.get(test_id, []))
            )

            # Same-file siblings of a strong semantic hit (see SEM-COLOC above). They are
            # not type==semantic, so has_semantic is False — but composite can sit below
            # 42 % and they would be wrongly dropped unless we treat them like vetted suite members.
            _has_sem_coloc_flag = any(
                m.get('match_strategy') == 'semantic_colocated_file'
                for m in combined_match_details.get(test_id, [])
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
            #    • MIN_CONFIDENCE_THRESHOLD when AST-ONLY, no semantic signal.
            passes_threshold = (confidence_score / 100.0) >= MIN_CONFIDENCE_THRESHOLD

            _composite_ratio = confidence_score / 100.0
            if has_ast and has_semantic:
                # "Both" — use lenient 30 % floor (semantic already vouches for it).
                is_ast_any = _composite_ratio >= 0.30
            elif _has_sem_coloc_flag:
                # Included because another test in this file had high vector similarity;
                # do not require 42 % composite (often AST-only scoring for this row).
                is_ast_any = True
            elif has_ast and not has_semantic:
                is_ast_any = _composite_ratio >= MIN_CONFIDENCE_THRESHOLD
            else:
                is_ast_any = False

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

            # ── Module-name AST token gate ────────────────────────────────────
            # Problem: module-level pattern queries AND "exact" queries that used
            # a file STEM (e.g. "constants") instead of a specific changed symbol
            # can match tests from a DIFFERENT source file that shares the same
            # stem.  Example: src/navigation/constants.js (changed) and
            # src/types/constants.ts (source of regex tests) both normalise to
            # production_class = "constants".  When the diff only touches the
            # navigation file, all regex tests are falsely promoted.
            #
            # SCOPE: only all-lowercase stems are collision-prone (e.g. "constants",
            # "utils", "types").  CamelCase stems (e.g. "FAQDataList",
            # "FrequentlyAskedQuestions", "HomeIntroPage") are specific enough to
            # be practically unique — applying the gate there would incorrectly
            # drop legitimate tests whose describe labels don't echo the module name
            # (e.g. "FAQ fallback logic — resolveFaqItems" tests).
            #
            # Gate: if ALL AST evidence for a test comes from collision-prone stems,
            # require the test's class/describe name to share ≥1 4-char token with
            # the diff's changed symbols.  Tests with no vocabulary overlap are
            # dropped as stem-collision false positives.
            if has_ast and _diff_class_tokens:
                _module_names_in_exact = frozenset(
                    search_queries.get('module_exact_matches', [])
                )
                # Collision-prone = all-lowercase stems (generic, widely shared).
                # CamelCase stems are treated as strong evidence.
                _collision_prone = frozenset(
                    n for n in _module_names_in_exact if n == n.lower()
                )
                _has_strong_ast = any(
                    m.get('type') in (
                        'function_level', 'direct_file', 'direct_file_match',
                        'direct_test_file', 'integration', 'cochanged_test_suite',
                    ) or (
                        # 'exact' match is strong when class is NOT a collision-prone stem.
                        # CamelCase module names and specific symbols are strong.
                        m.get('type') == 'exact' and
                        m.get('class', '') not in _collision_prone
                    ) or (
                        # 'module' type is strong when the pattern isn't collision-prone.
                        m.get('type') == 'module' and
                        m.get('pattern', '').replace('.*', '') not in _collision_prone
                    )
                    for m in combined_match_details.get(test_id, [])
                    if m.get('type') != 'semantic'
                )
                if not _has_strong_ast:
                    _test_class_m = (
                        test.get('class_name') or test.get('test_class') or ''
                    )
                    if _test_class_m and not _coloc_class_is_relevant(_test_class_m):
                        logger.debug(
                            "[FILTER] Dropped collision-prone module AST (no token overlap): %s [%s]",
                            test_id, _test_class_m,
                        )
                        continue
            # ─────────────────────────────────────────────────────────────────

            # ── Semantic-only precision gate ─────────────────────────────────
            # Tests that have NO AST match and came only from the semantic RAG
            # pipeline are checked for vocabulary alignment with the diff's actual
            # changed symbols (4-char minimum token, to exclude generic words like
            # 'api', 'get', 'all' that appear in virtually every API test).
            #
            # If the token gate PASSES, _sem_token_gate_passed is set True so the
            # test is kept even though pure-semantic confidence scores are capped
            # at 40 (= 100 × 0.40), which is always below the 42 % threshold.
            # Trusting LLM classification + vocabulary gate here is equivalent to
            # the logic that trusts co-located tests via _has_sem_coloc_flag.
            _sem_token_gate_passed = False
            if has_semantic and not has_ast and not _has_sem_coloc_flag:
                _test_class = (
                    test.get('class_name')
                    or test.get('test_class')
                    or ''
                )
                if not _sem_only_is_relevant(_test_class):
                    logger.debug(
                        "[FILTER] Dropped semantic-only (no symbol overlap): %s [%s]",
                        test_id, _test_class,
                    )
                    continue
                # Token gate passed — bypass confidence threshold for this test
                _sem_token_gate_passed = True
            # ─────────────────────────────────────────────────────────────────

            if passes_threshold or is_ast_any or _sem_token_gate_passed:
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
                # ── Rule-based dependency hint (fast, no LLM) ────────────
                # This produces a rule_hint that is:
                #   a) passed to the LLM as context so it can skip obvious cases
                #   b) used as a fallback when LLM is unavailable or times out
                #
                # Rules:
                #   independent    — direct_import / source_annotation /
                #                    describe_label / function_level match
                #   cross_dependent — semantic-only, transitive import,
                #                     co-location, module-stem-only match
                _DIRECT_REF_TYPES = frozenset({
                    'direct_import', 'source_annotation',
                    'source_annotation_normalized', 'describe_label',
                })
                _rule_hint = 'cross_dependent'   # conservative default
                if is_ast:
                    _ast_refs = {
                        m.get('reference_type', '')
                        for m in test_matches
                        if m.get('type') not in ('semantic',)
                    }
                    _ast_mtypes = {
                        m.get('type', '')
                        for m in test_matches
                        if m.get('type') not in ('semantic',)
                    }
                    if (
                        _ast_refs & _DIRECT_REF_TYPES
                        or 'function_level' in _ast_mtypes
                        or (is_ast and not is_semantic and 'exact' in _ast_mtypes)
                    ):
                        _rule_hint = 'independent'
                # Semantic-only → cross_dependent (already default)

                test_dict = {
                    'test_id': test_id,
                    'class_name': test.get('class_name'),
                    'method_name': test.get('method_name'),
                    'test_file_path': test.get('test_file_path') or test.get('file_path', ''),
                    'test_type': test.get('test_type'),
                    'confidence': 'high' if test.get('confidence_score', 0) >= 70 else 'medium' if test.get('confidence_score', 0) >= 50 else 'low',
                    'confidence_score': test.get('confidence_score', 0),
                    'match_type': match_type,
                    'matched_classes': matched_classes,
                    'similarity': similarity,
                    'is_ast_match': is_ast,
                    'is_semantic_match': is_semantic,
                    'semantic_only_no_overlap': semantic_only_no_overlap,
                    # dependency_type starts as rule_hint; overwritten by LLM below
                    'dependency_type': _rule_hint,
                    'dependency_reason': None,
                    'dependency_confidence': None,
                    'dependency_source': 'rule',   # updated to 'llm' after LLM pass
                    'rule_hint': _rule_hint,        # kept so LLM prompt can use it
                    # Pass-through of semantic retrieval LLM label/reason when present
                    'semanticLabel': test.get('semanticLabel'),
                    'semanticReason': test.get('semanticReason'),
                }
                
                all_tests.append(test_dict)
        
        # ── LLM Dependency Classification ────────────────────────────────────
        # After all tests are collected, ask the LLM to verify/override the
        # fast rule-based dependency_type for each test.
        #
        # Why here (not inside the per-test loop)?
        #   The LLM call is ASYNC and BATCHED — doing it per-test would mean
        #   one LLM call per test (very slow).  Doing it once on the full list
        #   costs 2-4 LLM calls for a typical 30-test run.
        #
        # Fallback contract:
        #   If LLM is unavailable, times out, or returns bad JSON,
        #   each test already has dependency_type = rule_hint, so the UI
        #   still shows a reasonable classification.
        if all_tests:
            try:
                from services.llm_reasoning_service import LLMReasoningService
                if llm_service is None:
                    llm_service = LLMReasoningService()

                dep_classifications = await llm_service.classify_dependency_type(
                    diff_content or "",
                    all_tests,          # each has rule_hint, class_name, method_name, match_type
                )

                if dep_classifications:
                    # Build a quick lookup: test_id → classification result
                    dep_by_id = {str(c["test_id"]): c for c in dep_classifications}
                    llm_applied = 0
                    for t in all_tests:
                        tid = str(t.get("test_id", ""))
                        c   = dep_by_id.get(tid)
                        if not c:
                            # LLM didn't classify this test → keep rule_hint
                            continue
                        # Map LLM label → internal snake_case key
                        llm_label = c.get("label", "")
                        t["dependency_type"] = (
                            "independent"
                            if llm_label == "Independent"
                            else "cross_dependent"
                        )
                        t["dependency_reason"]     = c.get("reason", "")
                        t["dependency_confidence"] = c.get("confidence", "low")
                        t["dependency_source"]     = "llm"
                        llm_applied += 1

                    logger.info(
                        "[DEP_CLASSIFY] Applied LLM classification to %d/%d test(s)",
                        llm_applied, len(all_tests),
                    )
                else:
                    logger.info("[DEP_CLASSIFY] LLM returned no results — using rule_hint for all tests")

            except Exception as _dep_err:
                logger.warning(
                    "[DEP_CLASSIFY] Dependency classification failed (%s) — rule_hint kept",
                    _dep_err,
                )

        # Strip internal rule_hint field before sending response (not needed by client)
        for t in all_tests:
            t.pop("rule_hint", None)
        # ─────────────────────────────────────────────────────────────────────

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
                    try:
                        validate_schema_name(_sch)
                    except ValueError as e:
                        logger.error("[SQL] Skipping invalid schema %r in diagnostics: %s", _sch, e)
                        continue
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

        # Counts computed after LLM pass so they reflect final labels
        _independent_count = sum(1 for t in all_tests if t.get('dependency_type') == 'independent')
        _cross_dep_count   = sum(1 for t in all_tests if t.get('dependency_type') == 'cross_dependent')
        logger.info(
            "[DEP_CLASSIFY] Final: independent=%d cross_dependent=%d",
            _independent_count, _cross_dep_count,
        )

        return {
            'total_tests': len(all_tests),
            'ast_matches': ast_in_final,
            'semantic_matches': semantic_in_final,
            'independent_count': _independent_count,
            'cross_dependent_count': _cross_dep_count,
            'tests': all_tests,
            'semantic_results': semantic_results,  # Include semantic results for enhancement
            'match_details': combined_results.get('match_details', {}),  # Include match_details for better match type detection
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
