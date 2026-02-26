# Git Diff Processor - Usage Guide

## Overview

The Git Diff Processor reads git diff output and finds which tests should be run based on code changes. It queries the deterministic database to identify affected tests.

**What it does:**
1. Reads git diff from a file
2. Parses changes (files, classes, methods)
3. Shows what will be searched in the database
4. Queries database to find affected tests
5. Displays results with explanations

---

## Quick Start

### Step 1: Generate Git Diff

Save your git diff to a file:

```bash
# Option 1: Diff between two commits
git diff commit1 commit2 > git_diff_processor/sample_diffs/diff_commit1.txt

# Option 2: Single commit
git show commit_hash > git_diff_processor/sample_diffs/diff_commit1.txt

# Option 3: Uncommitted changes
git diff > git_diff_processor/sample_diffs/diff_uncommitted.txt
```

### Step 2: Run the Processor

```bash
# Specify file path
python git_diff_processor/git_diff_processor.py sample_diffs/diff_commit1.txt

# Or use default (sample_diffs/diff_commit1.txt)
python git_diff_processor/git_diff_processor.py
```

---

## How It Works

### Step-by-Step Process

**Step 1: Read Git Diff**
- Reads the diff file you provide
- Validates file exists and is readable

**Step 2: Parse Changes**
- Extracts changed files
- Identifies changed classes (from `class` definitions)
- Identifies changed methods (from `def` definitions)
- Counts additions/deletions

**Step 3: Build Search Strategy**
- Converts file paths to production class names
- Creates exact match queries (e.g., `agent.agent_pool`)
- Creates module-level patterns (e.g., `agent.*`)
- Shows what will be searched

**Step 4: Query Database**
- Queries `reverse_index` table for exact matches
- Queries for module patterns
- Combines results

**Step 5: Display Results**
- Shows all affected tests
- Indicates confidence level (high/medium)
- Explains why each test was selected

---

## Example Output

```
==================================================
Git Diff to Test Selection
==================================================

  Testing database connection...
[OK] Connected to database: planon
[OK] Using schema: planon1

  Step 1: Reading git diff file...
    File: sample_diffs/diff_commit1.txt
    File size: 245 characters
    Status: [OK] File read successfully

  Step 2: Parsing git diff...
  Parsed Changes:

    Changed files: 1
      - agent/agent_pool.py (modified)
    Changed classes: 0
    Changed methods: 2
      - get_agent
      - reset_agent

  Step 3: Building search strategy...
  What We'll Search in Database:

    Exact production class matches: 1
      - agent.agent_pool
    
    Database tables to query:
      - reverse_index (primary - fast lookup)
      - test_dependencies (secondary - fallback)

  Step 4: Querying database for affected tests...
  Querying database (Exact matches)...
    agent.agent_pool: 3 tests

  Step 5: Results
  Test Selection Results:

    Found 3 affected test(s):

  High Confidence Matches (Exact class matches): 3
    test_0001: TestAgentPool.test_get_agent_creates_new_instance
      Matched classes: agent.agent_pool
    test_0002: TestAgentPool.test_get_agent_reuses_instance
      Matched classes: agent.agent_pool
    test_0003: TestAgentPool.test_reset_agent
      Matched classes: agent.agent_pool

  Summary:
    Total tests to run: 3
    High confidence: 3
    Medium confidence: 0

==================================================
Processing Complete!
==================================================
Selected 3 test(s) to run based on code changes
```

---

## Understanding the Output

### Changed Files
Shows which production files were modified, added, or deleted.

### Search Strategy
Shows what production classes will be searched in the database:
- **Exact matches**: Direct class names (most reliable)
- **Module patterns**: Module-level matches like `agent.*` (broader search)

### Test Results
- **High confidence**: Tests that directly reference the changed class (exact match)
- **Medium confidence**: Tests that match module patterns (broader match)

### Why Tests Were Selected
Each test shows which production class matched, helping you understand why it was selected.

---

## File Format

The processor expects standard git unified diff format:

```diff
diff --git a/path/to/file.py b/path/to/file.py
index abc123..def456 100644
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,6 +10,8 @@ def function_name():
+    # New line
     existing_code
+    return value
```

**Supported:**
- ✅ Multiple files in one diff
- ✅ Additions, deletions, modifications
- ✅ Class and method changes
- ✅ Standard git diff format

---

## Database Connection

The processor connects to the deterministic database:
- Uses `deterministic/db_connection.py`
- Queries `planon1` schema
- Requires `.env` file with database credentials

**Make sure:**
1. Deterministic database is set up
2. `.env` file is configured
3. Database connection test passes

---

## Common Scenarios

### Scenario 1: Single File Change

**Git Diff:** One file changed (`agent/agent_pool.py`)

**Result:** Finds all tests that reference `agent.agent_pool`

**Example:** 3 tests found (all test methods in `TestAgentPool` class)

---

### Scenario 2: Multiple Files Changed

**Git Diff:** Multiple files changed

**Result:** Finds tests for all changed files, combines results

**Example:** 
- `agent/agent_pool.py` → 3 tests
- `api/routes.py` → 5 tests
- **Total:** 8 unique tests (some may overlap)

---

### Scenario 3: Module-Level Changes

**Git Diff:** Multiple files in same module changed (e.g., `agent/*.py`)

**Result:** Uses module pattern matching (`agent.*`)

**Example:** Finds all tests that reference any class in `agent` module

---

### Scenario 4: No Tests Found

**Possible reasons:**
- Changed files are not referenced by any tests
- Changed files are test files themselves
- Production class names don't match database entries

**What to do:**
- Check if the changed file is actually production code
- Verify class names match what's in the database
- Consider running full regression if unsure

---

## Advanced Usage

### Custom Diff File Location

```bash
python git_diff_processor/git_diff_processor.py /path/to/your/diff.txt
```

### Processing Multiple Diffs

```bash
# Process first commit
python git_diff_processor/git_diff_processor.py sample_diffs/diff_commit1.txt

# Process second commit
python git_diff_processor/git_diff_processor.py sample_diffs/diff_commit2.txt
```

---

## Troubleshooting

### Error: "Diff file not found"
**Solution:** Check the file path. Use absolute path if needed.

### Error: "Cannot connect to database"
**Solution:** 
1. Run `python deterministic/db_connection.py` to test connection
2. Check `.env` file configuration
3. Ensure database is running

### Error: "No tests found"
**Possible causes:**
- Changed files are test files (not production code)
- Class names don't match database entries
- Files are new and not yet referenced by tests

**Solution:** Check the parsed changes output to see what was detected.

---

## Next Steps

After getting test selection results:
1. Review the selected tests
2. Run the selected tests in your CI/CD pipeline
3. Collect test results for feedback loop
4. Use results to improve selection accuracy

---

## Integration with CI/CD

This processor can be integrated into CI/CD pipelines:

```bash
# In CI/CD script
git diff $BASE_COMMIT $HEAD_COMMIT > diff.txt
python git_diff_processor/git_diff_processor.py diff.txt > selected_tests.txt
# Use selected_tests.txt to run only affected tests
```

---

## Files in This Package

- `git_diff_processor.py` - Main script
- `utils/diff_parser.py` - Diff parsing utilities
- `sample_diffs/` - Folder for your diff files
- `README.md` - This file

---

## Dependencies

- `deterministic/db_connection.py` - Database connection
- `deterministic/utils/db_helpers.py` - Database query helpers
- Python standard library (no external dependencies)

---

## Support

For issues or questions:
1. Check the parsed changes output
2. Verify database connection
3. Review the search strategy display
4. Check database has test data loaded
