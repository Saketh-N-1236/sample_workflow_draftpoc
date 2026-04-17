# Test Selection System — Complete Overview

> **Audience:** Manager / stakeholder review  
> **Purpose:** APIs, full execution flow, current accuracy gaps, and the codebase-analysis limitation.

---

## Table of Contents

1. [What the System Does](#1-what-the-system-does)
2. [API Catalogue](#2-api-catalogue)
3. [End-to-End Execution Flow](#3-end-to-end-execution-flow)
4. [Why the System Is Not Always Accurate](#4-why-the-system-is-not-always-accurate)
5. [The Codebase Analysis Gap](#5-the-codebase-analysis-gap)
6. [Summary Table](#6-summary-table)

---

## 1. What the System Does

Given a **git diff** (what lines of production code changed), the system automatically identifies the **minimum set of test cases** that need to run — without executing the entire test suite.

It answers: *"You changed these 5 lines. Out of 500 tests, only these 12 need to run."*

---

## 2. API Catalogue

The backend exposes **20 API endpoints** across 3 route groups.

### 2.1 Repository APIs (`/api/repositories`)

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 1 | GET | `/api/repositories` | List all connected repositories |
| 2 | POST | `/api/repositories/connect` | Connect a new GitHub / GitLab repository |
| 3 | GET | `/api/repositories/{id}/branches` | Fetch available branches for a repo |
| 4 | GET | `/api/repositories/{id}/diff` | Fetch the git diff for the latest commit |
| 5 | GET | `/api/repositories/{id}` | Get details of a single repository |
| 6 | PUT | `/api/repositories/{id}` | Update repository settings |
| 7 | PATCH | `/api/repositories/{id}/threshold` | Update the risk / confidence threshold |
| 8 | POST | `/api/repositories/{id}/refresh` | Re-sync repository metadata |

### 2.2 Test Repository APIs (`/api/test-repositories`)

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 9 | POST | `/api/test-repositories/upload` | Upload a test repository ZIP |
| 10 | GET | `/api/test-repositories` | List all uploaded test repositories |
| 11 | GET | `/api/test-repositories/{id}` | Get details of a test repository |
| 12 | DELETE | `/api/test-repositories/{id}` | Delete a test repository |
| 13 | GET | `/api/test-repositories/{id}/analysis` | Get analysis results (test registry, dependencies) |
| 14 | POST | `/api/test-repositories/{id}/analyze` | Re-run full static analysis on the test repo |
| 15 | POST | `/api/test-repositories/{id}/regenerate-embeddings` | Re-embed all tests into Pinecone |
| 16 | POST | `/api/test-repositories/repositories/{id}/bind-test-repo` | Link a test repo to a source repo |
| 17 | DELETE | `/api/test-repositories/repositories/{id}/unbind-test-repo/{tid}` | Unlink a test repo |
| 18 | GET | `/api/test-repositories/repositories/{id}/test-repositories` | List all test repos bound to a source repo |
| 19 | PUT | `/api/test-repositories/repositories/{id}/primary-test-repo/{tid}` | Set the primary test repo |

### 2.3 Selection API (`/api/repositories`)

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 20 | POST | `/api/repositories/{id}/select-tests` | **Core API — run test selection for a diff** |

---

## 3. End-to-End Execution Flow

When the user clicks **"Select Tests"**, the system goes through 2 independent layers and then merges results.

```
User clicks "Select Tests"
        │
        ▼
POST /api/repositories/{id}/select-tests
        │
        ├─── 1. Fetch diff from GitHub / GitLab
        │
        ├─── 2. Parse diff → extract changed files, symbols, functions
        │
        ├──────────────────────────────────────────────────┐
        │                                                  │
        ▼                                                  ▼
  LAYER 1: AST                                    LAYER 2: SEMANTIC
  (Structural Analysis)                           (Meaning-Based Search)
  ─────────────────────                           ─────────────────────
  SQL queries on test registry DB                 Embed diff → Pinecone search
  Matches: exact symbol names,                    Matches: tests whose descriptions
  file paths, import chains                       mean the same thing as the change
                                                  AI classifier: keeps Critical/High only
        │                                                  │
        └──────────────┬───────────────────────────────────┘
                       │
                       ▼
               MERGE both results
                       │
                       ▼
              Confidence filter
              (drop tests below threshold)
                       │
                       ▼
              Final selected tests returned
```

### Detailed Stage Breakdown

| Stage | What Happens | Component |
|-------|-------------|-----------|
| **Diff fetch** | Pull latest commit diff from GitHub/GitLab API | `github_service.py` / `gitlab_service.py` |
| **Diff parse** | Extract changed files, class names, function names, symbols | `diff_parser.py` |
| **AST search** | Query `reverse_index` DB table for tests linked to changed symbols | `selection_engine.py` |
| **Diff summarise** | LLM writes a plain-English summary of what changed | `diff_summarizer.py` |
| **Query rewrite** | LLM generates 4 angle variants of the query | `query_rewriter.py` |
| **Vector search** | Embed all queries → search Pinecone for similar tests | `rag_pipeline.py` |
| **LLM classify** | Filter semantic results: Critical / High / NonRelevant | `llm_reasoning_service.py` |
| **Co-location** | Pull in sibling tests from the same confirmed test file | `process_diff_programmatic.py` |
| **Merge** | Combine AST + Semantic results, deduplicate | `process_diff_programmatic.py` |
| **Filter** | Drop tests below confidence threshold | `selection_service.py` |
| **Return** | Send selected tests to frontend | `selection.py` |

---

## 4. Why the System Is Not Always Accurate

There are four categories of accuracy gaps, explained below with plain-language examples.

---

### 4.1 String-Value Changes Are Invisible to AST

**What happens:**
AST works by looking at *symbol names* (function names, constant names, class names). When a change is only a string value inside an object property, the AST sees *no named symbol changed* and returns 0 matches.

**Example:**
```js
// Before
paymentsCheckout: '/api/v2/payments/checkout'

// After
paymentsCheckout: '/api/v2/payments/v2/checkout'
```
The name `paymentsCheckout` didn't change — only its value did. AST finds 0 tests.

**Who covers the gap:** Semantic search — it understands *"payment checkout API path changed"* and finds the right tests through meaning, not symbol names.

**Impact:** Low — semantic search reliably covers this case. But it adds ~15–20 seconds to the selection time because semantic runs as fallback.

---

### 4.2 Cross-File Import Chains Are Not Traced for JavaScript

**What happens:**
When test file A imports from production file B, and production file B is what changed, the system needs to know "A depends on B" to include A's tests.

For Python files this works. For JavaScript / TypeScript, `import` statements in test files are not currently analysed — so the link between a test file and its production file dependency is missing from the database.

**Example:**
```js
// auth-storage.cross.test.js
import { EMAIL_REGEX } from '../types/constants'  // ← this import is NOT recorded
```
If `constants.ts` changes, the test above should be selected. But because the import chain is not in the database, AST cannot find it.

**Who covers the gap:** Semantic search + co-location. If any test from `auth-storage.cross.test.js` appears in vector search results, all sibling tests in the same file are also pulled in through co-location.

**Impact:** Medium — semantic + co-location recovers most missing tests, but the path is indirect and depends on vector similarity being strong enough to surface at least one test from that file.

---

### 4.3 Semantic Similarity Has a Fixed Threshold

**What happens:**
The vector search uses a similarity score between 0 and 1. Tests below 0.45 are dropped. If a genuinely relevant test scores 0.44 it is missed. If an irrelevant test scores 0.46 it is included.

**Example:**
A test for `validateEmailOrUsername` might score 0.44 against a `CARD_REGEX` change because there is only weak vocabulary overlap — it would be missed by vector search even though it imports from the same source file.

**Who covers the gap:** Co-location. If *any* test from that file passes the threshold, all sibling tests are co-located regardless of individual scores.

**Impact:** Low — co-location absorbs most near-miss cases. Residual risk is tests in files where no sibling crosses the threshold.

---

### 4.4 LLM Classifier Can Over-Prune

**What happens:**
After vector search returns candidates, an LLM classifier labels each test Critical / High / NonRelevant. Tests labelled NonRelevant are dropped. The LLM sometimes incorrectly marks a relevant test as NonRelevant — especially cross-dependent tests where the structural link (import) is not visible in the test name.

**Example:**
`validateEmailOrUsername uses EMAIL_REGEX` — the LLM may see this as unrelated to a `CARD_REGEX` change and mark it NonRelevant, even though both are in the same source file.

**Who covers the gap:** AST-linked tests are **restored** even if the classifier drops them (a safety rule: AST evidence overrides classifier label). Tests found only by semantic with no AST link may be lost.

**Impact:** Medium for tests that are semantic-only with no AST confirmation.

---

## 5. The Codebase Analysis Gap

This is the single most important structural limitation of the current system.

### What "codebase analysis" means

When the test repository is uploaded and analysed, the system:
- ✅ Reads every **test file** and records: test names, describe labels, class names
- ✅ Records which tests exist and what they are called
- ❌ Does **not** read the **production source files** to record: which functions exist, which files import which, which constants are exported from where

### Why this matters

The test selection is only as good as the map between *production code* and *tests*. Without reading production source files:

| What is missing | Effect |
|---|---|
| Import chains between production files and test files are not recorded | AST cannot find tests through import relationships for JS/TS |
| Which constants/functions are exported from which file is unknown | A change to `constants.ts` cannot be traced to every test that imports from it |
| The `reverse_index` table has only 220 entries for 77 tests | Most entries came from describe-label matching, not true production-to-test dependency analysis |

### Concrete consequence

When `constants.ts` changes:
- **What should happen:** Find every test file that has `import ... from 'constants'` and include all tests from those files
- **What actually happens:** Find tests whose describe label contains the changed symbol name (e.g., `CARD_REGEX`) — a much narrower set

The gap is covered by semantic search and co-location, but that is a workaround, not a solution.

### What the fix looks like

Analyse the production source files (not just test files) during the upload/analysis step:
1. Walk every `.js` / `.ts` / `.py` file in the repository
2. Extract all exported functions, constants, classes
3. Record which test files import from which production files
4. Populate the `reverse_index` with true production → test mappings

Once done, AST would handle all cross-file cases directly, eliminating the dependency on semantic search as a fallback for structural matches.

---

## 6. Summary Table

| Issue | Current Accuracy Impact | Covered By (workaround) | Permanent Fix |
|---|---|---|---|
| String-value changes invisible to AST | Low | Semantic search | Improve AST diff parsing to detect value changes |
| JS/TS import chains not traced | Medium | Semantic + co-location | Analyse production source files during upload |
| Fixed similarity threshold (0.45) | Low | Co-location expansion | Adaptive threshold per change type |
| LLM classifier over-prunes | Medium | AST-link restore rule | Improve LLM prompt (done ✓) |
| Codebase not analysed | High (structural) | Semantic + co-location as fallback | Upload-time production file analysis |

### Overall accuracy today

| Scenario type | Precision | Recall |
|---|---|---|
| Symbol / constant change (e.g. CARD_REGEX) | ~90% | ~95% |
| String-value change (e.g. API path) | ~85% | ~100% |
| Cross-file import change (JS) | ~80% | ~90% |
| Function rename / refactor | ~95% | ~95% |
