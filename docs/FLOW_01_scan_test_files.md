# Flow Diagram: 01_scan_test_files.py

## Simple Flow

```
START
  │
  ▼
┌─────────────────────────────────┐
│ Check if test_repository exists │
└─────────────────────────────────┘
  │
  │ (if exists)
  ▼
┌─────────────────────────────────┐
│ Scan Directory (scan_directory) │
│ • Recursively walk directory    │
│ • Find test_*.py files          │
│ • Find *_test.py files          │
│ • Return list of test files     │
└─────────────────────────────────┘
  │
  │ [List of test file paths]
  ▼
┌─────────────────────────────────┐
│ Extract Metadata (for each file)│
│ • Get file path                 │
│ • Count lines                   │
│ • Get file size                 │
│ • Store metadata                │
└─────────────────────────────────┘
  │
  │ [List of file metadata]
  ▼
┌─────────────────────────────────┐
│ Group Files by Category         │
│ • unit/ directory → unit        │
│ • integration/ → integration   │
│ • e2e/ → e2e                   │
│ • others → other               │
└─────────────────────────────────┘
  │
  │ [Grouped files by category]
  ▼
┌─────────────────────────────────┐
│ Prepare Output Data             │
│ • Total files count            │
│ • Total lines count            │
│ • Total size                   │
│ • Categories breakdown         │
│ • All file metadata            │
└─────────────────────────────────┘
  │
  │ [Output dictionary]
  ▼
┌─────────────────────────────────┐
│ Save to JSON File               │
│ • 01_test_files.json           │
│ • Save in outputs/ directory   │
└─────────────────────────────────┘
  │
  ▼
END
```

## Detailed Steps

```
1. START
   │
   ├─> Check: Does test_repository/ exist?
   │   │
   │   ├─> NO → Print error, EXIT
   │   │
   │   └─> YES → Continue
   │
2. Scan Directory
   │
   ├─> Walk through test_repository/
   │   │
   │   ├─> Check each file:
   │   │   │
   │   │   ├─> Matches test_*.py? → Add to list
   │   │   │
   │   │   └─> Matches *_test.py? → Add to list
   │   │
   │   └─> Return: [file1, file2, file3, ...]
   │
3. Extract Metadata (for each file)
   │
   ├─> For each test file:
   │   │
   │   ├─> Get file path
   │   ├─> Count lines (read file)
   │   ├─> Get file size (bytes)
   │   └─> Create metadata dict
   │
   └─> Return: [{path, line_count, size_bytes}, ...]
   │
4. Group by Category
   │
   ├─> Check file path:
   │   │
   │   ├─> Contains "unit" → unit category
   │   ├─> Contains "integration" → integration category
   │   ├─> Contains "e2e" → e2e category
   │   └─> Otherwise → other category
   │
   └─> Return: {unit: [...], integration: [...], e2e: [...], other: [...]}
   │
5. Prepare Output
   │
   ├─> Calculate totals:
   │   ├─> total_files = count of files
   │   ├─> total_lines = sum of all line counts
   │   └─> total_size = sum of all file sizes
   │
   └─> Create output dict with all data
   │
6. Save to JSON
   │
   ├─> Create outputs/ directory (if needed)
   ├─> Write JSON file: 01_test_files.json
   └─> Print success message
   │
7. END
```

## Input/Output

**Input:**
- Directory: `test_repository/`

**Output:**
- JSON File: `test_analysis/outputs/01_test_files.json`
- Contains:
  ```json
  {
    "scan_directory": "path/to/test_repository",
    "total_files": 18,
    "total_lines": 5000,
    "total_size_bytes": 150000,
    "categories": {
      "unit": 13,
      "integration": 3,
      "e2e": 2,
      "other": 0
    },
    "files": [
      {
        "path": "test_repository/unit/test_agent.py",
        "line_count": 150,
        "size_bytes": 5000
      },
      ...
    ]
  }
  ```

## Key Functions Used

- `scan_directory()` - Scans directory for test files
- `get_file_metadata()` - Extracts file metadata
- `group_files_by_category()` - Groups files by test type
- `save_json()` - Saves data to JSON file
