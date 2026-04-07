"""Unit tests for test-selection remediation (schema merge, dead zone, co-change)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# backend/ on path
_backend = Path(__file__).resolve().parents[2]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from deterministic.db_connection import DB_SCHEMA  # noqa: E402
from git_diff_processor.cochange_tight_suite import (  # noqa: E402
    _test_file_path_ilike_args,
)
from git_diff_processor.diff_scenario_analysis import (  # noqa: E402
    _dead_zone_like_patterns,
    check_dead_zone_for_files_multi,
)
from git_diff_processor.process_diff_programmatic import (  # noqa: E402
    _merge_ast_results,
    _resolve_schema_list,
)


class SelectionRemediationTests(unittest.TestCase):
    def test_resolve_schema_list_prefers_schema_names(self):
        self.assertEqual(_resolve_schema_list("a", ["x", "y"]), ["x", "y"])
        self.assertEqual(_resolve_schema_list("only", None), ["only"])
        self.assertEqual(_resolve_schema_list(None, []), [DB_SCHEMA])
        self.assertEqual(_resolve_schema_list(None, None), [DB_SCHEMA])

    def test_merge_ast_results_dedupes_and_merges_details(self):
        base = _merge_ast_results(
            None,
            {
                "tests": [
                    {"test_id": "t1", "confidence_score": 50},
                ],
                "match_details": {"t1": [{"type": "exact"}]},
            },
            "schema_a",
        )
        merged = _merge_ast_results(
            base,
            {
                "tests": [
                    {"test_id": "t1", "confidence_score": 40},
                    {"test_id": "t2", "confidence_score": 60},
                ],
                "match_details": {
                    "t1": [{"type": "module"}],
                    "t2": [{"type": "function_level"}],
                },
            },
            "schema_b",
        )
        self.assertEqual(merged["total_tests"], 2)
        by_id = {t["test_id"]: t for t in merged["tests"]}
        self.assertEqual(by_id["t1"]["source_schema"], "schema_a")
        self.assertEqual(by_id["t2"]["source_schema"], "schema_b")
        self.assertEqual(len(merged["match_details"]["t1"]), 2)

    def test_dead_zone_generic_stem_stricter_patterns(self):
        p = _dead_zone_like_patterns("util", "src/helpers/util.ts")
        self.assertNotIn("%util%", p)
        self.assertTrue(any("util." in x or x.endswith("%util") for x in p))

    def test_dead_zone_strong_stem_includes_substring_and_tail(self):
        p = _dead_zone_like_patterns("signUpFormHook", "src/features/signUpFormHook.ts")
        self.assertTrue(any("%signUpFormHook%" == x for x in p))
        self.assertTrue(any("features/signUpFormHook.ts" in x for x in p))

    def test_check_dead_zone_multi_no_cursor(self):
        class _Dummy:
            def cursor(self):
                raise RuntimeError("should not connect")

        r = check_dead_zone_for_files_multi(_Dummy(), [], ["a.py"], {})
        self.assertFalse(r["checked"])

    def test_cochange_path_ilike_prefers_tail(self):
        cond, args = _test_file_path_ilike_args("e2e/foo/api-navigation.feature.test.js")
        self.assertIn("ILIKE", cond)
        self.assertTrue(any("api-navigation.feature.test.js" in str(a) for a in args))
        self.assertTrue(any("foo/api-navigation" in str(a) for a in args))


if __name__ == "__main__":
    unittest.main()
