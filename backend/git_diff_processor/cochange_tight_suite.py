"""
Tight co-change suite selection.

When a diff touches BOTH production code AND a test file in the same commit,
semantic search often returns false positives (other files that mention similar
words). The correct minimal set is usually: every test living in the modified
test file(s) — sibling describes in that file, not cross-repo semantic matches.

Scenario 5 (ApiConstants + api-navigation.feature.test.js): expect ~7 tests in
one file, not 14 scattered semantic hits.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TEST_PATH_HINT = re.compile(
    r"(\.test\.|\.spec\.|/__tests__/|/tests?/|test_repository[/\\]|\.feature\.test\.)",
    re.IGNORECASE,
)

_CODE_EXT = frozenset(
    {".js", ".ts", ".tsx", ".jsx", ".java", ".py", ".go", ".c", ".cpp", ".h", ".hpp"}
)


def is_likely_test_file(path: str) -> bool:
    if not path:
        return False
    p = path.replace("\\", "/")
    if _TEST_PATH_HINT.search(p):
        return True
    low = p.lower()
    return low.endswith(".test.js") or low.endswith(".spec.ts")


def is_likely_production_file(path: str) -> bool:
    if not path or is_likely_test_file(path):
        return False
    suf = Path(path).suffix.lower()
    return suf in _CODE_EXT


def tight_cochange_applies(changed_files: List[str]) -> bool:
    if not changed_files or len(changed_files) < 2:
        return False
    has_test = any(is_likely_test_file(f) for f in changed_files)
    has_prod = any(is_likely_production_file(f) for f in changed_files)
    return has_test and has_prod


def _basename(path: str) -> str:
    return Path(path.replace("\\", "/")).name


def _test_file_path_ilike_args(changed_test_path: str) -> Tuple[str, tuple]:
    """
    Build ILIKE disjuncts so we prefer path-tail matches over basename-only
    (reduces false positives when two suites share the same filename).
    """
    bn = _basename(changed_test_path)
    norm = changed_test_path.replace("\\", "/")
    likes: List[str] = []
    if bn:
        likes.extend((f"%/{bn}", f"%\\{bn}", f"%{bn}"))
    if "/" in norm:
        tail2 = "/".join(norm.split("/")[-2:])
        if tail2 and tail2 != bn:
            likes.append(f"%{tail2}%")
            bslash = tail2.replace("/", "\\")
            if bslash != tail2:
                likes.append(f"%{bslash}%")
    ordered: List[str] = []
    seen: set = set()
    for x in likes:
        if x and x not in seen:
            seen.add(x)
            ordered.append(x)
    if not ordered:
        return "", tuple()
    cond = " OR ".join(["file_path ILIKE %s"] * len(ordered))
    return cond, tuple(ordered)


def fetch_tests_in_changed_test_files(
    conn, schema: str, changed_files: List[str]
) -> List[Dict[str, Any]]:
    """test_registry rows for co-changed test files (path-tail aware)."""
    test_files = [f for f in changed_files if is_likely_test_file(f)]
    if not test_files:
        return []
    out: List[Dict[str, Any]] = []
    seen: set = set()
    with conn.cursor() as cur:
        for tf in test_files:
            cond, args = _test_file_path_ilike_args(tf)
            if not cond:
                continue
            cur.execute(
                f"""
                SELECT DISTINCT test_id, class_name, method_name, file_path, test_type
                FROM {schema}.test_registry
                WHERE ({cond})
                ORDER BY test_id
                """,
                args,
            )
            for row in cur.fetchall():
                tid = row[0]
                if tid in seen:
                    continue
                seen.add(tid)
                out.append(
                    {
                        "test_id": tid,
                        "class_name": row[1],
                        "method_name": row[2],
                        "file_path": row[3],
                        "test_type": row[4],
                    }
                )
    return out


def fetch_tests_in_changed_test_files_multi(
    conn, schemas: List[str], changed_files: List[str]
) -> List[Dict[str, Any]]:
    """Union suite rows across bound test-repo schemas (dedupe by test_id)."""
    clean = [s for s in schemas if s]
    if not clean:
        return []
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for sch in clean:
        for r in fetch_tests_in_changed_test_files(conn, sch, changed_files):
            tid = r.get("test_id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            row = dict(r)
            row["source_schema"] = sch
            out.append(row)
    return out


def apply_tight_cochanged_suite(
    conn,
    schema: str,
    changed_files: List[str],
    combined_results: Dict[str, Any],
    *,
    schemas: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    If prod+test co-change: replace combined test list with full suite from
    modified test file(s). Drops semantic false positives from other paths.
    """
    if os.getenv("DISABLE_TIGHT_COCHANGE_SUITE", "").lower() in ("1", "true", "yes"):
        return combined_results, None

    if not tight_cochange_applies(changed_files):
        return combined_results, None

    schema_list = [s for s in (schemas or []) if s] or [schema]
    if len(schema_list) > 1:
        suite_rows = fetch_tests_in_changed_test_files_multi(conn, schema_list, changed_files)
    else:
        suite_rows = fetch_tests_in_changed_test_files(conn, schema_list[0], changed_files)
    if not suite_rows:
        logger.info(
            "[COCHANGE] Tight mode eligible but no test_registry rows for basenames — skipping"
        )
        return combined_results, None

    allowed_ids = {r["test_id"] for r in suite_rows}
    existing = {t.get("test_id"): t for t in combined_results.get("tests", []) if t.get("test_id")}
    md = dict(combined_results.get("match_details") or {})

    new_tests: List[Dict[str, Any]] = []
    for r in suite_rows:
        tid = r["test_id"]
        if tid in existing:
            t = dict(existing[tid])
        else:
            t = {
                "test_id": tid,
                "class_name": r["class_name"],
                "method_name": r["method_name"],
                "test_file_path": r["file_path"],
                "file_path": r["file_path"],
                "test_type": r.get("test_type"),
            }
        lst = md.setdefault(tid, [])
        if not any(m.get("type") == "cochanged_test_suite" for m in lst):
            lst.append(
                {
                    "type": "cochanged_test_suite",
                    "confidence": "very_high",
                    "reason": "Modified test file + production file in same diff — suite-scoped selection",
                }
            )
        t["confidence_score"] = max(int(t.get("confidence_score") or 0), 82)
        t["is_ast_match"] = True
        t["is_semantic_match"] = False
        new_tests.append(t)

    # Drop match_details for tests no longer in the result
    md = {k: v for k, v in md.items() if k in allowed_ids}

    combined_results["tests"] = new_tests
    combined_results["total_tests"] = len(new_tests)
    combined_results["match_details"] = md

    meta = {
        "mode": "tight_cochanged_suite",
        "suite_file_basenames": list({_basename(f) for f in changed_files if is_likely_test_file(f)}),
        "tests_in_suite": len(new_tests),
        "dropped_cross_file_semantic": True,
    }
    logger.info(
        "[COCHANGE] Tight suite: %s test(s) in modified test file(s) %s",
        len(new_tests),
        meta["suite_file_basenames"],
    )
    return combined_results, meta
