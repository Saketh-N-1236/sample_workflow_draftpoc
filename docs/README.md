# Documentation Index

This folder contains beginner-friendly documentation for the Test Impact Analysis platform.

## Available Guides

### 1. [Test Analysis Guide](test_analysis_guide.md)
Complete guide to the test analysis phase:
- How test files are scanned and analyzed
- 8-step process explained with examples
- Understanding AST parsing
- Reverse indexing concepts
- Real-world usage examples

**Read this first** to understand how we extract information from your test repository.

### 2. [Deterministic Database Guide](deterministic_database_guide.md)
Complete guide to the database implementation:
- Database schema and table structure
- How data is loaded from JSON to PostgreSQL
- Understanding foreign keys and indexes
- SQL query examples
- Real-world usage scenarios

**Read this second** to understand how data is stored and queried.

## Quick Start

### For Test Analysis:
1. Read: [Test Analysis Guide](test_analysis_guide.md)
2. Run: `python test_analysis/01_scan_test_files.py` (and subsequent steps)
3. Check: `test_analysis/outputs/` for JSON results

### For Database:
1. Read: [Deterministic Database Guide](deterministic_database_guide.md)
2. Setup: Create `.env` file with database credentials
3. Run: `python deterministic/01_create_tables.py` (and subsequent steps)
4. Verify: `python deterministic/07_verify_data.py`

## Project Flow

```
Test Repository
    ↓
[Test Analysis Phase]
    ├── Step 1: Scan files
    ├── Step 2: Detect framework
    ├── Step 3: Build registry
    ├── Step 4: Extract dependencies
    ├── Step 5: Extract metadata
    ├── Step 6: Build reverse index
    ├── Step 7: Map structure
    └── Step 8: Generate summary
    ↓
JSON Output Files
    ↓
[Database Phase]
    ├── Step 1: Create tables
    ├── Step 2: Load registry
    ├── Step 3: Load dependencies
    ├── Step 4: Load reverse index
    ├── Step 5: Load metadata
    ├── Step 6: Load structure
    └── Step 7: Verify data
    ↓
PostgreSQL Database (planon.planon1)
    ↓
Ready for Test Selection Algorithms
```

## Key Concepts

### Test Analysis Concepts
- **AST Parsing**: Understanding code structure programmatically
- **Reverse Index**: Fast lookup of "which tests use this code"
- **Static Dependencies**: Code relationships extracted from imports

### Database Concepts
- **Foreign Keys**: Links between tables ensuring data integrity
- **Indexes**: Fast query performance
- **Connection Pooling**: Efficient database connection management
- **Batch Operations**: Inserting multiple records efficiently

## Examples in Documentation

Both guides include:
- ✅ Step-by-step explanations
- ✅ Code examples
- ✅ Real-world scenarios
- ✅ Common questions answered
- ✅ Beginner-friendly language

## Need Help?

If you're stuck:
1. Check the relevant guide (Test Analysis or Database)
2. Look at the example outputs in the guide
3. Run the verification scripts to see what's working
4. Check the JSON output files to understand data structure

## What's Next?

After understanding both phases:
- Build test selection algorithms using SQL queries
- Add semantic/vector data for AI-powered matching
- Create API endpoints for CI/CD integration
