# Entire Process — Test Selection System

A beginner-friendly guide covering how the system works, why it sometimes gets it wrong, how AST interacts with diffs, what is stored in each database, and all fixes applied.

---

## Table of Contents

1. [Big Picture — What the System Does](#1-big-picture)
2. [How AST Works With a Git Diff](#2-how-ast-works-with-a-git-diff)
3. [What the Diff Parser Extracts (and What It Misses)](#3-what-the-diff-parser-extracts)
4. [What Is Stored in PostgreSQL](#4-what-is-stored-in-postgresql)
5. [What Is Stored in Pinecone (Vector DB)](#5-what-is-stored-in-pinecone-vector-db)
6. [False Positives — Why Wrong Tests Get Selected](#6-false-positives)
7. [False Negatives — Why Correct Tests Get Missed](#7-false-negatives)
8. [Why AST Fails Sometimes](#8-why-ast-fails-sometimes)
9. [Confidence Score — How It Is Calculated](#9-confidence-score)
10. [Full Execution Flow (End to End)](#10-full-execution-flow)
11. [All Fixes Applied (Chronological)](#11-all-fixes-applied)

---

## 1. Big Picture

**Simple Analogy:**
Think of the system like a librarian who finds "affected textbooks" when one chapter changes. The librarian uses **two methods**:

1. **Card catalog (AST / PostgreSQL)** — looks up which tests are structurally linked to the changed code in a database.
2. **Reading covers for similarity (Semantic / Pinecone)** — uses AI embeddings to find tests that sound like they relate to the change.

Both methods can sometimes pick the wrong books or miss the right ones. The system merges both results and applies a confidence score to decide the final selection.

**Key principle:** The system works WITHOUT the production codebase. It only needs:
- The **git diff** (what changed)
- The **test repository** (all test files, analyzed once)

---

## 2. How AST Works With a Git Diff

### Step-by-Step

```
Git diff arrives
      ↓
STEP 1 — Parse the diff (two paths depending on format)

  Standard path  ("diff --git a/... b/..." format):
  • Reads file headers, hunk headers, +/- lines, context lines
  • Extracts: changed files, methods, classes, constants
  • Pre-change context scan: reads context lines (space-prefix) BEFORE
    the first +/- line to find the real changed function

  Headerless path ("Changed Files:" format — used by the UI):
  • No diff --git header; file list provided separately
  • Reads hunk headers (@@ lines) + +/- lines + context lines
  • Same pre-change context scan applied (added fix)
  • Tracks changed line ranges per method
      ↓
STEP 2 — Build search queries
  • Module stems:   ['utilities', 'helpers', 'helpers.utilities']
  • Exact symbols:  ['checkWhiteSpace', 'capitalizeFirstLetter']
  • Changed line ranges: [{method: 'checkWhiteSpace', start: 174, end: 174}]
  • All combined into a lookup list for PostgreSQL
      ↓
STEP 3 — Query PostgreSQL (5 Strategies, each broader than the last)

  Strategy 0 — Function-level mapping (strongest)
    Question: "Which tests directly CALL checkWhiteSpace()?"
    Table:    test_function_mapping
    Signal:   Strongest — the test literally invokes the changed function

  Strategy 2 — Describe / class label match
    Question: "Which test suites are NAMED after checkWhiteSpace?"
    Table:    reverse_index (production_class column, describe_label type)
    Signal:   Strong — test suite is explicitly about this function

  Strategy 3 — Module pattern match
    Question: "Which tests import from 'utilities' by module name?"
    Table:    reverse_index (normalized_import type)
    Signal:   Medium — test uses this module

  Strategy 4 — File stem match (broader)
    Question: "Which test FILES are named after utilities?"
    Table:    test_registry (file_path ILIKE '%utilities%.test%')
    Signal:   Medium — test file is dedicated to the changed module

  Strategy 4a — Co-location expansion (weakest)
    Question: "Are there other tests in the SAME TEST FILE as already-found tests?"
    Source:   test_registry (file_path grouping)
    Signal:   Weakest — sibling tests in the same file, included defensively
    Gate:     If ALL AST evidence is only co-location AND there is NO semantic
              match → the test is dropped (co-location-only gate)
      ↓
STEP 4 — Semantic search (runs in parallel with AST)
  • ENTIRE raw diff sent to LLM for plain-English summary
  • Summary rewritten into N query variations by LLM
  • Each variation → Pinecone vector search
  • Top results returned with similarity scores
      ↓
STEP 5 — Merge AST + Semantic results
  • Tests found by both = "Both" (strongest)
  • Tests found only by AST = "AST Only"
  • Tests found only by Semantic = "Semantic Only"
      ↓
STEP 6 — Score + Filter
  • Composite confidence score calculated (see Section 9)
  • Tests below the threshold are dropped
  • Remaining tests are ranked and returned
```

---

## 3. What the Diff Parser Extracts

The diff has TWO pipelines reading it — AST (precise but narrow) and Semantic (full but fuzzy).

### AST Pipeline — What It Extracts vs. Misses

| Diff content | AST uses it? | How |
|---|---|---|
| Changed file path | ✅ Yes | Module stems: `utilities`, `helpers`, `helpers.utilities` |
| Hunk header `@@ ... @@ export function getScreenNumber` | ✅ Yes (as pending, may be overridden) | Deferred until first +/- line seen |
| Context line ` export function checkWhiteSpace(string) {` | ✅ Yes (fix applied) | Pre-change context scan overrides hunk header |
| Added line `+  if (string === null ...)` | ✅ Partially | Extracts function/class name only if declared |
| Deleted line `-  return ...` | ✅ Partially | Same as added lines |
| `+ export const MY_REGEX = ...` | ✅ Yes | UPPER_CASE constants on `+` lines extracted |
| `+ class UtilityHelper {` | ✅ Yes | Class name extracted |
| Changed line numbers `@@ -171,8 +171,9` | ✅ Yes (new) | Stored as `changed_line_ranges` per method |
| Deleted/renamed symbol detection | ✅ Yes | `extract_deleted_added_renamed_symbols()` |
| Variable names inside function body | ❌ No | Only function/class names are extracted |
| Code comments `// fix null crash` | ❌ No | Ignored by parser |
| String literals `"Invalid input"` | ❌ No | Not extracted |
| TypeScript types `: string \| null` | ❌ No | Not extracted |
| New imports added in the diff | ❌ No | Classified as `import_only`, not tracked |
| Function parameters | ❌ No | Not extracted |
| Condition logic (`null`, `undefined`) | ❌ No | Not extracted |

### Semantic Pipeline — What It Uses

The semantic pipeline reads the **ENTIRE raw diff** (no line-by-line parsing):

```
Full diff text → LLM summarizer → plain-English summary
                                      ↓
                               Query rewriter (3 variations)
                                      ↓
                               Pinecone vector search
```

The LLM prompt explicitly asks it to:
- Name every changed **file path** exactly as written
- List **function names, constants, exports** that changed
- Name **dependencies referenced in the diff** (imports, symbols)
- Avoid vague descriptions like "auth layer" without naming real identifiers

So things AST misses (variable names, condition logic, comments, types) **CAN** influence semantic search because the LLM reads and summarizes the full text.

**What semantic can miss:**
- Very large diffs truncated by `DIFF_SUMMARY_MAX_CHARS` env var
- LLM generalising ("validation logic") instead of naming exact symbols
- Vocabulary mismatch between diff terms and test names

---

## 4. What Is Stored in PostgreSQL

PostgreSQL stores **structural / relational data** — facts about how tests and production code are connected. It is populated by running the `RepoAnalyzer` on the test repository.

### Tables

| Table | What it stores | Example row |
|---|---|---|
| `test_registry` | Every test that exists — id, name, file, type | `test_0072`, `checkWhiteSpace > returns false`, `utilities.pure.test.js`, `unit` |
| `reverse_index` | "This production module/class → these tests depend on it" | `production_class='utilities'` → tests `0068, 0069, 0070, 0071, 0072, 0073` |
| `test_function_mapping` | "This test calls this specific function from this module" | `test_0072` calls `checkWhiteSpace` from module `utilities` |
| `test_metadata` | Extra info: tags, markers, async flag, fixtures | `test_0072` is `unit` type, synchronous |

### How the Data Gets In

1. `RepoAnalyzer` scans all test files in the test repository.
2. For JavaScript/TypeScript, it reads import statements:
   ```js
   import { checkWhiteSpace } from '../helpers/utilities'
   ```
   - Stores raw path: `production_class = '../helpers/utilities'`
   - **Also stores normalized stem** (fix applied): `production_class = 'utilities'`
   - This dual storage ensures both lookup styles work.
3. It reads `describe('checkWhiteSpace', ...)` labels → stores as a `production_class` entry so Strategy 2 can find it via describe-label matching.
4. It reads actual function calls inside test bodies → stores in `test_function_mapping`.

### Import Path Mismatch — Why Dual Storage Is Needed

**Before the fix**, only the raw import path was stored:

```
DB:     production_class = '../helpers/utilities'
Search: WHERE production_class = 'utilities'     → NO MATCH (exact)
        WHERE production_class LIKE 'utilities.%' → NO MATCH (no dot prefix)
        WHERE production_class LIKE '%.utilities' → NO MATCH (slash not dot)
```

**After the fix**, both raw AND normalized stem are stored:
```
DB:     production_class = '../helpers/utilities'  (old row kept)
        production_class = 'utilities'              (new normalized row)
Search: WHERE production_class = 'utilities'        → MATCH ✓
```

**Important:** Re-analysis must be run after this fix for new rows to appear in the DB.

### Static Nature of the Database

The database reflects the test repository **at the time of the last analysis run**. If new tests are added, import paths change, or the analyzer code is updated → re-run `RepoAnalyzer`.

---

## 5. What Is Stored in Pinecone (Vector DB)

Pinecone stores **AI-generated vector embeddings** — numerical representations of what each test "means" in language space.

### Chunking Strategy — "Test-Boundary Chunking"

The system does **NOT** embed entire test files. It splits at individual test boundaries:

```
utilities.pure.test.js  (whole file, 300 lines)
          ↓ split at each it(...) / test(...) block
Chunk 1:  it('returns true for a string that contains a space', ...)   → lines 5–14
Chunk 2:  it('returns false for a string with no whitespace', ...)     → lines 15–24
Chunk 3:  it('returns an empty string when the value is null', ...)    → lines 25–36
...
```

**Why one chunk per test?** So Pinecone returns specific test IDs, not "the utilities file in general."

**Fallback strategy (when no test boundaries found):**
1. Method-boundary chunking — splits at function declarations
2. Character-based splitting — max 2000 characters per chunk

### What Text Is Embedded Per Chunk

```
Test: returns false for a string with no whitespace
Component: checkWhiteSpace
Language: javascript
Test code: it('returns false for a string with no whitespace', () => {
  expect(checkWhiteSpace('hello')).toBe(false);
});
```

This combined text is converted into a **768-dimensional vector** (list of 768 numbers) by the embedding model (Ollama / OpenAI).

### What Is Stored in Each Pinecone Record

| Field | Value |
|---|---|
| Vector ID | `test_0072` |
| Vector | `[0.12, -0.34, 0.87, ...]` (768 numbers) |
| Metadata: test_id | `test_0072` |
| Metadata: class_name | `checkWhiteSpace` |
| Metadata: method_name | `returns false for a string with no whitespace` |
| Metadata: file_path | `test_repository/standalone/utilities.pure.test.js` |
| Metadata: test_repo_id | `test_repo_261b672a` |

---

## 6. False Positives

False positives = tests that are **selected but should NOT run**.

### Reason 1 — Co-location Expansion Drags in Siblings (Strategy 4a)

When `checkWhiteSpace` tests are found in `auth-storage.cross.test.js`, Strategy 4a grabs ALL other tests in that file — including `validateEmailOrUsername` which has no connection to `checkWhiteSpace`.

- **Why it happens:** The test FILE imports `utilities.js` (for the `capitalizeFirstLetter` tests), so ALL tests in that file get linked to the module change. Without per-test source tracking, the system cannot distinguish which individual tests use which imports.
- **Fix applied (partial):** Co-location-only gate — if a test's ONLY AST evidence is `colocated_in_same_file` AND it has NO semantic match at all → it is dropped. This handles runs where `validateEmailOrUsername` is purely co-located with no semantic confirmation.
- **Remaining limitation:** When `validateEmailOrUsername` also appears in Pinecone results (e.g. 38% similarity due to vocabulary overlap with "null"), the composite score decides. At 38% similarity with AST co-location, the score may still reach the threshold.

### Reason 2 — Vocabulary Overlap in Semantic Search

Words like `"null"`, `"undefined"`, `"returns false"`, `"guard"` appear in many unrelated test names. Example:
```
toastReducer > resets showToast to null when null is dispatched
```
This got a 41% similarity score just because the diff also mentions `"null"`.

- **Fix applied:** Raised similarity threshold from 30% to 35%, and added a 40% composite confidence floor for semantic-only tests. LLM score = 0.0 is now explicitly treated as irrelevant (not as "has a score").

### Reason 3 — Wrong Function Extracted From Diff

The git diff hunk header `@@ -171,8 @@ export function getScreenNumber` shows the **enclosing** function — but the actual change is 3 lines lower inside `checkWhiteSpace`.

- **Why it happens:** Git's `@@` header format shows the nearest function ABOVE the change, not the one being changed.
- **Fix applied (standard path):** Pre-change context scanning. Before the first `+/-` line, the parser scans context lines for function declarations. The last one found overrides the hunk header.
- **Fix applied (headerless path):** Same pre-change context scan added to the headerless diff path used by the UI.

### Reason 4 — LLM Score 0.0 Treated as "Has LLM Score"

`llm_score = 0.0` means "LLM says irrelevant." But the filter checked `if llm_score is not None` — `0.0 is not None` is `True` — so irrelevant tests bypassed the 40% threshold.

- **Fix applied:** Changed to `if llm_score > 0`. Only positive scores count as LLM confirmation.

---

## 7. False Negatives

False negatives = tests that **should run but were NOT selected**.

### Reason 1 — Context Lines Ignored in Headerless Diff Format

The UI sends diffs in "Changed Files:" format (no `diff --git` header). The original headerless parser only processed `+` and `-` lines — it skipped all ` ` (space-prefixed) context lines entirely.

```
 export function checkWhiteSpace(string) {   ← context line (IGNORED before fix)
+  if (string === null || string === undefined) return false;
```

So `checkWhiteSpace` was never extracted → tests depending on it were never found by AST.

- **Fix applied:** Pre-change context scanning added to the headerless path. Before the first `+/-` in each hunk, the parser scans context lines and uses the last function declaration found as the actual changed function.

### Reason 2 — Import Path Mismatch in the Database

Test files store imports as raw relative paths (`'../helpers/utilities'`). The diff analysis generates search terms as file stems (`'utilities'`). The DB only had the raw path — no exact or LIKE match was possible.

- **Fix applied:** `_normalize_import_to_stem('../helpers/utilities')` → `'utilities'`. The `reverse_index` now stores BOTH the raw path AND the normalized stem. Re-analysis required (and completed).

### Reason 3 — "Both" Tests Filtered by Composite Score (Score 33–37 < 40)

When a test is found by BOTH AST (`direct_file` match) and semantic (low-medium similarity), the original formula gave too low a score:

```
Score = AST(55) × 40% + Vector(36) × 30% + LLM(0) × 20% + Speed(10) × 10%
      = 22 + 10.8 + 0 + 1  =  33.8  →  filtered (< 40)
```

Legitimate siblings like `checkArray`, `getProgressWidth` were dropped even though AST found them.

- **Fix applied:** `is_ast_any` condition — any test with ANY AST match passes at a lower 30% floor. The semantic score is additional confirmation, not a penalty. Semantic-only tests still require ≥ 40%.

### Reason 4 — Indirect Function Calls Not Recorded

If a test calls `capitalizeFirstLetter()` which internally calls `checkWhiteSpace()`, the database only records the direct call. The indirect dependency on `checkWhiteSpace` is invisible to AST.

- **Why it happens:** Without the production codebase, the system cannot trace internal call chains.
- **Mitigation:** Strategy 4 (file-stem match) catches these defensively — any test importing from `utilities.js` is included.

### Reason 5 — Confidence Score Not Persisted in "No LLM" Branch

When LLM reasoning was disabled (or `llm_scores_map` was empty), the code called `calculate_confidence_score_with_breakdown()` but discarded the returned score (`_, breakdown = ...`), keeping the original low score from the RAG pipeline.

- **Fix applied:** Changed to `new_score, breakdown = ...` and explicitly stored `test['confidence_score'] = new_score`.

---

## 8. Why AST Fails Sometimes

| Reason | Status | Explanation |
|---|---|---|
| Wrong function from hunk header | ✅ Fixed | Pre-change context scan overrides hunk header with correct function |
| Context lines ignored (headerless path) | ✅ Fixed | Headerless path now scans pre-change context lines |
| Import path mismatch | ✅ Fixed + Re-analysis done | DB now stores both raw path AND normalized stem |
| "Both" tests filtered at 33–37% | ✅ Fixed | `is_ast_any` applies 30% floor for any AST match |
| Co-location drag of unrelated tests | ✅ Partially fixed | Co-location-only gate drops tests with no semantic confirmation |
| Re-analysis not run | ⚠️ Manual step | After any analyzer change, re-run `RepoAnalyzer` |
| Indirect calls not tracked | ⚠️ By design | No production codebase → cannot trace call chains |
| Test file not scanned on Windows | ✅ Fixed | Pre-scanned file list passed directly to analyzer, bypassing internal re-scan |
| Strategy 4a expansion never triggers | ⚠️ Edge case | If no exact-matched test is in the cross-dependent file, expansion never fires |

---

## 9. Confidence Score

The confidence score (0–100) is a weighted composite of four signals:

| Signal | Weight | What it measures |
|---|---|---|
| AST Score | 40% | How strong the database linkage is |
| Vector Score | 30% | Semantic similarity from Pinecone (0–100) |
| LLM Score | 20% | Relevance score given by LLM (0 = irrelevant) |
| Speed Score | 10% | Test execution time bonus (fast unit tests score higher) |

### AST Score Values

| Match type | AST Score | Meaning |
|---|---|---|
| `function_level` (direct call) | 100 | Test literally calls the changed function |
| `exact` / `describe_label` | 90 | Test suite is named after the changed symbol |
| `normalized_import` | 70 | Test file imports from the changed module (normalized) |
| `direct_file` / `file_stem` | 55 | Test file named after the changed module |
| `colocated_in_same_file` | 50 | Test shares a file with a directly-matched test |

### Score Formula

```
composite = AST × 0.40 + Vector × 0.30 + LLM × 0.20 + Speed × 0.10
```

### Special Rules

| Condition | Rule |
|---|---|
| AST-only (no semantic match) | Minimum floor of 50 |
| Any AST match (including "Both") | Minimum floor of 30% — semantic is confirmatory, not penalizing |
| Semantic-only, vector ≥ 55% | "Semantic primary boost" — applies 80% weight to vector score |
| LLM score = 0.0 | Does NOT count as "has LLM score" — 0.0 = irrelevant |
| Co-location-only + no semantic | Hard drop — filtered before scoring |

### Filter Thresholds

| Test type | Threshold | Reason |
|---|---|---|
| Semantic-only | ≥ 40% composite | Prevent dead-zone false positives |
| AST-confirmed (any strategy) | ≥ 30% composite | DB-confirmed dependency — lower bar acceptable |
| Co-location-only, no semantic | Dropped regardless | Weakest signal, no confirmatory evidence |
| LLM score > 0 | Always included | LLM explicitly confirmed relevance |

### Confidence Labels

| Score | Label | Meaning |
|---|---|---|
| 70–100 | High | Very likely to be affected |
| 40–69 | Medium | Probably affected |
| 30–39 | Low (AST-confirmed) | Weak combined signal but DB-confirmed |
| < 30 | Filtered out | Not selected |

---

## 10. Full Execution Flow (End to End)

```
USER submits diff via UI
        ↓
API endpoint receives diff + test_repo_id
        ↓
┌──────────────────────────────────────────────────────────┐
│  PHASE 1 — Parse Diff                                    │
│  deterministic/parsing/diff_parser.py                    │
│                                                          │
│  Detects format automatically:                           │
│  • Standard:   "diff --git a/... b/..." header           │
│  • Headerless: "Changed Files:" + file list (UI format)  │
│                                                          │
│  Extracts:                                               │
│  • Changed files, methods, classes, constants            │
│  • Pre-change context scan → correct changed function    │
│  • changed_line_ranges → {method, start_line, end_line}  │
│  • Deleted/renamed symbol detection                      │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│  PHASE 2 — Build Search Queries                          │
│  deterministic/parsing → build_search_queries()          │
│                                                          │
│  Produces:                                               │
│  • exact_matches:   ['checkWhiteSpace', 'utilities']     │
│  • module_matches:  ['helpers.utilities']                │
│  • test_file_candidates: ['utilities.test.js']           │
│  • changed_functions: [{module, function}]               │
│  • deleted_symbols / added_symbols / renamed_symbols     │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│  PHASE 3 — Dead Zone Check                               │
│  diff_scenario_analysis.py                               │
│                                                          │
│  • Query PostgreSQL: do ALL changed files have zero      │
│    test coverage? (check reverse_index + function_mapping│
│  • If YES (complete dead zone) → return 0 tests, stop   │
│  • If NO → continue to search phases                    │
└──────────────────────────────────────────────────────────┘
        ↓
        ├───────────────────────────┬──────────────────────┐
        ↓                           ↓
┌────────────────────┐   ┌──────────────────────────────┐
│   AST SEARCH       │   │   SEMANTIC SEARCH            │
│                    │   │                              │
│ find_tests_ast_    │   │ rag_pipeline.py              │
│ only()             │   │                              │
│                    │   │ 1. FULL diff → LLM summary   │
│ Strategy 0:        │   │    (concrete symbols + paths)│
│  function_mapping  │   │                              │
│ Strategy 2:        │   │ 2. Summary → N query         │
│  exact / describe  │   │    variations (LLM rewriter) │
│ Strategy 3:        │   │                              │
│  module pattern    │   │ 3. Each query →              │
│ Strategy 4:        │   │    Pinecone vector search    │
│  file stem         │   │                              │
│ Strategy 4a:       │   │ 4. Results merged by         │
│  co-location       │   │    similarity score          │
│  (+ gate: drop if  │   │                              │
│  no semantic conf.)│   └──────────────┬───────────────┘
└────────┬───────────┘                  │
         └──────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  PHASE 4 — Merge AST + Semantic Results                  │
│  process_diff_programmatic.py                            │
│                                                          │
│  • Combine by test_id                                    │
│  • Tag each: AST Only / Semantic Only / Both             │
│  • Update similarity on "Both" tests if semantic higher  │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│  PHASE 5 — LLM Reasoning (optional)                      │
│  llm_reasoning_service.py                                │
│                                                          │
│  • Top candidates sent to LLM for relevance scoring      │
│  • LLM returns 0.0–1.0 per test                          │
│  • 0.0 = irrelevant (explicitly, not "no score")         │
│  • Scores merged back into match_details                 │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│  PHASE 6 — Score + Filter                                │
│  process_diff_programmatic.py                            │
│                                                          │
│  For each test:                                          │
│  1. Calculate composite confidence score                 │
│     (AST×40% + Vector×30% + LLM×20% + Speed×10%)        │
│  2. Co-location-only gate:                               │
│     ALL matches are colocated_in_same_file AND no        │
│     semantic → DROP immediately                          │
│  3. Filter thresholds:                                   │
│     • Semantic-only: must be ≥ 40%                       │
│     • AST-confirmed: passes at ≥ 30% (is_ast_any)        │
│     • LLM score > 0: always included                     │
│  4. Drop tests below threshold                           │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│  PHASE 7 — Format + Return                               │
│                                                          │
│  • Assign confidence labels (high/medium/low)            │
│  • Build coverage gap report                             │
│  • Build breakage warnings (deleted/renamed symbols)     │
│  • Return JSON to frontend                               │
└──────────────────────────────────────────────────────────┘
        ↓
UI displays selected tests with match type + confidence
```

---

## 11. All Fixes Applied (Chronological)

### Scenario 7 — Dead Zone False Positives (44 tests selected, should be 0)

| Fix | File | Description |
|---|---|---|
| Dead zone early exit | `diff_scenario_analysis.py` | Added `check_dead_zone_for_files()` — if ALL changed files have zero DB coverage, return 0 tests immediately |
| Semantic-only filter | `process_diff_programmatic.py` | Removed `has_semantic` from unconditional pass; semantic-only tests must now meet 40% threshold |
| Adaptive threshold | `process_diff_programmatic.py` | When AST finds 0 tests, semantic threshold tightened to 0.45 |

---

### Scenario 8 — AST Found 0 Tests, All Confidence "Low"

| Fix | File | Description |
|---|---|---|
| JavaScriptPlugin re-scan fix | `test_analysis/plugins/javascript/plugin.py` | Pre-scanned file list passed directly to analyzer, bypassing internal re-scan that returned 0 files on Windows long paths |
| `analyze()` accepts file list | `javascript_analyzer.py` | Added optional `test_files` parameter to skip internal scan |
| Confidence formula boost | `git_diff_processor.py` | Semantic primary boost threshold lowered from ≥70% to ≥55%; semantic-only weight raised to 80% for strong matches |
| Strategy 3 name filter removed | `git_diff_processor.py` | Removed filter requiring test name to contain the changed constant — broke shared constants cascade pattern |

---

### Scenario 9 — Wrong Tests Selected, Expected Tests Missing

| Fix | File | Description |
|---|---|---|
| Pre-change context scan (standard path) | `deterministic/parsing/diff_parser.py` | Context lines before first +/- scanned; last function declaration overrides hunk header method |
| Pre-change context scan (headerless path) | `deterministic/parsing/diff_parser.py` | Same fix applied to the UI's "Changed Files:" diff format |
| Import path normalization | `javascript_analyzer.py` | `_normalize_import_to_stem()` added; reverse_index now stores both raw path AND stem |
| `has_llm_score` bypass fix | `process_diff_programmatic.py` | Changed `llm_score is not None` to `llm_score > 0`; score=0.0 no longer bypasses filter |
| Confidence score persisted | `process_diff_programmatic.py` | Fixed `_, breakdown = ...` to `new_score, breakdown = ...`; score now stored correctly |
| `is_ast_any` (30% floor) | `process_diff_programmatic.py` | Replaced `is_ast_only` with `is_ast_any` — any AST match passes at 30%, fixing "Both" tests filtered at 33–37% |
| Co-location-only gate | `process_diff_programmatic.py` | Tests with ONLY co-location AST evidence AND no semantic → dropped |
| Changed line ranges | `deterministic/parsing/diff_parser.py` | `changed_line_ranges` dict added to file_info; records `{method, start_line, end_line}` per hunk for future precision improvements |

---

*Last updated: March 2026*
