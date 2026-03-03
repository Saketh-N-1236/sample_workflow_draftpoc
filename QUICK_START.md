# Quick Start Guide - Test Impact Analysis System

## ✅ System Capabilities

**Yes, this system works on ANY repository and ANY git changes!**

### Supported Features:
- ✅ **Multi-language support**: Python, JavaScript, Java, TypeScript (via Tree-sitter)
- ✅ **Configurable repository paths**: Use environment variables
- ✅ **Any git diff format**: Works with any git diff output
- ✅ **Language-agnostic parsing**: Automatically detects and parses different languages
- ✅ **Dynamic test discovery**: Finds tests regardless of repository structure

---

## 🚀 Complete Pipeline Commands

### Step 1: Configure Repository Path (Optional)

If your test repository is not in the default `test_repository` folder:

```powershell
# Windows PowerShell
$env:TEST_REPO_PATH = "C:\path\to\your\test\repository"

# Or set project root if different
$env:PROJECT_ROOT = "C:\path\to\your\project\root"
```

```bash
# Linux/Mac
export TEST_REPO_PATH="/path/to/your/test/repository"
export PROJECT_ROOT="/path/to/your/project/root"
```

### Step 2: Test Analysis Pipeline

Run these commands in order to analyze your test repository:

```powershell
# 1. Scan test files
python test_analysis/01_scan_test_files.py

# 2. Detect test framework
python test_analysis/02_detect_framework.py

# 3. Build test registry
python test_analysis/03_build_test_registry.py

# 4. Extract static dependencies
python test_analysis/04_extract_static_dependencies.py

# 5. Extract function calls
python test_analysis/04b_extract_function_calls.py

# 6. Extract test metadata
python test_analysis/05_extract_test_metadata.py

# 7. Build reverse index
python test_analysis/06_build_reverse_index.py

# 8. Map test structure
python test_analysis/07_map_test_structure.py

# 9. Generate summary report
python test_analysis/08_generate_summary.py
```

### Step 3: Load Data into Database

```powershell
# 1. Create database tables
python deterministic/01_create_tables.py

# 2. Load test registry
python deterministic/02_load_test_registry.py

# 3. Load dependencies
python deterministic/03_load_dependencies.py

# 4. Load function mappings
python deterministic/04b_load_function_mappings.py

# 5. Load metadata
python deterministic/05_load_metadata.py

# 6. Load reverse index
python deterministic/04_load_reverse_index.py

# 7. Load test structure
python deterministic/06_load_structure.py

# 8. Verify data
python deterministic/07_verify_data.py
```

### Step 4: Generate Embeddings (Optional - for Semantic Search)

```powershell
# Generate embeddings for semantic search
python semantic_retrieval/09_generate_embeddings.py
```

### Step 5: Process Git Diff and Select Tests

```powershell
# Option 1: Process the sample git diff file
python git_diff_processor/git_diff_processor.py git_diff_processor/sample_diffs/diff_commit1.txt

# Option 2: Process git diff from command line
git diff HEAD~1 HEAD > my_diff.txt
python git_diff_processor/git_diff_processor.py my_diff.txt

# Option 3: Process diff between two commits
git diff commit1 commit2 > my_diff.txt
python git_diff_processor/git_diff_processor.py my_diff.txt

# Option 4: Process diff for specific files
git diff HEAD -- path/to/file1.py path/to/file2.js > my_diff.txt
python git_diff_processor/git_diff_processor.py my_diff.txt
```

---

## 📋 One-Line Commands (Full Pipeline)

### Windows PowerShell - Full Pipeline

```powershell
# Set repository path (if needed)
$env:TEST_REPO_PATH = "C:\path\to\your\tests"

# Run complete pipeline
python test_analysis/01_scan_test_files.py; python test_analysis/02_detect_framework.py; python test_analysis/03_build_test_registry.py; python test_analysis/04_extract_static_dependencies.py; python test_analysis/04b_extract_function_calls.py; python test_analysis/05_extract_test_metadata.py; python test_analysis/06_build_reverse_index.py; python test_analysis/07_map_test_structure.py; python test_analysis/08_generate_summary.py; python deterministic/01_create_tables.py; python deterministic/02_load_test_registry.py; python deterministic/03_load_dependencies.py; python deterministic/04b_load_function_mappings.py; python deterministic/05_load_metadata.py; python deterministic/04_load_reverse_index.py; python deterministic/06_load_structure.py; python deterministic/07_verify_data.py; python semantic_retrieval/09_generate_embeddings.py
```

### Linux/Mac - Full Pipeline

```bash
# Set repository path (if needed)
export TEST_REPO_PATH="/path/to/your/tests"

# Run complete pipeline
python test_analysis/01_scan_test_files.py && \
python test_analysis/02_detect_framework.py && \
python test_analysis/03_build_test_registry.py && \
python test_analysis/04_extract_static_dependencies.py && \
python test_analysis/04b_extract_function_calls.py && \
python test_analysis/05_extract_test_metadata.py && \
python test_analysis/06_build_reverse_index.py && \
python test_analysis/07_map_test_structure.py && \
python test_analysis/08_generate_summary.py && \
python deterministic/01_create_tables.py && \
python deterministic/02_load_test_registry.py && \
python deterministic/03_load_dependencies.py && \
python deterministic/04b_load_function_mappings.py && \
python deterministic/05_load_metadata.py && \
python deterministic/04_load_reverse_index.py && \
python deterministic/06_load_structure.py && \
python deterministic/07_verify_data.py && \
python semantic_retrieval/09_generate_embeddings.py
```

---

## 🔧 Working with Any Repository

### Example 1: Different Test Repository Location

```powershell
# Point to your actual test repository
$env:TEST_REPO_PATH = "C:\MyProject\tests"
python test_analysis/03_build_test_registry.py
```

### Example 2: Different Project Root

```powershell
# Set project root for module resolution
$env:PROJECT_ROOT = "C:\MyProject\src"
python test_analysis/04_extract_static_dependencies.py
```

### Example 3: Process Any Git Diff

```powershell
# From any git repository
cd C:\MyProject
git diff origin/main HEAD > changes.diff
python C:\path\to\sample_workflow\git_diff_processor\git_diff_processor.py changes.diff
```

---

## 📝 Git Diff Examples

### Example 1: Diff between commits
```powershell
git diff abc123 def456 > diff.txt
python git_diff_processor/git_diff_processor.py diff.txt
```

### Example 2: Diff for specific branch
```powershell
git diff main feature-branch > diff.txt
python git_diff_processor/git_diff_processor.py diff.txt
```

### Example 3: Diff for staged changes
```powershell
git diff --cached > diff.txt
python git_diff_processor/git_diff_processor.py diff.txt
```

### Example 4: Diff for working directory
```powershell
git diff > diff.txt
python git_diff_processor/git_diff_processor.py diff.txt
```

---

## 🌍 Multi-Language Support

The system automatically detects and parses:
- **Python** (.py files)
- **JavaScript** (.js, .jsx files)
- **Java** (.java files)
- **TypeScript** (.ts, .tsx files)

No configuration needed! The parser registry automatically selects the correct parser.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEST_REPO_PATH` | Path to test repository | `test_repository/` |
| `PROJECT_ROOT` | Path to project root | Parent of `test_analysis/` |
| `LANGUAGE_CONFIG_PATH` | Path to language config | `config/language_configs.yaml` |

### Database Configuration

Edit `.env` file or set environment variables:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=test_impact_analysis
DB_USER=your_user
DB_PASSWORD=your_password
```

---

## 📊 Output Files

All outputs are saved in:
- `test_analysis/outputs/` - Analysis results (JSON)
- `git_diff_processor/outputs/` - Test selection results (JSON + TXT)
- Database tables - Persistent storage

---

## ✅ Verification

After running the pipeline, verify everything worked:

```powershell
# Check test registry
python deterministic/07_verify_data.py

# Check outputs
ls test_analysis/outputs/
ls git_diff_processor/outputs/
```

---

## 🐛 Troubleshooting

### Issue: "No test files found!"
**Solution**: Set `TEST_REPO_PATH` environment variable to point to your test repository.

### Issue: "Database connection error"
**Solution**: Check `.env` file or database connection settings in `deterministic/db_connection.py`.

### Issue: "Parser not found for language X"
**Solution**: The system will fall back to regex-based parsing. For better support, install Tree-sitter:
```powershell
pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-java
```

---

## 📚 Next Steps

1. **Customize language config**: Edit `config/language_configs.yaml` for your project structure
2. **Add custom parsers**: Implement `LanguageParser` interface for new languages
3. **Configure semantic search**: Set up embeddings for better test selection
4. **Integrate with CI/CD**: Use git diff processor in your CI pipeline

---

## 🎯 Summary

**Yes, the system works on ANY repository and ANY git changes!**

- ✅ Configure repository path via `TEST_REPO_PATH`
- ✅ Works with any git diff format
- ✅ Supports multiple languages automatically
- ✅ No hardcoded paths or assumptions
- ✅ Fully configurable and extensible

Just set the environment variables and run the commands!
