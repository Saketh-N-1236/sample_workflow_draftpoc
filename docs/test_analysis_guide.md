# Test Analysis Guide - Beginner's Documentation

## Overview

This guide explains the **Test Analysis** phase of the project. This phase analyzes your test repository to extract information about all your tests, their structure, dependencies, and characteristics.

**What it does:** Scans your test files and creates a complete inventory of everything about your tests.

---

## What is Test Analysis?

Test Analysis is like creating a **catalog** of all your tests. Just like a library catalog tells you:
- What books are available
- Where they are located
- What topics they cover

Test Analysis tells you:
- What tests exist
- Where they are located
- What code they test
- How they are organized

---

## The 8-Step Process

We break down the analysis into 8 simple steps. Each step does one specific job and saves its results.

### Step 1: Scan Test Files 📁

**What it does:** Finds all test files in your repository

**How it works:**
1. Scans the `test_repository/` folder
2. Looks for files matching test patterns: `test_*.py`, `*_test.py`
3. Counts lines, gets file sizes
4. Groups files by type (unit, integration, e2e)

**Example Output:**
```
Found 15 test files:
  - unit/test_agent_pool.py (127 lines)
  - unit/test_api_routes.py (180 lines)
  - integration/test_agent_flow.py (164 lines)
  - e2e/test_complete_chat_flow.py (145 lines)
```

**File:** `test_analysis/01_scan_test_files.py`

**Output:** `test_analysis/outputs/01_test_files.json`

---

### Step 2: Detect Framework 🔍

**What it does:** Identifies which test framework you're using (pytest, unittest, etc.)

**How it works:**
1. Checks for configuration files (`pytest.ini`, `conftest.py`)
2. Scans test files for framework-specific patterns
3. Looks for imports like `import pytest` or `import unittest`
4. Determines the primary framework with confidence level

**Example Output:**
```
Framework detected: pytest
Confidence: high
Indicators:
  - pytest.ini found
  - conftest.py found
  - 15 files use pytest
```

**File:** `test_analysis/02_detect_framework.py`

**Output:** `test_analysis/outputs/02_framework_detection.json`

---

### Step 3: Build Test Registry 📋

**What it does:** Creates a complete list of all tests with unique IDs

**How it works:**
1. Parses each test file using AST (Abstract Syntax Tree)
2. Finds test classes (classes starting with `Test`)
3. Finds test methods (methods starting with `test_`)
4. Assigns unique ID to each test (test_0001, test_0002, etc.)

**Example:**
```python
# From test_agent_pool.py
class TestAgentPool:
    def test_get_agent_creates_new_instance(self):
        # This becomes:
        # test_id: test_0001
        # class_name: TestAgentPool
        # method_name: test_get_agent_creates_new_instance
```

**Example Output:**
```
Total tests: 95
Total classes: 18
Tests by type:
  - unit: 95
```

**File:** `test_analysis/03_build_test_registry.py`

**Output:** `test_analysis/outputs/03_test_registry.json`

**JSON Structure:**
```json
{
  "total_tests": 95,
  "tests": [
    {
      "test_id": "test_0001",
      "file_path": "test_repository/unit/test_agent_pool.py",
      "class_name": "TestAgentPool",
      "method_name": "test_get_agent_creates_new_instance",
      "test_type": "unit"
    }
  ]
}
```

---

### Step 4: Extract Static Dependencies 🔗

**What it does:** Finds which production code each test references

**How it works:**
1. Parses import statements in test files
2. Extracts what classes/modules are imported
3. Filters out test framework imports (pytest, unittest)
4. Maps each test to the production code it uses

**Example:**
```python
# In test_agent_pool.py
from agent.agent_pool import get_agent, reset_agent
from agent.langgraph_agent import LangGraphAgent

# This creates mappings:
# test_0001 -> agent.agent_pool
# test_0001 -> agent.langgraph_agent
```

**Example Output:**
```
Total dependencies: 617
Tests with dependencies: 86
Most referenced modules:
  - agent: 50 references
  - fastapi: 32 references
```

**File:** `test_analysis/04_extract_static_dependencies.py`

**Output:** `test_analysis/outputs/04_static_dependencies.json`

**Why this matters:** When production code changes, we can quickly find which tests might be affected.

---

### Step 5: Extract Test Metadata 📝

**What it does:** Extracts descriptions, markers, and characteristics from tests

**How it works:**
1. Reads test method names
2. Extracts docstrings (test descriptions)
3. Finds pytest markers (`@pytest.mark.slow`, `@pytest.mark.asyncio`)
4. Identifies test patterns (naming conventions)

**Example:**
```python
@pytest.mark.asyncio
async def test_get_agent_creates_new_instance(self):
    """Test that get_agent creates a new instance on first call."""
    # Extracted:
    # - description: "Test that get_agent creates a new instance on first call."
    # - markers: ["asyncio"]
    # - is_async: True
```

**Example Output:**
```
Tests with descriptions: 95 (100%)
Tests with markers: 0
Async tests: 0
Parameterized tests: 21
```

**File:** `test_analysis/05_extract_test_metadata.py`

**Output:** `test_analysis/outputs/05_test_metadata.json`

---

### Step 6: Build Reverse Index 🔄

**What it does:** Creates a reverse mapping: production code → tests

**Why this is important:** 
- Step 4 gives us: test → production code
- Step 6 gives us: production code → tests (the reverse)

This allows fast lookup: "Which tests use this class?"

**Example:**
```
Production Class: agent.agent_pool
  -> test_0001 (TestAgentPool.test_get_agent_creates_new_instance)
  -> test_0002 (TestAgentPool.test_get_agent_reuses_instance)
  -> test_0003 (TestAgentPool.test_reset_agent)
```

**Example Output:**
```
Total production classes: 49
Total mappings: 617
Most referenced class: HumanMessage (28 tests)
```

**File:** `test_analysis/06_build_reverse_index.py`

**Output:** `test_analysis/outputs/06_reverse_index.json`

**Use case:** When `agent.agent_pool.py` changes, we can instantly find all 3 tests that use it.

---

### Step 7: Map Test Structure 🗺️

**What it does:** Analyzes how tests are organized in directories

**How it works:**
1. Maps directory structure (unit/, integration/, e2e/)
2. Identifies shared utilities (conftest.py, fixtures/)
3. Counts files and lines per directory
4. Creates structure map

**Example Output:**
```
Directory Structure:
  unit/: 11 files, 2036 lines
  integration/: 2 files, 250 lines
  e2e/: 1 file, 145 lines
  
Shared Utilities:
  - conftest.py (378 lines)
  - fixtures/ (7 files)
```

**File:** `test_analysis/07_map_test_structure.py`

**Output:** `test_analysis/outputs/07_test_structure.json`

---

### Step 8: Generate Summary Report 📊

**What it does:** Combines all previous steps into one comprehensive report

**How it works:**
1. Loads all previous JSON outputs
2. Combines statistics
3. Generates insights
4. Creates final summary

**Example Output:**
```
Test Repository Overview:
  - 15 test files
  - 95 tests total
  - Framework: pytest (high confidence)
  
Key Insights:
  - Average of 1.9 tests per production class
  - 100% of tests have descriptions
  - Tests organized into 4 categories
```

**File:** `test_analysis/08_generate_summary.py`

**Output:** `test_analysis/outputs/08_summary_report.json`

---

## How to Run

### Run All Steps

```bash
# Step 1: Scan files
python test_analysis/01_scan_test_files.py

# Step 2: Detect framework
python test_analysis/02_detect_framework.py

# Step 3: Build registry
python test_analysis/03_build_test_registry.py

# Step 4: Extract dependencies
python test_analysis/04_extract_static_dependencies.py

# Step 5: Extract metadata
python test_analysis/05_extract_test_metadata.py

# Step 6: Build reverse index
python test_analysis/06_build_reverse_index.py

# Step 7: Map structure
python test_analysis/07_map_test_structure.py

# Step 8: Generate summary
python test_analysis/08_generate_summary.py
```

### Run Individual Steps

Each step can run independently. Some steps depend on previous outputs:
- Step 3 can use Step 1 output (or scan directly)
- Step 4 needs Step 3 output
- Step 5 needs Step 3 output
- Step 6 needs Step 4 output
- Step 8 needs all previous outputs

---

## Understanding the Output

### JSON Files

Each step creates a JSON file in `test_analysis/outputs/`. These files contain structured data that can be:
- Read by other programs
- Used for database loading
- Analyzed for insights

### Console Output

Each step also prints human-readable output showing:
- What it's doing
- Progress indicators
- Summary statistics
- Sample results

---

## Key Concepts for Beginners

### AST (Abstract Syntax Tree)

**What it is:** A tree-like representation of your code structure

**Why we use it:** 
- Can't just read code as text (too complex)
- AST parser understands code structure
- Can extract classes, methods, imports reliably

**Example:**
```python
# Your code:
class TestAgent:
    def test_method(self):
        pass

# AST representation:
# Module
#   └── ClassDef(name='TestAgent')
#       └── FunctionDef(name='test_method')
```

### Reverse Index

**Think of it like:** A phone book in reverse

**Normal phone book:** Name → Phone Number
**Reverse phone book:** Phone Number → Name

**In our case:**
- Normal: Test → Production Code (Step 4)
- Reverse: Production Code → Tests (Step 6)

**Why both?**
- Normal: "What does this test use?"
- Reverse: "Which tests use this code?" (faster for test selection)

---

## Real-World Example

Let's say you change a file: `agent/agent_pool.py`

**Using our analysis:**

1. **Step 6 (Reverse Index)** tells us:
   ```
   agent.agent_pool → [test_0001, test_0002, test_0003]
   ```

2. **Step 3 (Registry)** tells us:
   ```
   test_0001: TestAgentPool.test_get_agent_creates_new_instance
   test_0002: TestAgentPool.test_get_agent_reuses_instance
   test_0003: TestAgentPool.test_reset_agent
   ```

3. **Result:** We know exactly which 3 tests to run!

**Without analysis:** You'd have to guess or run all 95 tests.

---

## What You Get After Analysis

After running all 8 steps, you have:

✅ **Complete test inventory** (95 tests cataloged)
✅ **Test-to-code mappings** (617 dependency relationships)
✅ **Reverse index** (49 production classes mapped)
✅ **Test metadata** (descriptions, markers, patterns)
✅ **Structure map** (directory organization)

**This data is ready for:**
- Loading into database (next phase)
- Building test selection algorithms
- Creating test impact analysis

---

## Common Questions

### Q: Do I need to run all steps?
**A:** Yes, for complete analysis. But you can run steps individually to understand each one.

### Q: What if I add new tests?
**A:** Re-run the analysis steps. They will update the JSON files with new tests.

### Q: How long does it take?
**A:** For 15 files with 95 tests: less than 1 minute total.

### Q: Can I modify the analysis?
**A:** Yes! Each step is a separate file. You can modify any step to add new analysis.

---

## Next Steps

After completing test analysis, the next phase is:
- **Deterministic Database** - Store all this data in PostgreSQL for fast queries

See `docs/deterministic_database_guide.md` for the next phase.
