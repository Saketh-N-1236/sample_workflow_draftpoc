# Test Selection System - Visual Flow Diagram

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: TEST REPOSITORY ANALYSIS                   │
└─────────────────────────────────────────────────────────────────────────────┘

    Test Repository (test_repository/)
           │
           ├─ test_*.py files
           ├─ *_test.py files
           ├─ unit/ directory
           ├─ integration/ directory
           └─ e2e/ directory
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 1: Scan Test Files (01_scan_test_files.py)            │
    │  • Recursively scan repository                               │
    │  • Identify test file patterns                               │
    │  • Extract file metadata                                     │
    │  • Categorize by directory type                              │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 2: Detect Framework (02_detect_framework.py)          │
    │  • Check pytest.ini, setup.cfg, pyproject.toml               │
    │  • Analyze conftest.py                                      │
    │  • Identify framework patterns                               │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 3: Build Test Registry (03_build_test_registry.py)    │
    │  • Parse files using AST                                     │
    │  • Extract test classes (class Test*)                       │
    │  • Extract test methods (def test_*)                        │
    │  • Generate unique test IDs                                  │
    │  • Categorize test types (unit/integration/e2e)             │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 4: Extract Dependencies (04_extract_static_dependencies)│
    │  • Parse imports from test files                             │
    │  • Extract string references (patch(), Mock())              │
    │  • Filter production code imports                            │
    │  • Map test → production code                                │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 5: Extract Metadata (05_extract_test_metadata.py)     │
    │  • Extract docstrings                                        │
    │  • Identify pytest markers                                   │
    │  • Detect async tests                                        │
    │  • Detect parameterized tests                                │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 6: Build Reverse Index (06_build_reverse_index.py)    │
    │  • Create production code → tests mapping                    │
    │  • Include reference types (direct_import, string_ref)      │
    │  • Enable fast lookup                                        │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 7: Map Structure (07_map_test_structure.py)            │
    │  • Map directory structure                                   │
    │  • Count files per category                                  │
    │  • Calculate statistics                                     │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 8: Generate Summary (08_generate_summary.py)          │
    │  • Aggregate all statistics                                  │
    │  • Create comprehensive report                               │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    JSON Output Files (test_analysis/outputs/)
    ├── 01_test_files.json
    ├── 02_framework_detection.json
    ├── 03_test_registry.json
    ├── 04_static_dependencies.json
    ├── 05_test_metadata.json
    ├── 06_reverse_index.json
    ├── 07_test_structure.json
    └── 08_summary_report.json


┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 2: DATABASE LOADING                               │
└─────────────────────────────────────────────────────────────────────────────┘

    JSON Output Files
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 1: Create Tables (01_create_tables.py)                 │
    │  • Create PostgreSQL schema                                   │
    │  • Create test_registry table                                 │
    │  • Create test_dependencies table                             │
    │  • Create reverse_index table                                 │
    │  • Create test_metadata table                                 │
    │  • Create test_structure table                                │
    │  • Create indexes for performance                            │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 2: Load Test Registry (02_load_test_registry.py)      │
    │  • Read 03_test_registry.json                                │
    │  • Batch insert into test_registry table                     │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 3: Load Dependencies (03_load_test_dependencies.py)   │
    │  • Read 04_static_dependencies.json                           │
    │  • Batch insert into test_dependencies table                 │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 4: Load Reverse Index (04_load_reverse_index.py)      │
    │  • Read 06_reverse_index.json                                │
    │  • Batch insert into reverse_index table                     │
    │  • Include reference_type (direct_import, string_ref)       │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 5: Load Metadata (05_load_test_metadata.py)           │
    │  • Read 05_test_metadata.json                                │
    │  • Batch insert into test_metadata table                     │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 6: Load Structure (06_load_test_structure.py)          │
    │  • Read 07_test_structure.json                               │
    │  • Batch insert into test_structure table                    │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 7: Verify Data (07_verify_data.py)                     │
    │  • Count records in each table                               │
    │  • Verify foreign key relationships                          │
    │  • Run sample queries                                        │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │           PostgreSQL Database (planon.planon1)                │
    │  ┌────────────────────────────────────────────────────┐     │
    │  │ test_registry                                      │     │
    │  │ • test_id (PK)                                     │     │
    │  │ • file_path                                        │     │
    │  │ • class_name                                       │     │
    │  │ • method_name                                      │     │
    │  │ • test_type                                        │     │
    │  └────────────────────────────────────────────────────┘     │
    │  ┌────────────────────────────────────────────────────┐     │
    │  │ reverse_index                                       │     │
    │  │ • production_class                                  │     │
    │  │ • test_id (FK)                                      │     │
    │  │ • reference_type                                    │     │
    │  │ • test_file_path                                    │     │
    │  └────────────────────────────────────────────────────┘     │
    │  ┌────────────────────────────────────────────────────┐     │
    │  │ test_dependencies                                   │     │
    │  │ • test_id (FK)                                      │     │
    │  │ • referenced_class                                 │     │
    │  └────────────────────────────────────────────────────┘     │
    │  ┌────────────────────────────────────────────────────┐     │
    │  │ test_metadata                                       │     │
    │  │ • test_id (FK)                                      │     │
    │  │ • description, markers, etc.                        │     │
    │  └────────────────────────────────────────────────────┘     │
    └──────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 3: GIT DIFF PROCESSING                              │
└─────────────────────────────────────────────────────────────────────────────┘

    Git Diff File (diff_commit1.txt)
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 1: Read Git Diff (git_diff_processor.py)              │
    │  • Read diff file                                            │
    │  • Parse unified diff format                                 │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 2: Parse Git Diff (diff_parser.py)                    │
    │  • Extract changed files                                     │
    │  • Extract changed classes                                   │
    │  • Extract changed methods                                   │
    │  • Filter production Python files                            │
    │  • Extract module names from file paths                      │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Step 3: Build Search Queries (diff_parser.py)              │
    │  • Generate exact class matches                              │
    │  • Generate module patterns (agent.*, api.*)                 │
    │  • Generate test file candidates                             │
    └──────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 4: TEST SELECTION                                 │
└─────────────────────────────────────────────────────────────────────────────┘

    Search Queries
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Strategy 1: Direct Test Files (find_direct_test_files)    │
    │  • Match test file names (test_agent_pool.py)               │
    │  • Multi-strategy pattern matching                           │
    │  • Search by basename, full path, etc.                      │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Strategy 2: Integration/E2E Tests                         │
    │  • Find integration tests for changed modules                │
    │  • Query by test_type = 'integration' or 'e2e'              │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Strategy 3: Exact Matches (query_tests_for_classes)       │
    │  • Query reverse_index for exact class matches               │
    │  • Match sub-paths (api.routes → api.routes.get_agent)        │
    │  • Include string references (patch/Mock calls)             │
    │  • Prioritize exact matches over sub-paths                  │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Strategy 4: Module Patterns (query_tests_module_pattern)  │
    │  • Query for module patterns (agent.*)                      │
    │  • Prefer direct references over indirect                    │
    │  • Filter by specific classes if provided                   │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Aggregate Results (find_affected_tests)                    │
    │  • Combine all strategies                                    │
    │  • Deduplicate test IDs                                      │
    │  • Categorize by confidence (high/medium)                    │
    │  • Track match details for each test                         │
    └──────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 5: OUTPUT GENERATION                              │
└─────────────────────────────────────────────────────────────────────────────┘

    Test Selection Results
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Display Results (display_results)                           │
    │  • Show high confidence matches                              │
    │  • Show medium confidence matches                            │
    │  • Show unused tests                                         │
    │  • Display summary statistics                                │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  Save to File (save_results_to_file)                         │
    │  • Generate complete output file                             │
    │  • Include ALL tests (not truncated)                         │
    │  • Include match details                                     │
    │  • Include unused tests                                      │
    │  • Save to git_diff_processor/outputs/                       │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    Output File (test_selection_<diff_name>_<timestamp>.txt)
    • Complete test list
    • Match reasons
    • Test metadata
    • Summary statistics


┌─────────────────────────────────────────────────────────────────────────────┐
│                            KEY COMPONENTS                                    │
└─────────────────────────────────────────────────────────────────────────────┘

    AST Parser (ast_parser.py)
    • parse_file() - Parse Python files to AST
    • extract_imports() - Extract import statements
    • extract_string_references() - Extract patch()/Mock() calls
    • extract_classes() - Extract class definitions
    • extract_functions() - Extract function definitions

    Database Helpers (db_helpers.py)
    • get_tests_for_production_class() - Query tests for a class
    • batch_insert_test_registry() - Efficient batch inserts
    • batch_insert_reverse_index() - Batch insert reverse index

    Diff Parser (diff_parser.py)
    • parse_git_diff() - Parse git diff format
    • extract_production_classes_from_file() - Extract module names
    • extract_test_file_candidates() - Generate test file patterns
    • build_search_queries() - Build search strategy

    File Scanner (file_scanner.py)
    • scan_directory() - Recursively scan test repository
    • _categorize_directory() - Categorize test types
    • Multi-strategy test file discovery


┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA FLOW SUMMARY                                   │
└─────────────────────────────────────────────────────────────────────────────┘

    Test Files → AST Parsing → JSON Files → Database → Query → Results → Output

    Key Transformations:
    1. Test files → Test registry (test_id, class, method)
    2. Test files → Dependencies (test → production code)
    3. Dependencies → Reverse index (production code → tests)
    4. Git diff → Changed modules/classes
    5. Changed modules → Database queries → Affected tests
    6. Affected tests → Formatted output (console + file)
