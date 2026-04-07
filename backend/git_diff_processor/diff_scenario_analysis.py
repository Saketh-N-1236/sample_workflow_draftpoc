"""
Impact intelligence: scenario tags, dead zones, linkage profiles, FP/FN hints.

Maps user concepts:
  - Fully cross-dependent / fully standalone  → test_dependencies row counts
  - Tight isolation / max blast radius       → diff breadth
  - Mixed-language diff                      → multiple source extensions
  - Micro hotfix (null/guard)                → dominant guard-style +lines
  - Dead zone (zero coverage)                → changed symbols with no reverse_index
  - Action-type cascade                      → documented strategy order
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Lines that look like null-safety / defensive micro-edits (not exhaustive)
_GUARD_LINE_PATTERNS = re.compile(
    r"(?:"
    r"\?\?|\?\.|if\s*\([^)]*(?:null|undefined|None|==\s*0\b)"
    r"|optional\s*\.|Optional<|@Nullable|nonnull|assert\.|guard"
    r"|isNull|isNone|is_empty|throw new (?:Illegal|NullPointer)"
    r")",
    re.IGNORECASE,
)

# Order of strategies (for transparency / "action cascade")
ACTION_TYPE_CASCADE = [
    "0_function_mapping",  # test_function_mapping — calls/patches to changed function
    "1_direct_test_file",  # co-located test_*.py / *.test.ts etc.
    "2_integration_e2e",     # module-tagged integration tests
    "3_exact_symbol",      # reverse_index production_class exact
    "4_module_pattern",    # broader module — higher FP risk
    "5_same_file_expand",  # siblings in same test file (guarded)
    "6_semantic_rag",      # embedding similarity — verify manually
    "7_llm_reasoning",     # optional relevance filter
]


def _changed_extensions(changed_files: List[str]) -> Set[str]:
    return {Path(f).suffix.lower() for f in changed_files if f}


def classify_diff_scenarios(
    parsed_diff: Dict[str, Any],
    search_queries: Dict[str, Any],
    diff_content: str,
) -> Dict[str, Any]:
    """
    Tag the diff shape for UI / policy (not for filtering tests by default).
    """
    files = list(parsed_diff.get("changed_files") or [])
    tags: List[str] = []
    exts = _changed_extensions(files)

    source_exts = {e for e in exts if e in (
        ".py", ".java", ".js", ".ts", ".tsx", ".jsx", ".c", ".cpp", ".cc", ".h", ".hpp",
        ".go", ".rb", ".cs", ".kt",
    )}
    if len(source_exts) > 1:
        tags.append("MIXED_LANGUAGE_DIFF")

    n_files = len(files)
    n_exact = len(search_queries.get("exact_matches") or [])
    n_fn = len(search_queries.get("changed_functions") or [])

    if n_files >= 12 or (n_exact >= 20 and n_files >= 5):
        tags.append("MAXIMUM_BLAST_RADIUS")
    elif n_files <= 1 and n_exact <= 4 and n_fn <= 2:
        tags.append("TIGHT_FEATURE_ISOLATION")

    plus_lines = [
        ln
        for ln in (diff_content or "").split("\n")
        if ln.startswith("+") and not ln.startswith("+++")
    ]
    if plus_lines and len(plus_lines) <= 20:
        guarded = sum(1 for ln in plus_lines if _GUARD_LINE_PATTERNS.search(ln))
        if guarded >= max(2, int(0.45 * len(plus_lines))):
            tags.append("MICRO_GUARD_HOTFIX")

    if n_fn >= 1:
        tags.append("SYMBOL_LEVEL_CHANGES")

    return {
        "scenario_tags": tags,
        "changed_file_count": n_files,
        "source_extensions": sorted(source_exts),
        "action_type_cascade": list(ACTION_TYPE_CASCADE),
        "precision_notes": _precision_notes(tags, n_files, n_exact),
    }


def _precision_notes(tags: List[str], n_files: int, n_exact: int) -> List[str]:
    notes = []
    if "MICRO_GUARD_HOTFIX" in tags:
        notes.append(
            "Diff looks like small null/guard edits: prefer function-level and exact-symbol "
            "matches; module-wide matches may include false positives."
        )
    if "MAXIMUM_BLAST_RADIUS" in tags:
        notes.append(
            "Large blast radius: listed tests may miss some affected areas (false negatives). "
            "Consider broader suites or full CI."
        )
    if "MIXED_LANGUAGE_DIFF" in tags:
        notes.append(
            "Multiple languages in one diff: ensure analysis ran for each language; "
            "semantic search may bridge gaps."
        )
    if "TIGHT_FEATURE_ISOLATION" in tags:
        notes.append(
            "Small, focused change: AST matches are usually reliable; semantic hits are optional."
        )
    if not notes:
        notes.append(
            "Review tests tagged semantic-only or module-pattern with extra care (FP risk)."
        )
    return notes


# Stems shorter than this or in GENERIC_STEMS use stricter LIKE patterns (fewer false "covered").
_MIN_STEM_LEN = 4
_GENERIC_STEMS = frozenset(
    {
        "util",
        "utils",
        "index",
        "main",
        "test",
        "tests",
        "common",
        "base",
        "core",
        "api",
        "data",
        "mock",
        "helper",
        "helpers",
        "config",
        "types",
        "type",
    }
)


def _dead_zone_like_patterns(stem: str, fpath: str) -> List[str]:
    """Build ILIKE patterns for reverse_index / module_name coverage checks."""
    stem = stem or ""
    patterns: List[str] = []
    norm = (fpath or "").replace("\\", "/")
    if "/" in norm:
        tail2 = "/".join(norm.split("/")[-2:])
        if tail2 and len(tail2) >= 5:
            patterns.append(f"%{tail2}%")
    if len(stem) >= _MIN_STEM_LEN and stem.lower() not in _GENERIC_STEMS:
        patterns.append(f"%{stem}%")
    else:
        if stem:
            patterns.extend((f"{stem}.%", f"%.{stem}"))
    out: List[str] = []
    seen: Set[str] = set()
    for p in patterns:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _symbol_coverage_patterns(symbol: str) -> List[str]:
    """Patterns for reverse_index / test_function_mapping aligned with file-level logic."""
    if not symbol:
        return []
    last = symbol.split(".")[-1]
    pats = [symbol, f"{symbol}.%", f"%.{symbol}"]
    if last and last != symbol:
        if len(last) >= _MIN_STEM_LEN and last.lower() not in _GENERIC_STEMS:
            pats.append(f"%{last}%")
        else:
            pats.extend((f"{last}.%", f"%.{last}"))
    out: List[str] = []
    seen: Set[str] = set()
    for p in pats:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _count_distinct_tests_ilike(
    cur, schema: str, table: str, column: str, patterns: List[str]
) -> int:
    if not patterns or not schema:
        return 0
    wh = " OR ".join([f"{column} ILIKE %s"] * len(patterns))
    cur.execute(
        f"SELECT COUNT(DISTINCT test_id) FROM {schema}.{table} WHERE {wh}",
        patterns,
    )
    return int(cur.fetchone()[0] or 0)


def _file_db_coverage_one_schema(
    cur, schema: str, stem: str, fpath: str
) -> int:
    """Distinct tests referencing this file stem (reverse_index + test_function_mapping)."""
    patterns = _dead_zone_like_patterns(stem, fpath)
    if not patterns:
        return 0
    ri = _count_distinct_tests_ilike(cur, schema, "reverse_index", "production_class", patterns)
    tfm = 0
    try:
        tfm = _count_distinct_tests_ilike(
            cur, schema, "test_function_mapping", "module_name", patterns
        )
    except Exception:
        pass
    # Same test may appear in both — approximate union as max + min is wrong; use separate OR query is heavy.
    # Conservative: use max(ri, tfm) if both use same patterns (underestimate union) — better FN than FP for dead zone.
    return max(ri, tfm) if ri and tfm else (ri + tfm)


def find_dead_zone_symbols(
    conn, schema: str, symbols: List[str], limit: int = 80
) -> List[Dict[str, str]]:
    """
    Changed symbols that have zero tests in reverse_index / test_function_mapping
    (aligned with file-level dead zone pattern logic).
    """
    dead: List[Dict[str, str]] = []
    if not symbols or not schema:
        return dead
    seen = set()
    try:
        with conn.cursor() as cur:
            for sym in symbols[:limit]:
                if not sym or sym in seen:
                    continue
                seen.add(sym)
                patterns = _symbol_coverage_patterns(sym)
                ri = _count_distinct_tests_ilike(
                    cur, schema, "reverse_index", "production_class", patterns
                )
                tfm = 0
                try:
                    tfm = _count_distinct_tests_ilike(
                        cur, schema, "test_function_mapping", "module_name", patterns
                    )
                except Exception:
                    pass
                n = max(ri, tfm) if ri and tfm else (ri + tfm)
                if n == 0:
                    dead.append(
                        {
                            "symbol": sym,
                            "reason": "DEAD_ZONE_ZERO_TEST_COVERAGE",
                            "message": (
                                f"No test in registry references '{sym}' (reverse_index / "
                                f"test_function_mapping)."
                            ),
                        }
                    )
    except Exception as e:
        logger.debug("dead_zone query failed: %s", e)
    return dead


def check_dead_zone_for_files(
    conn,
    schema: str,
    changed_files: List[str],
    search_queries: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Determine whether ALL changed files have zero test coverage in the DB.

    Strategy:
    1. Derive a stem from each changed file path (e.g. "signUpFormHook" from
       "src/features/auth/hooks/signUpFormHook.ts").
    2. For each stem check:
       - reverse_index.production_class ILIKE '%{stem}%'
       - test_function_mapping.module_name  ILIKE '%{stem}%'
    3. A file is "dead" only when BOTH queries return 0 rows.
    4. Returns is_complete_dead_zone=True only when EVERY changed file is dead.

    Returns:
        {
          "is_complete_dead_zone": bool,
          "dead_files":    [{"file": str, "stem": str, "reason": str}],
          "covered_files": [{"file": str, "stem": str, "coverage_count": int}],
          "checked": bool,   # False when schema/conn unavailable
        }
    """
    dead_files: List[Dict[str, Any]] = []
    covered_files: List[Dict[str, Any]] = []

    if not changed_files or not schema:
        return {
            "is_complete_dead_zone": False,
            "dead_files": [],
            "covered_files": [],
            "checked": False,
        }

    try:
        with conn.cursor() as cur:
            for fpath in changed_files:
                if not fpath:
                    continue
                stem = Path(fpath).stem  # e.g. "signUpFormHook"

                total_coverage = _file_db_coverage_one_schema(cur, schema, stem, fpath)
                if total_coverage == 0:
                    dead_files.append(
                        {
                            "file": fpath,
                            "stem": stem,
                            "reason": (
                                f"No test references '{stem}' in reverse_index "
                                f"or test_function_mapping (schema={schema})."
                            ),
                        }
                    )
                    logger.debug(
                        "[DEAD_ZONE] %s → stem=%s: 0 coverage rows", fpath, stem
                    )
                else:
                    covered_files.append(
                        {
                            "file": fpath,
                            "stem": stem,
                            "coverage_count": total_coverage,
                        }
                    )
                    logger.debug(
                        "[DEAD_ZONE] %s → stem=%s: %d coverage row(s) — not dead",
                        fpath,
                        stem,
                        total_coverage,
                    )

        is_complete = len(dead_files) > 0 and len(covered_files) == 0
        if is_complete:
            logger.info(
                "[DEAD_ZONE] Complete dead zone: all %d changed file(s) have zero DB coverage.",
                len(dead_files),
            )
        return {
            "is_complete_dead_zone": is_complete,
            "dead_files": dead_files,
            "covered_files": covered_files,
            "checked": True,
        }

    except Exception as exc:
        logger.debug("[DEAD_ZONE] check_dead_zone_for_files failed: %s", exc)
        return {
            "is_complete_dead_zone": False,
            "dead_files": [],
            "covered_files": [],
            "checked": False,
        }


def check_dead_zone_for_files_multi(
    conn,
    schemas: List[str],
    changed_files: List[str],
    search_queries: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Dead zone across multiple test-repo schemas: a file is covered if ANY schema
    has non-zero linkage for that file stem (same pattern rules as single-schema).
    """
    dead_files: List[Dict[str, Any]] = []
    covered_files: List[Dict[str, Any]] = []

    clean_schemas = [s for s in (schemas or []) if s]
    if not changed_files or not clean_schemas:
        return {
            "is_complete_dead_zone": False,
            "dead_files": [],
            "covered_files": [],
            "checked": False,
            "schemas_checked": clean_schemas,
        }

    try:
        with conn.cursor() as cur:
            for fpath in changed_files:
                if not fpath:
                    continue
                stem = Path(fpath).stem
                total_coverage = 0
                for sch in clean_schemas:
                    total_coverage = max(
                        total_coverage,
                        _file_db_coverage_one_schema(cur, sch, stem, fpath),
                    )
                if total_coverage == 0:
                    dead_files.append(
                        {
                            "file": fpath,
                            "stem": stem,
                            "reason": (
                                f"No test references '{stem}' in reverse_index or "
                                f"test_function_mapping in any of schemas {clean_schemas}."
                            ),
                        }
                    )
                    logger.debug(
                        "[DEAD_ZONE_MULTI] %s → stem=%s: 0 coverage in all schemas",
                        fpath,
                        stem,
                    )
                else:
                    covered_files.append(
                        {
                            "file": fpath,
                            "stem": stem,
                            "coverage_count": total_coverage,
                        }
                    )
                    logger.debug(
                        "[DEAD_ZONE_MULTI] %s → stem=%s: %d coverage row(s) (best schema)",
                        fpath,
                        stem,
                        total_coverage,
                    )

        is_complete = len(dead_files) > 0 and len(covered_files) == 0
        if is_complete:
            logger.info(
                "[DEAD_ZONE_MULTI] Complete dead zone: all %d changed file(s) have zero "
                "DB coverage in every bound schema.",
                len(dead_files),
            )
        return {
            "is_complete_dead_zone": is_complete,
            "dead_files": dead_files,
            "covered_files": covered_files,
            "checked": True,
            "schemas_checked": clean_schemas,
        }
    except Exception as exc:
        logger.debug("[DEAD_ZONE_MULTI] failed: %s", exc)
        return {
            "is_complete_dead_zone": False,
            "dead_files": [],
            "covered_files": [],
            "checked": False,
            "schemas_checked": clean_schemas,
        }


def linkage_profiles_for_tests(
    conn, schema: str, test_ids: List[str]
) -> Dict[str, str]:
    """
    FULLY_CROSS_DEPENDENT (many deps), FULLY_STANDALONE (few), MODERATE_LINKAGE.
    """
    out: Dict[str, str] = {}
    if not test_ids or not schema:
        return out
    ids = [t for t in test_ids if t][:500]
    if not ids:
        return out
    try:
        ph = ",".join(["%s"] * len(ids))
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT test_id, COUNT(*) AS n
                FROM {schema}.test_dependencies
                WHERE test_id IN ({ph})
                GROUP BY test_id
                """,
                ids,
            )
            for row in cur.fetchall():
                tid, n = row[0], int(row[1] or 0)
                if n >= 10:
                    out[tid] = "FULLY_CROSS_DEPENDENT"
                elif n <= 2:
                    out[tid] = "FULLY_STANDALONE"
                else:
                    out[tid] = "MODERATE_LINKAGE"
            # Tests with no dependency rows → standalone for this metric
            for tid in ids:
                if tid not in out:
                    out[tid] = "FULLY_STANDALONE"
    except Exception as e:
        logger.debug("linkage_profiles failed: %s", e)
    return out


def evidence_quality(match_types: List[str]) -> str:
    """Single label for how strongly the diff links to the test."""
    if "function_level" in match_types:
        return "CONFIRMED_FUNCTION"
    if "direct_file" in match_types or "direct_test_file" in match_types:
        return "CONFIRMED_FILE"
    if "exact" in match_types:
        return "CONFIRMED_SYMBOL"
    if "integration" in match_types:
        return "INTEGRATION_SCOPE"
    if "module" in match_types:
        return "BROAD_MODULE"
    if "semantic" in match_types:
        return "SEMANTIC_SUPPLEMENT"
    return "UNKNOWN"


def false_positive_risk(
    match_types: List[str],
    scenario_tags: List[str],
    semantic_only_no_overlap: bool,
) -> str:
    if semantic_only_no_overlap:
        return "HIGH"
    if "semantic" in match_types and "exact" not in match_types and "function_level" not in match_types:
        if "module" in match_types:
            return "MEDIUM"
        return "MEDIUM_HIGH"
    if "module" in match_types and "exact" not in match_types and "function_level" not in match_types:
        if "MICRO_GUARD_HOTFIX" in scenario_tags:
            return "MEDIUM_HIGH"
        return "MEDIUM"
    if "exact" in match_types or "function_level" in match_types:
        return "LOW"
    return "LOW_MEDIUM"


def false_negative_hints(scenario_tags: List[str], dead_zone_count: int) -> List[str]:
    hints = []
    if "MAXIMUM_BLAST_RADIUS" in scenario_tags:
        hints.append(
            "FN_RISK: Large change set — run area suites or full test job in addition to listed tests."
        )
    if dead_zone_count > 0:
        hints.append(
            f"FN_RISK: {dead_zone_count} changed symbol(s) have no mapped tests — manual review."
        )
    if "MIXED_LANGUAGE_DIFF" in scenario_tags:
        hints.append(
            "FN_RISK: Verify each language's test pipeline was indexed for this repo."
        )
    return hints


def build_impact_intelligence(
    conn,
    schema: str,
    parsed_diff: Dict[str, Any],
    search_queries: Dict[str, Any],
    diff_content: str,
    all_tests: List[Dict[str, Any]],
    match_details: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Full bundle for API: scenarios + dead zones + per-test FP/FN annotations.
    """
    shape = classify_diff_scenarios(parsed_diff, search_queries, diff_content or "")
    exact = list(search_queries.get("exact_matches") or [])
    dead = find_dead_zone_symbols(conn, schema, exact)
    tids = [t.get("test_id") for t in all_tests if t.get("test_id")]
    linkage = linkage_profiles_for_tests(conn, schema, tids)

    per_test: Dict[str, Dict[str, Any]] = {}
    for t in all_tests:
        tid = t.get("test_id")
        if not tid:
            continue
        md = match_details.get(tid, [])
        mtypes = [m.get("type", "") for m in md]
        sem_only = t.get("semantic_only_no_overlap", False)
        per_test[tid] = {
            "test_linkage_profile": linkage.get(tid, "UNKNOWN"),
            "evidence_quality": evidence_quality(mtypes),
            "false_positive_risk": false_positive_risk(
                mtypes, shape["scenario_tags"], sem_only
            ),
        }

    return {
        **shape,
        "dead_zones": dead,
        "dead_zone_count": len(dead),
        "false_negative_hints": false_negative_hints(
            shape["scenario_tags"], len(dead)
        ),
        "per_test_intelligence": per_test,
    }


def merge_per_test_intelligence(
    all_tests: List[Dict[str, Any]], intelligence: Dict[str, Any]
) -> None:
    """Mutate all_tests entries in place."""
    pt = intelligence.get("per_test_intelligence") or {}
    for t in all_tests:
        tid = t.get("test_id")
        if tid and tid in pt:
            t.update(pt[tid])
