# Deterministic Database Guide - Beginner's Documentation

## Overview

This guide explains the **Deterministic Database** phase. This phase stores all the test analysis data into a PostgreSQL database so we can query it quickly and efficiently.

**What it does:** Takes the JSON files from test analysis and loads them into a structured database.

**Why a database?** 
- Fast queries (find tests in milliseconds)
- Relational data (link tests to code)
- Scalable (handles thousands of tests)
- Ready for semantic data (can add vector embeddings later)

---

## What is "Deterministic"?

**Deterministic** means "based on facts, not guesses."

In our case:
- ✅ **Deterministic:** Test imports `agent.agent_pool` → we know this for certain
- ✅ **Deterministic:** Test file is in `unit/` directory → fact
- ❌ **Not deterministic:** "This test might be related" → guess

**Why deterministic first?**
- Most reliable (based on actual code)
- Fast (simple SQL queries)
- Safe (no false positives)

Later, we'll add **semantic** (AI-based) analysis to enhance, not replace, deterministic data.

---

## Database Setup

### Your Database Configuration

- **Database Name:** `planon`
- **Schema Name:** `planon1`
- **All tables created in:** `planon1` schema

### Environment Variables

Create a `.env` file in the `deterministic/` folder:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=planon
DB_SCHEMA=planon1
DB_USER=your_username
DB_PASSWORD=your_password
```

**Important:** Never commit `.env` to version control (it contains passwords).

---

## The 7-Step Process

### Step 1: Database Connection 🔌

**What it does:** Sets up connection to PostgreSQL database

**File:** `deterministic/db_connection.py`

**Key Features:**
- Loads credentials from `.env` file
- Creates connection pool (reuses connections)
- Sets schema search path to `planon1`
- Provides context manager for safe connections

**How to test:**
```bash
python deterministic/db_connection.py
```

**Example Output:**
```
[OK] Connected to database: planon
[OK] Using schema: planon1
[OK] Schema exists and is accessible
Connection test PASSED!
```

**What you learn:**
- How to connect to PostgreSQL from Python
- Connection pooling (efficient reuse)
- Environment variables for security

---

### Step 2: Create Tables 🏗️

**What it does:** Creates all database tables with proper structure

**File:** `deterministic/01_create_tables.py`

**Tables Created:**

#### 1. `test_registry`
Stores all test information.

**Columns:**
- `test_id` (Primary Key) - Unique identifier (test_0001, test_0002, etc.)
- `file_path` - Path to test file
- `class_name` - Test class name (if any)
- `method_name` - Test method name
- `test_type` - Type of test (unit, integration, e2e)
- `line_number` - Line number in file

**Example Data:**
```
test_id: test_0001
file_path: test_repository/unit/test_agent_pool.py
class_name: TestAgentPool
method_name: test_get_agent_creates_new_instance
test_type: unit
```

#### 2. `test_dependencies`
Stores test → production code mappings.

**Columns:**
- `id` (Primary Key)
- `test_id` (Foreign Key → test_registry)
- `referenced_class` - Production class/module name
- `import_type` - Type of import

**Example Data:**
```
test_id: test_0001
referenced_class: agent.agent_pool
import_type: from_import
```

**Why this table?** Answers: "What production code does this test use?"

#### 3. `reverse_index`
Stores production code → tests mappings (the reverse).

**Columns:**
- `id` (Primary Key)
- `production_class` - Production class/module name
- `test_id` (Foreign Key → test_registry)
- `test_file_path` - Denormalized for performance

**Example Data:**
```
production_class: agent.agent_pool
test_id: test_0001
test_file_path: test_repository/unit/test_agent_pool.py
```

**Why this table?** Answers: "Which tests use this production code?" (FAST lookup)

#### 4. `test_metadata`
Stores test descriptions, markers, and characteristics.

**Columns:**
- `id` (Primary Key)
- `test_id` (Foreign Key → test_registry, Unique)
- `description` - Test docstring/description
- `markers` - Pytest markers (stored as JSONB)
- `is_async` - Whether test is async
- `is_parameterized` - Whether test is parameterized
- `pattern` - Test naming pattern

**Example Data:**
```
test_id: test_0001
description: "Test that get_agent creates a new instance on first call."
markers: ["asyncio"]
is_async: true
pattern: "test_prefix"
```

#### 5. `test_structure`
Stores directory structure information.

**Columns:**
- `id` (Primary Key)
- `directory_path` - Path to directory
- `category` - Test category (unit, integration, e2e)
- `file_count` - Number of files
- `total_lines` - Total lines of code

**Indexes Created:**
- Indexes on foreign keys (for fast joins)
- Indexes on frequently queried columns
- GIN index on JSONB markers (for JSON queries)

**How to run:**
```bash
python deterministic/01_create_tables.py
```

**Example Output:**
```
[OK] Created table: planon1.test_registry
[OK] Created table: planon1.test_dependencies
[OK] Created table: planon1.reverse_index
[OK] Created table: planon1.test_metadata
[OK] Created table: planon1.test_structure
[OK] All tables created successfully!
```

---

### Step 3: Load Test Registry 📥

**What it does:** Loads all tests from JSON into `test_registry` table

**File:** `deterministic/02_load_test_registry.py`

**How it works:**
1. Reads `test_analysis/outputs/03_test_registry.json`
2. Extracts all test records
3. Inserts into `test_registry` table
4. Handles duplicates (updates if test_id exists)

**Example:**
```python
# From JSON:
{
  "test_id": "test_0001",
  "file_path": "test_repository/unit/test_agent_pool.py",
  "class_name": "TestAgentPool",
  "method_name": "test_get_agent_creates_new_instance"
}

# Inserted into database:
INSERT INTO planon1.test_registry 
(test_id, file_path, class_name, method_name, test_type)
VALUES ('test_0001', '...', 'TestAgentPool', '...', 'unit')
```

**How to run:**
```bash
python deterministic/02_load_test_registry.py
```

**Example Output:**
```
Loading 95 tests in batches of 50...
Processing: 95/95 tests (100.0%)

Loading Summary:
  Total tests in JSON: 95
  Successfully loaded: 95
  Tests in database (after): 95
```

---

### Step 4: Load Dependencies 🔗

**What it does:** Loads test → production code mappings

**File:** `deterministic/03_load_dependencies.py`

**How it works:**
1. Reads `test_analysis/outputs/04_static_dependencies.json`
2. For each test, extracts all referenced classes
3. Inserts into `test_dependencies` table
4. Links to `test_registry` via foreign key

**Example:**
```python
# Test test_0001 references:
# - agent.agent_pool
# - agent.langgraph_agent

# Creates 2 rows in test_dependencies:
# Row 1: test_id=test_0001, referenced_class=agent.agent_pool
# Row 2: test_id=test_0001, referenced_class=agent.langgraph_agent
```

**How to run:**
```bash
python deterministic/03_load_dependencies.py
```

**Example Output:**
```
Loading 617 dependencies in batches of 100...
Processing: 617/617 dependencies (100.0%)

Loading Summary:
  Total dependencies: 617
  Successfully loaded: 617
  Unique production classes: 49
```

---

### Step 5: Load Reverse Index 🔄

**What it does:** Loads production code → tests mappings (the reverse)

**File:** `deterministic/04_load_reverse_index.py`

**Why this is important:**
This is the **fast lookup table**. When code changes, we can instantly find which tests to run.

**Example Query:**
```sql
-- "Which tests use agent.agent_pool?"
SELECT test_id, test_file_path 
FROM planon1.reverse_index 
WHERE production_class = 'agent.agent_pool';

-- Returns: test_0001, test_0002, test_0003
```

**How it works:**
1. Reads `test_analysis/outputs/06_reverse_index.json`
2. For each production class, gets list of tests
3. Inserts into `reverse_index` table
4. Creates indexes for fast queries

**How to run:**
```bash
python deterministic/04_load_reverse_index.py
```

**Example Output:**
```
Loading 617 reverse index entries...
Processing: 617/617 entries (100.0%)

Reverse Index Statistics:
  Unique production classes: 49
  Unique tests: 95
  Average tests per class: 12.59
```

---

### Step 6: Load Metadata 📝

**What it does:** Loads test descriptions, markers, and characteristics

**File:** `deterministic/05_load_metadata.py`

**How it works:**
1. Reads `test_analysis/outputs/05_test_metadata.json`
2. Extracts descriptions, markers, patterns
3. Stores markers as JSONB (for flexible querying)
4. Links to `test_registry` via test_id

**Example:**
```python
# Test metadata:
{
  "test_id": "test_0001",
  "description": "Test that get_agent creates a new instance",
  "markers": ["asyncio"],
  "is_async": true,
  "pattern": "test_prefix"
}

# Stored in database:
# - description as TEXT
# - markers as JSONB (can query with JSON operators)
# - is_async as BOOLEAN
```

**JSONB Benefits:**
- Can query markers: `WHERE markers @> '["asyncio"]'`
- Flexible (can add new markers without schema change)
- Fast queries with GIN index

**How to run:**
```bash
python deterministic/05_load_metadata.py
```

**Example Output:**
```
Loading 95 metadata records...
Processing: 95/95 records (100.0%)

Metadata Statistics:
  Tests with descriptions: 95 (100%)
  Tests with markers: 0
  Async tests: 0
  Parameterized tests: 21
```

---

### Step 7: Load Structure 🗺️

**What it does:** Loads directory structure information

**File:** `deterministic/06_load_structure.py`

**How it works:**
1. Reads `test_analysis/outputs/07_test_structure.json`
2. Extracts directory information
3. Inserts into `test_structure` table

**Example:**
```
Directory: unit/
  - File count: 11
  - Total lines: 2036
  - Category: unit
```

**How to run:**
```bash
python deterministic/06_load_structure.py
```

---

### Step 8: Verify Data ✅

**What it does:** Verifies all data loaded correctly and tests queries

**File:** `deterministic/07_verify_data.py`

**What it checks:**
1. Counts records in each table
2. Verifies foreign key relationships (no orphaned records)
3. Runs sample queries to test functionality
4. Displays comprehensive report

**Example Queries Tested:**

**Query 1: Find tests for a production class**
```sql
SELECT test_id, method_name
FROM planon1.reverse_index ri
JOIN planon1.test_registry tr ON ri.test_id = tr.test_id
WHERE ri.production_class = 'agent.agent_pool';
```

**Query 2: Tests by type**
```sql
SELECT test_type, COUNT(*) 
FROM planon1.test_registry 
GROUP BY test_type;
```

**Query 3: Tests with most dependencies**
```sql
SELECT tr.test_id, tr.method_name, COUNT(td.id) as dep_count
FROM planon1.test_registry tr
LEFT JOIN planon1.test_dependencies td ON tr.test_id = td.test_id
GROUP BY tr.test_id, tr.method_name
ORDER BY dep_count DESC
LIMIT 5;
```

**How to run:**
```bash
python deterministic/07_verify_data.py
```

**Example Output:**
```
Verification Summary:
  Total records: 1428
  Foreign key integrity: [OK] Valid
  Data loaded successfully: [OK] Yes
  
Database is ready for:
  - Deterministic test selection queries
  - Fast code -> tests lookups
  - Test metadata queries
```

---

## Understanding Database Relationships

### Foreign Keys

Foreign keys link tables together and ensure data integrity.

**Example:**
```
test_dependencies.test_id → test_registry.test_id
```

This means:
- Every `test_id` in `test_dependencies` MUST exist in `test_registry`
- If you delete a test from `test_registry`, related dependencies are automatically deleted (CASCADE)
- Prevents orphaned records (dependencies pointing to non-existent tests)

### Indexes

Indexes make queries fast. Think of them like an index in a book:
- Without index: Read entire book to find a topic
- With index: Jump directly to the page

**Our indexes:**
- `test_registry.file_path` - Fast lookup by file
- `reverse_index.production_class` - Fast lookup by code
- `test_metadata.markers` (GIN) - Fast JSON queries

---

## Real-World Usage Examples

### Example 1: Find Tests for Changed Code

**Scenario:** You changed `agent/agent_pool.py`

**Query:**
```sql
-- Step 1: Find tests using this class
SELECT DISTINCT tr.test_id, tr.class_name, tr.method_name
FROM planon1.reverse_index ri
JOIN planon1.test_registry tr ON ri.test_id = tr.test_id
WHERE ri.production_class = 'agent.agent_pool'
ORDER BY tr.test_id;
```

**Result:**
```
test_0001 | TestAgentPool | test_get_agent_creates_new_instance
test_0002 | TestAgentPool | test_get_agent_reuses_instance
test_0003 | TestAgentPool | test_reset_agent
```

**Action:** Run these 3 tests instead of all 95!

---

### Example 2: Get Test Details

**Scenario:** You want details about a specific test

**Query:**
```sql
SELECT 
    tr.test_id,
    tr.class_name,
    tr.method_name,
    tr.file_path,
    tm.description,
    tm.markers,
    COUNT(td.id) as dependency_count
FROM planon1.test_registry tr
LEFT JOIN planon1.test_metadata tm ON tr.test_id = tm.test_id
LEFT JOIN planon1.test_dependencies td ON tr.test_id = td.test_id
WHERE tr.test_id = 'test_0001'
GROUP BY tr.test_id, tr.class_name, tr.method_name, tr.file_path, tm.description, tm.markers;
```

**Result:**
```
test_id: test_0001
class_name: TestAgentPool
method_name: test_get_agent_creates_new_instance
file_path: test_repository/unit/test_agent_pool.py
description: "Test that get_agent creates a new instance on first call."
markers: ["asyncio"]
dependency_count: 8
```

---

### Example 3: Find All Async Tests

**Query:**
```sql
SELECT tr.test_id, tr.method_name, tr.file_path
FROM planon1.test_registry tr
JOIN planon1.test_metadata tm ON tr.test_id = tm.test_id
WHERE tm.is_async = true;
```

---

## Database Schema Diagram

```
test_registry (95 rows)
    │
    ├── test_dependencies (617 rows)
    │   └── test_id → test_registry.test_id
    │
    ├── reverse_index (617 rows)
    │   └── test_id → test_registry.test_id
    │
    └── test_metadata (95 rows)
        └── test_id → test_registry.test_id (unique)

test_structure (4 rows)
    └── (independent table)
```

**Key Points:**
- `test_registry` is the central table
- Other tables link to it via `test_id`
- `reverse_index` is optimized for fast lookups
- All relationships use foreign keys for data integrity

---

## How Data Flows

### From Test Analysis to Database

```
Test Analysis JSON Files
    ↓
Load Scripts (Steps 2-6)
    ↓
PostgreSQL Database (planon.planon1)
    ↓
Ready for Queries
```

### Example Flow:

1. **Test Analysis** creates: `03_test_registry.json` (95 tests)
2. **Load Script** reads JSON and inserts into database
3. **Database** stores: 95 rows in `test_registry` table
4. **Query** retrieves: `SELECT * FROM test_registry WHERE test_type = 'unit'`

---

## Key Concepts for Beginners

### Connection Pooling

**What it is:** Reusing database connections instead of creating new ones each time

**Why it matters:**
- Creating connections is slow
- Pool keeps connections ready
- Much faster for multiple queries

**Example:**
```python
# Without pooling: Create connection, use, close (slow)
# With pooling: Get from pool, use, return to pool (fast)
```

### Batch Insert

**What it is:** Inserting multiple rows at once instead of one-by-one

**Why it matters:**
- One-by-one: 95 separate INSERT statements (slow)
- Batch: 1 INSERT with 95 rows (fast)

**Example:**
```python
# Slow (95 queries):
for test in tests:
    cursor.execute("INSERT INTO test_registry ...", test)

# Fast (1 query):
execute_values(cursor, "INSERT INTO test_registry ...", all_tests)
```

### Foreign Keys

**What they are:** Links between tables that ensure data consistency

**Example:**
- `test_dependencies.test_id` must exist in `test_registry`
- Prevents: Dependencies pointing to non-existent tests
- Enforces: Data integrity

### Indexes

**What they are:** Special data structures that make queries fast

**Example:**
- Without index: Scan all 617 rows to find `agent.agent_pool`
- With index: Jump directly to matching rows (milliseconds)

---

## Common Questions

### Q: Why PostgreSQL instead of a simple file?
**A:** 
- Fast queries (milliseconds vs seconds)
- Handles relationships (foreign keys)
- Scalable (millions of records)
- Can add vector search later (pgvector)

### Q: What if I need to update data?
**A:** Re-run the load scripts. They use `ON CONFLICT` to update existing records.

### Q: Can I query the database directly?
**A:** Yes! Use any PostgreSQL client (pgAdmin, DBeaver, psql) or Python scripts.

### Q: What's next after this?
**A:** 
1. Build test selection algorithms (using SQL queries)
2. Add semantic/vector data (pgvector extension)
3. Create API endpoints for test selection

---

## Summary

**What we accomplished:**
✅ Created 5 database tables with proper structure
✅ Loaded 95 tests into `test_registry`
✅ Loaded 617 dependencies into `test_dependencies`
✅ Loaded 617 reverse index entries
✅ Loaded 95 metadata records
✅ Loaded 4 structure records
✅ Verified all data integrity

**Total records:** 1,428 across all tables

**Database is ready for:**
- Fast deterministic test selection
- Code → tests lookups
- Test metadata queries
- Future semantic enhancements

---

## Next Steps

After deterministic database is complete:
1. **Test Selection Algorithms** - Build SQL queries to select tests based on code changes
2. **Semantic Layer** - Add vector embeddings for AI-powered matching
3. **API Development** - Create REST API for CI/CD integration

The foundation is solid and ready for the next phase!
