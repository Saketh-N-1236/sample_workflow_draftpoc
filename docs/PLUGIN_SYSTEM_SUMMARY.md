# Plugin-Based Dependency Extraction System

## Overview

A language-agnostic plugin architecture for extracting and identifying production code dependencies from test files. This system replaces the previous generic approach with language-specific plugins that understand each language's import patterns, test frameworks, and production code identification rules.

## Architecture

### Base Plugin Interface (`base.py`)

All plugins inherit from `DependencyPlugin` and implement:

- `extract_imports()` - Extract import statements from source code
- `is_production_import()` - Identify production code vs test frameworks/stdlib
- `extract_class_name()` - Extract class/module names from imports
- `extract_string_references()` - Extract string-based references (e.g., patch() calls)
- `extract_dependencies()` - Main entry point that orchestrates all extraction

### Plugin Registry

- Auto-registers built-in plugins (Java, Python, JavaScript)
- Maps file extensions to plugins
- Provides fallback to universal parser if no plugin available

## Language-Specific Plugins

### Java Plugin (`java_plugin.py`)

**Handles:**
- `import com.example.Foo;`
- `import static com.example.Bar.*;`
- Wildcard imports

**Filters:**
- Standard library: `java.*`, `javax.*`, `sun.*`
- Test frameworks: `org.junit.*`, `org.testng.*`, `org.mockito.*`, etc.

**Extracts:**
- Class names from fully qualified imports (e.g., `com.strmecast.istream.request.LoginRequest` → `LoginRequest`)

### Python Plugin (`python_plugin.py`)

**Handles:**
- `import foo`
- `from bar import baz`
- `from foo.bar import baz, qux`

**Filters:**
- Standard library modules
- Test frameworks: `pytest`, `unittest`, `mock`, etc.

**Extracts:**
- Module/class names from imports

### JavaScript Plugin (`javascript_plugin.py`)

**Handles:**
- ES6 imports: `import Foo from 'module'`
- CommonJS: `require('module')`
- Dynamic imports: `import('module')`

**Filters:**
- Node.js standard library
- Test frameworks: `jest`, `mocha`, `chai`, etc.

**Extracts:**
- Module names from imports

## Integration

### Updated Files

1. **`test_analysis/04_extract_static_dependencies.py`**
   - Uses plugin registry to get language-specific plugin
   - Falls back to universal parser if no plugin available
   - Includes error handling and logging

2. **`test_analysis/utils/dependency_plugins/__init__.py`**
   - Exports `get_registry()` function
   - Auto-imports all built-in plugins

## Benefits

1. **Language-Specific Logic**: Each plugin understands its language's patterns
2. **Extensible**: Easy to add new languages by creating a plugin
3. **Accurate**: Java plugin correctly identifies `com.strmecast.istream.*` as production code
4. **Maintainable**: Language logic is isolated in plugins
5. **Robust**: Fallback to universal parser if plugin fails

## Usage

```python
from utils.dependency_plugins import get_registry

registry = get_registry()
plugin = registry.get_plugin_for_file(filepath)

if plugin:
    result = plugin.extract_dependencies(filepath)
    # result contains:
    # - imports: all imports
    # - production_imports: filtered production code imports
    # - production_classes: extracted class names
    # - string_references: string-based references
    # - all_production_references: combined production references
```

## Running the Analysis

```powershell
# Set schema for test repository
$env:TEST_REPO_SCHEMA="test_repo_17f1584c"

# Run dependency extraction
python test_analysis/04_extract_static_dependencies.py

# Build reverse index
python test_analysis/06_build_reverse_index.py

# Load into database
python deterministic/03_load_dependencies.py
python deterministic/04_load_reverse_index.py
```

## Future Enhancements

1. Add more language plugins (Kotlin, Go, Ruby, C#, etc.)
2. Support for package.json, pom.xml, requirements.txt parsing
3. Better string reference extraction
4. Plugin configuration files for custom rules
