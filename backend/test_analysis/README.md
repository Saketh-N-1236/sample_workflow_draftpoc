# Test Repository Analysis System

A step-by-step analysis tool for processing test repositories. Each step is implemented as a separate, runnable file with clear outputs.

## Overview

This system analyzes test repositories to extract:
- Test file inventory
- Framework detection
- Test registry (classes and methods)
- Static dependencies (test → production code)
- Test metadata (descriptions, markers, patterns)
- Reverse index (production code → tests)
- Test structure mapping
- Comprehensive summary report

## Project Structure

```
test_analysis/
├── __init__.py
├── 01_scan_test_files.py          # Step 1: Discover all test files
├── 02_detect_framework.py         # Step 2: Identify test framework
├── 03_build_test_registry.py       # Step 3: Create test inventory
├── 04_extract_static_dependencies.py  # Step 4: Extract imports/dependencies
├── 05_extract_test_metadata.py    # Step 5: Extract test metadata
├── 06_build_reverse_index.py      # Step 6: Create reverse index
├── 07_map_test_structure.py       # Step 7: Map directory structure
├── 08_generate_summary.py          # Step 8: Generate summary report
├── utils/
│   ├── __init__.py
│   ├── file_scanner.py            # File scanning utilities
│   ├── ast_parser.py              # AST parsing utilities
│   └── output_formatter.py        # Output formatting utilities
├── outputs/                        # Generated output files
│   ├── 01_test_files.json
│   ├── 02_framework_detection.json
│   ├── 03_test_registry.json
│   ├── 04_static_dependencies.json
│   ├── 05_test_metadata.json
│   ├── 06_reverse_index.json
│   ├── 07_test_structure.json
│   └── 08_summary_report.json
└── requirements.txt
```

## Usage

### Running Individual Steps

Each step can be run independently:

```bash
# Step 1: Scan test files
python test_analysis/01_scan_test_files.py

# Step 2: Detect framework
python test_analysis/02_detect_framework.py

# Step 3: Build test registry
python test_analysis/03_build_test_registry.py

# Step 4: Extract static dependencies
python test_analysis/04_extract_static_dependencies.py

# Step 5: Extract test metadata
python test_analysis/05_extract_test_metadata.py

# Step 6: Build reverse index
python test_analysis/06_build_reverse_index.py

# Step 7: Map test structure
python test_analysis/07_map_test_structure.py

# Step 8: Generate summary
python test_analysis/08_generate_summary.py
```

### Running All Steps

You can run all steps sequentially:

```bash
python test_analysis/01_scan_test_files.py
python test_analysis/02_detect_framework.py
python test_analysis/03_build_test_registry.py
python test_analysis/04_extract_static_dependencies.py
python test_analysis/05_extract_test_metadata.py
python test_analysis/06_build_reverse_index.py
python test_analysis/07_map_test_structure.py
python test_analysis/08_generate_summary.py
```

## Step Descriptions

### Step 1: Scan Test Files
- Recursively scans the test repository
- Identifies test files (test_*.py, *_test.py patterns)
- Extracts file metadata (size, line count)
- Categorizes by directory (unit, integration, e2e)
- **Output**: `01_test_files.json`

### Step 2: Detect Framework
- Checks for pytest.ini, setup.cfg, pyproject.toml
- Analyzes conftest.py
- Scans test files for framework patterns
- Determines primary framework (pytest/unittest)
- **Output**: `02_framework_detection.json`

### Step 3: Build Test Registry
- Parses each test file using AST
- Extracts test classes (class Test*)
- Extracts test methods (def test_*)
- Generates unique test IDs
- **Output**: `03_test_registry.json`

### Step 4: Extract Static Dependencies
- Parses imports from test files
- Filters out test framework imports
- Identifies production code references
- Builds test → production_code mapping
- **Output**: `04_static_dependencies.json`

### Step 5: Extract Test Metadata
- Extracts test names and descriptions
- Identifies pytest markers
- Detects async tests
- Identifies parameterized tests
- Analyzes test naming patterns
- **Output**: `05_test_metadata.json`

### Step 6: Build Reverse Index
- Inverts dependency mapping
- Creates production_code → [tests] index
- Groups by production module
- **Output**: `06_reverse_index.json`

### Step 7: Map Test Structure
- Analyzes directory hierarchy
- Maps package organization
- Identifies shared utilities (conftest.py, fixtures)
- **Output**: `07_test_structure.json`

### Step 8: Generate Summary
- Combines all previous outputs
- Generates statistics and insights
- Creates comprehensive report
- **Output**: `08_summary_report.json`

## Output Format

Each step produces:
1. **Console Output**: Human-readable progress and results
2. **JSON File**: Structured data saved to `outputs/` directory

### JSON Structure

All JSON files follow this structure:
```json
{
  "generated_at": "2024-01-01T12:00:00",
  "data": {
    // Step-specific data
  }
}
```

## Requirements

- Python 3.7+
- Standard library only (no external dependencies required)

Optional (for enhanced features):
- `ast-comments` for advanced docstring extraction

## Features

- **Beginner-Friendly**: Extensive comments explaining each step
- **Modular Design**: Each step is independent and can run separately
- **Clear Output**: Both console and JSON outputs for each step
- **Progress Indicators**: Shows progress for long-running operations
- **Error Handling**: Graceful error handling with clear messages
- **Data Validation**: Validates outputs before saving

## Example Output

### Step 1 Example:
```
==================================================
Step 1: Scanning Test Files
==================================================

  Scanning directory: test_repository
  Found test files: 15
  
  Summary:
    Total Files: 15
    Total Lines: 2809
    Unit Tests: 11
    Integration Tests: 2
    E2E Tests: 1
```

### Step 8 Example:
```
==================================================
ALL ANALYSIS STEPS COMPLETE!
==================================================

Summary:
  - 15 test files analyzed
  - 95 tests registered
  - 49 production classes mapped
  - Framework: pytest (high confidence)
```

## Next Steps

After completing all 8 steps, you have:
- Complete test inventory
- Test-to-code dependency mappings
- Reverse index for fast lookups
- Test metadata and characteristics
- Repository structure analysis

This foundation is ready for:
- Embedding generation (for semantic search)
- Coverage data integration
- Git history analysis
- Vector database population
- Test selection algorithms

## Troubleshooting

### Import Errors
If you encounter import errors, ensure you're running from the project root:
```bash
cd /path/to/project
python test_analysis/01_scan_test_files.py
```

### Missing Step Outputs
Some steps depend on previous steps:
- Step 3 needs Step 1 (or will scan directly)
- Step 4 needs Step 3
- Step 5 needs Step 3
- Step 6 needs Step 4
- Step 8 needs all previous steps

### File Not Found Errors
Ensure the test repository exists at:
```
/path/to/project/test_repository/
```

## Contributing

When adding new analysis steps:
1. Create a new numbered file (e.g., `09_new_analysis.py`)
2. Use utilities from `utils/` directory
3. Follow the output format (console + JSON)
4. Add extensive comments for beginners
5. Update this README

## License

This is part of the Test Impact Analysis platform project.
