"""
Scenario accuracy test runner.

Runs Scenario A and Scenario B against the live system and scores
Precision / Recall / F1 against a hardcoded expected-output ground truth.

Usage (from backend/):
    python scripts/test_scenarios.py                # run both scenarios
    python scripts/test_scenarios.py --scenario A   # only Scenario A
    python scripts/test_scenarios.py --scenario B   # only Scenario B
    python scripts/test_scenarios.py --no-semantic  # AST-only (diagnostic)

Environment:
    The script reads DB / LLM config from the same .env file the server uses.
    Set TEST_REPO_ID / DB_SCHEMA as usual.
"""

import sys
import asyncio
import argparse
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# ── path bootstrap ──────────────────────────────────────────────────────────
_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

# Load .env from project root (one level above backend/)
_env_file = _backend.parent / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)
# ────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
#  SCENARIO DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

# ---------------------------------------------------------------------------
# Scenario A — checkWhiteSpace whitespace-detection change
# ---------------------------------------------------------------------------
SCENARIO_A_DIFF = """\
diff --git a/src/helpers/utilities.js b/src/helpers/utilities.js
index abc1234..def5678 100644
--- a/src/helpers/utilities.js
+++ b/src/helpers/utilities.js
@@ -10,7 +10,8 @@ export function checkNull(value) {
 }
 
 export function checkWhiteSpace(str) {
-  return /\\s/.test(str);
+  if (typeof str !== 'string') return false;
+  return /\\s/.test(str);
 }
"""

# Expected test names for Scenario A
# Key = priority label, value = list of substrings that uniquely identify each test
SCENARIO_A_EXPECTED = {
    "CRITICAL": [
        "checkWhiteSpace > returns true for a string that contains a space",
        "checkWhiteSpace > returns false for a string with no whitespace",
    ],
    "HIGH": [
        "checkNull > returns the original value when it is defined and non-null",
        "checkNull > returns an empty string when the value is null",
        "checkArray > returns an empty array when the input is null",
        "checkArray > returns the original array when it contains items",
        "getTimes > correctly parses 3661 seconds into 1h 01m 01s",
        "getTimes > returns 0 hours when the duration is under 3600 seconds",
        "getProgressWidth > calculates 50% when value is half of max",
        "getProgressWidth > returns 0 when the value argument is missing or falsy",
        "capitalizeFirstLetter with checkWhiteSpace > capitalizes the first letter of each word in a multi-word string",
        "capitalizeFirstLetter with checkWhiteSpace > capitalizes a single word correctly without whitespace branch",
        "capitalizeFirstLetter with checkWhiteSpace > returns undefined when given a non-string truthy value after type guard fix",
        "isUserLoggedIn",
        "updateNewTokenDetails",
        "generateCardNumber",
    ],
    "SKIP": [
        # These are exact test-file names whose tests should NOT appear
        "regex.constants.test.js",
        "payment-state.cross.test.js",
        "user-profile.feature.test.js",
        "favourites-watchlist.feature.test.js",
        "api-navigation.feature.test.js",
    ],
}

# ---------------------------------------------------------------------------
# Scenario B — paymentReducer RESETPAYMENT new action
# ---------------------------------------------------------------------------
SCENARIO_B_DIFF = """\
diff --git a/src/reducer/paymentReducer.js b/src/reducer/paymentReducer.js
index 1111111..2222222 100644
--- a/src/reducer/paymentReducer.js
+++ b/src/reducer/paymentReducer.js
@@ -1,6 +1,7 @@
 export const paymentActions = {
   UPDATEALLCARDDETAILS: 'UPDATE_STORED_USER_ALL_CARD_DETAILS',
   UPDATEPAYMENTPLANDETAILS: 'UPDATE_PAYMENT_PLAN_DETAILS',
+  RESETPAYMENT: 'RESET_PAYMENT_STATE',
   CLEARCARDS: 'CLEAR_USER_CARDS',
 }
 
@@ -23,6 +24,10 @@ function paymentReducer(state = initialState, action) {
         ...state,
         paymentPlantDetails: action.payload
       }
+    case paymentActions.RESETPAYMENT:
+      return {
+        ...initialState,
+      }
     case paymentActions.CLEARCARDS:
       return {
         ...state,
"""

SCENARIO_B_EXPECTED = {
    "CRITICAL": [
        "updateUserCards action dispatched into paymentReducer > populates userCards in state after dispatch",
        "updateUserCards action dispatched into paymentReducer > sets cardsFetched to true when cards are provided",
        "updateUserCards action dispatched into paymentReducer > clears userCards when dispatched with an empty array",
        "updatePaymentPlanDetails action and paymentReducer > stores the subscription plan object in paymentPlantDetails",
        "updatePaymentPlanDetails action and paymentReducer > does not mutate userCards when a plan update is dispatched",
        "paymentActions.CLEARCARDS resets payment state > resets userCards to an empty array",
        "paymentActions.CLEARCARDS resets payment state > resets cardsFetched back to false after clearing",
        "CARD_NUMBER_REGEX validates checkout flow input > accepts a standard 19-character card number with spaces",
        "CARD_NUMBER_REGEX validates checkout flow input > rejects a card number shorter than 17 characters",
        "CARD_NUMBER_REGEX validates checkout flow input > rejects a card number that contains letters",
    ],
    "HIGH": [
        "storageKeys align with payment flow expectations > storageKeys.stripePaymentDetails equals STRIPEPAYMENTDETAILS",
        "storageKeys align with payment flow expectations > storageKeys.token equals TOKEN",
    ],
    "SKIP": [
        "regex.constants.test.js",
        "utilities.pure.test.js",
        "auth-storage.cross.test.js",
        "user-profile.feature.test.js",
        "favourites-watchlist.feature.test.js",
        "api-navigation.feature.test.js",
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
#  SCORING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScenarioResult:
    name: str
    selected_tests: List[Dict] = field(default_factory=list)
    # precision / recall categories
    true_positive: List[str] = field(default_factory=list)    # expected & selected
    false_positive: List[str] = field(default_factory=list)   # selected but should SKIP
    false_negative: List[str] = field(default_factory=list)   # expected but NOT selected
    unexpected_from_skip_file: List[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        tp = len(self.true_positive)
        fp = len(self.false_positive)
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        tp = len(self.true_positive)
        fn = len(self.false_negative)
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def _method_matches(method_name: str, substr: str) -> bool:
    """Case-insensitive substring match on method_name."""
    return substr.lower() in method_name.lower()


def _file_path_contains(file_path: str, skip_hint: str) -> bool:
    """True if the test file path contains the given hint (case-insensitive)."""
    return skip_hint.lower() in (file_path or "").lower()


def score_results(
    scenario_name: str,
    selected: List[Dict],
    expected: Dict[str, List[str]],
) -> ScenarioResult:
    result = ScenarioResult(name=scenario_name, selected_tests=selected)

    expected_critical = expected.get("CRITICAL", [])
    expected_high = expected.get("HIGH", [])
    expected_any = expected_critical + expected_high
    skip_file_hints = expected.get("SKIP", [])

    # Build fast lookup: for each expected test, whether it was found
    found_expected: Dict[str, bool] = {e: False for e in expected_any}

    for test in selected:
        method = test.get("method_name", "") or ""
        file_path = test.get("test_file_path", "") or ""

        # Check if this test is from a SKIP file
        in_skip_file = any(_file_path_contains(file_path, hint) for hint in skip_file_hints)

        # Check if it matches any expected test
        matched_expected = [e for e in expected_any if _method_matches(method, e)]

        if matched_expected:
            for m in matched_expected:
                found_expected[m] = True
            result.true_positive.append(method)
        elif in_skip_file:
            result.false_positive.append(method)
            result.unexpected_from_skip_file.append(f"{method}  [{Path(file_path).name}]")
        # else: selected but not in expected AND not in SKIP — neutral (e.g. borderline)

    # False negatives: expected but not found
    for expected_name, was_found in found_expected.items():
        if not was_found:
            result.false_negative.append(expected_name)

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  DISPLAY
# ══════════════════════════════════════════════════════════════════════════════

BOLD  = "\033[1m"
RED   = "\033[31m"
GREEN = "\033[32m"
YELLOW= "\033[33m"
CYAN  = "\033[36m"
DIM   = "\033[2m"
RESET = "\033[0m"

def _c(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}"


def print_run_header(label: str) -> None:
    width = 72
    print()
    print("═" * width)
    print(f"  {BOLD}{label}{RESET}")
    print("═" * width)


def print_selected_table(tests: List[Dict]) -> None:
    print(f"\n  {BOLD}Selected Tests ({len(tests)}){RESET}")
    hdr = f"  {'Test ID':<12} {'Match':<8} {'Sim':>6}  {'Conf':<8}  Test Name"
    print(_c(hdr, DIM))
    print(_c("  " + "─" * 70, DIM))
    for t in tests:
        tid   = (t.get("test_id") or "")[:11]
        mtype = (t.get("match_type") or "")[:7]
        sim   = t.get("similarity")
        sim_s = f"{sim*100:.1f}%" if sim else "   -  "
        conf  = (t.get("confidence") or "")[:7]
        name  = (t.get("method_name") or "")[:60]
        conf_col = GREEN if conf == "high" else YELLOW if conf == "medium" else DIM
        print(f"  {tid:<12} {mtype:<8} {sim_s:>6}  {conf_col}{conf:<8}{RESET}  {name}")


def print_score_report(r: ScenarioResult) -> None:
    total_expected = len(r.true_positive) + len(r.false_negative)
    print(f"\n  {BOLD}── Score: {r.name} ──────────────────────────────{RESET}")
    print(f"  {'Precision':<20} {_c(f'{r.precision*100:.1f}%', GREEN if r.precision >= 0.8 else YELLOW if r.precision >= 0.5 else RED)}")
    print(f"  {'Recall':<20} {_c(f'{r.recall*100:.1f}%', GREEN if r.recall >= 0.8 else YELLOW if r.recall >= 0.5 else RED)}")
    print(f"  {'F1':<20} {_c(f'{r.f1*100:.1f}%', GREEN if r.f1 >= 0.8 else YELLOW if r.f1 >= 0.5 else RED)}")
    print(f"  {'True positives':<20} {_c(str(len(r.true_positive)), GREEN)} / {total_expected} expected")
    print(f"  {'False positives':<20} {_c(str(len(r.false_positive)), RED if r.false_positive else GREEN)} (tests from SKIP files)")
    print(f"  {'False negatives':<20} {_c(str(len(r.false_negative)), RED if r.false_negative else GREEN)} (expected but missed)")

    if r.false_positive:
        print(f"\n  {RED}False Positives (should NOT be selected):{RESET}")
        for fp in r.false_positive:
            print(f"    ✗  {fp[:80]}")

    if r.unexpected_from_skip_file:
        print(f"\n  {RED}  From SKIP files:{RESET}")
        for item in r.unexpected_from_skip_file:
            print(f"      {item}")

    if r.false_negative:
        print(f"\n  {YELLOW}False Negatives (should be selected but weren't):{RESET}")
        for fn in r.false_negative:
            prio = "CRITICAL" if fn in (
                SCENARIO_A_EXPECTED.get("CRITICAL", []) + SCENARIO_B_EXPECTED.get("CRITICAL", [])
            ) else "HIGH"
            print(f"    ✗  [{prio}] {fn[:80]}")

    if not r.false_positive and not r.false_negative:
        print(f"\n  {GREEN}✓ Perfect selection — no FP, no FN{RESET}")


def print_comparison(before: ScenarioResult, after: ScenarioResult) -> None:
    print(f"\n  {BOLD}── Before vs After ─────────────────────────────{RESET}")
    metrics = [
        ("Precision", before.precision, after.precision),
        ("Recall",    before.recall,    after.recall),
        ("F1",        before.f1,        after.f1),
    ]
    for label, bv, av in metrics:
        delta = av - bv
        arrow = _c(f"▲ +{delta*100:.1f}%", GREEN) if delta > 0.005 else \
                _c(f"▼ {delta*100:.1f}%", RED) if delta < -0.005 else \
                _c("  ≈ no change", DIM)
        print(f"  {label:<14} {bv*100:.1f}% → {av*100:.1f}%   {arrow}")


# ══════════════════════════════════════════════════════════════════════════════
#  RUNNER
# ══════════════════════════════════════════════════════════════════════════════

async def run_scenario(
    diff: str,
    label: str,
    use_semantic: bool = True,
    schema: Optional[str] = None,
    test_repo_id: Optional[str] = None,
) -> List[Dict]:
    from git_diff_processor.process_diff_programmatic import process_diff_and_select_tests

    schema = schema or os.getenv("DB_SCHEMA", "planon1")
    test_repo_id = test_repo_id or os.getenv("TEST_REPO_ID") or None

    print(f"\n  {DIM}Running {label}  (schema={schema}, semantic={'on' if use_semantic else 'off'}) …{RESET}")
    result = await process_diff_and_select_tests(
        diff_content=diff,
        use_semantic=use_semantic,
        schema_name=schema,
        test_repo_id=test_repo_id,
    )
    tests = result.get("tests", [])
    print(f"  {DIM}→ {len(tests)} test(s) returned{RESET}")
    return tests


async def main(args: argparse.Namespace) -> None:
    schema     = args.schema or os.getenv("DB_SCHEMA", "planon1")
    repo_id    = args.repo_id or os.getenv("TEST_REPO_ID") or None
    use_sem    = not args.no_semantic
    compare    = args.compare   # second run stored in memory from --compare file

    run_a = args.scenario in (None, "A", "a")
    run_b = args.scenario in (None, "B", "b")

    # ── optionally load a previously saved JSON baseline ────────────────────
    baseline: Dict[str, List[Dict]] = {}
    if args.load_baseline and Path(args.load_baseline).exists():
        with open(args.load_baseline) as f:
            baseline = json.load(f)
        print(_c(f"\n  Loaded baseline from {args.load_baseline}", CYAN))

    # ── run scenarios ────────────────────────────────────────────────────────
    results_a: List[Dict] = []
    results_b: List[Dict] = []

    if run_a:
        print_run_header("SCENARIO A — checkWhiteSpace type-guard addition  (src/helpers/utilities.js)")
        results_a = await run_scenario(
            SCENARIO_A_DIFF, "Scenario A", use_semantic=use_sem,
            schema=schema, test_repo_id=repo_id,
        )
        print_selected_table(results_a)

    if run_b:
        print_run_header("SCENARIO B — paymentReducer RESETPAYMENT new action  (src/reducer/paymentReducer.js)")
        results_b = await run_scenario(
            SCENARIO_B_DIFF, "Scenario B", use_semantic=use_sem,
            schema=schema, test_repo_id=repo_id,
        )
        print_selected_table(results_b)

    # ── save current run as baseline if requested ────────────────────────────
    if args.save_baseline:
        payload = {}
        if run_a:
            payload["A"] = results_a
        if run_b:
            payload["B"] = results_b
        Path(args.save_baseline).write_text(json.dumps(payload, indent=2))
        print(_c(f"\n  Saved baseline → {args.save_baseline}", CYAN))

    # ── score & report ───────────────────────────────────────────────────────
    print()
    print("═" * 72)
    print(f"  {BOLD}SCORE REPORT{RESET}")
    print("═" * 72)

    if run_a:
        score_a = score_results("Scenario A", results_a, SCENARIO_A_EXPECTED)
        print_score_report(score_a)

        if "A" in baseline:
            score_a_base = score_results("Scenario A (baseline)", baseline["A"], SCENARIO_A_EXPECTED)
            print_comparison(score_a_base, score_a)

    if run_b:
        score_b = score_results("Scenario B", results_b, SCENARIO_B_EXPECTED)
        print_score_report(score_b)

        if "B" in baseline:
            score_b_base = score_results("Scenario B (baseline)", baseline["B"], SCENARIO_B_EXPECTED)
            print_comparison(score_b_base, score_b)

    # ── overall summary ───────────────────────────────────────────────────────
    if run_a and run_b:
        avg_f1 = (score_a.f1 + score_b.f1) / 2
        colour = GREEN if avg_f1 >= 0.8 else YELLOW if avg_f1 >= 0.5 else RED
        print()
        print("═" * 72)
        print(f"  {BOLD}OVERALL  avg-F1 = {_c(f'{avg_f1*100:.1f}%', colour)}{RESET}")
        print("═" * 72)
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Scenario A/B accuracy tests against the live system."
    )
    parser.add_argument(
        "--scenario", choices=["A", "a", "B", "b"],
        help="Run only one scenario (default: both)",
    )
    parser.add_argument(
        "--no-semantic", action="store_true",
        help="Disable semantic search (AST-only run for comparison)",
    )
    parser.add_argument(
        "--schema", default=None,
        help="DB schema to use (default: DB_SCHEMA env var or 'planon1')",
    )
    parser.add_argument(
        "--repo-id", default=None,
        help="Pinecone test_repo_id (default: TEST_REPO_ID env var)",
    )
    parser.add_argument(
        "--save-baseline", metavar="FILE",
        help="Save current run results as a JSON baseline for future --load-baseline comparisons",
    )
    parser.add_argument(
        "--load-baseline", metavar="FILE",
        help="Load a previously saved baseline and print before/after comparison",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="(alias hint) use --save-baseline / --load-baseline for before/after workflow",
    )

    args = parser.parse_args()
    asyncio.run(main(args))
