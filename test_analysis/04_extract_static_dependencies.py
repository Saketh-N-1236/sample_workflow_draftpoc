"""
Step 4: Extract Static Dependencies

This script extracts static dependencies from test files.
It identifies which production code classes/modules each test references.

What it does:
1. Loads test registry from Step 3
2. Parses each test file using AST
3. Extracts import statements (from X import Y)
4. Extracts referenced classes in test code
5. Filters out test framework imports (pytest, unittest)
6. Builds test → production_code mapping
7. Displays dependency statistics
8. Saves dependencies to JSON file

Run this script:
    python test_analysis/04_extract_static_dependencies.py
"""

from pathlib import Path
import sys
import json

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.ast_parser import parse_file, extract_imports, extract_string_references
from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_progress, print_summary
)

# Configuration
OUTPUT_DIR = Path(__file__).parent / "outputs"
STEP3_OUTPUT = OUTPUT_DIR / "03_test_registry.json"
OUTPUT_FILE = OUTPUT_DIR / "04_static_dependencies.json"

# Test framework imports to exclude (these are not production code)
TEST_FRAMEWORK_IMPORTS = {
    'pytest', 'unittest', 'mock', 'unittest.mock',
    'pytest_mock', 'pytest_asyncio', 'pytest_cov',
    'test', 'tests', 'testing'
}


def is_production_import(import_name: str) -> bool:
    """
    Check if an import is likely production code (not test framework).
    
    Args:
        import_name: The import module name
    
    Returns:
        True if it's likely production code, False if it's test framework
    """
    # Check if it starts with any test framework name
    for test_framework in TEST_FRAMEWORK_IMPORTS:
        if import_name.startswith(test_framework):
            return False
    
    # Check if it's a standard library import (common ones)
    stdlib_modules = {
        'os', 'sys', 'pathlib', 'json', 'datetime', 'typing',
        'collections', 'itertools', 'functools', 'asyncio',
        'abc', 'dataclasses', 'enum', 'logging', 're'
    }
    
    # Split by dot to check first part
    first_part = import_name.split('.')[0]
    if first_part in stdlib_modules:
        return False  # Standard library, not production code
    
    return True


def extract_dependencies_from_file(filepath: Path) -> dict:
    """
    Extract dependencies from a single test file.
    
    Args:
        filepath: Path to the test file
    
    Returns:
        Dictionary with dependency information
    """
    tree = parse_file(filepath)
    if not tree:
        return {
            "file_path": str(filepath),
            "imports": [],
            "production_imports": [],
            "from_imports": []
        }
    
    # Extract all imports
    imports_data = extract_imports(tree)
    
    # Extract string-based references (patch() calls, etc.)
    string_refs = extract_string_references(tree)
    
    # Filter for production code imports
    all_imports = imports_data['all_imports']
    production_imports = [
        imp for imp in all_imports
        if is_production_import(imp)
    ]
    
    # Filter string references for production code
    production_string_refs = [
        ref for ref in string_refs
        if is_production_import(ref)
    ]
    
    # Filter from_imports for production code
    production_from_imports = []
    for module, names in imports_data['from_imports']:
        if module and is_production_import(module):
            production_from_imports.append((module, names))
    
    # Combine all production references (imports + string refs)
    all_production_refs = set(production_imports)
    all_production_refs.update(production_string_refs)
    # Also add module names from from_imports
    for module, _ in production_from_imports:
        all_production_refs.add(module)
    
    return {
        "file_path": str(filepath),
        "imports": all_imports,
        "production_imports": production_imports,
        "string_references": string_refs,  # NEW: All string refs
        "production_string_references": production_string_refs,  # NEW: Filtered string refs
        "from_imports": imports_data['from_imports'],
        "production_from_imports": production_from_imports,
        "all_production_references": sorted(list(all_production_refs))  # NEW: Combined refs
    }


def build_dependency_mapping() -> dict:
    """
    Build dependency mapping for all tests.
    
    Returns:
        Dictionary with test dependencies
    """
    # Load test registry from Step 3
    if not STEP3_OUTPUT.exists():
        print("Error: Step 3 output not found. Please run Step 3 first.")
        return {}
    
    with open(STEP3_OUTPUT, 'r', encoding='utf-8') as f:
        registry_data = json.load(f)['data']
    
    tests = registry_data['tests']
    test_files = set(t['file_path'] for t in tests)
    
    print_section(f"Processing {len(test_files)} test files...")
    
    # Extract dependencies for each file
    file_dependencies = {}
    for i, filepath_str in enumerate(test_files):
        print_progress(i + 1, len(test_files), "files")
        filepath = Path(filepath_str)
        file_dependencies[filepath_str] = extract_dependencies_from_file(filepath)
    
    print()  # New line after progress
    
    # Map dependencies to individual tests
    test_dependencies = []
    for test in tests:
        file_path = test['file_path']
        file_deps = file_dependencies.get(file_path, {})
        
        # Get production imports for this test
        production_imports = file_deps.get('production_imports', [])
        production_from_imports = file_deps.get('production_from_imports', [])
        production_string_refs = file_deps.get('production_string_references', [])
        
        # Extract all referenced classes/modules (imports + string refs)
        referenced_classes = set(production_imports)
        referenced_classes.update(production_string_refs)  # Add string-based references
        
        for module, names in production_from_imports:
            referenced_classes.add(module)
            # Also add individual names if they're classes
            referenced_classes.update(names)
        
        # Track reference types for each class
        reference_types = {}
        for ref in production_imports:
            reference_types[ref] = 'direct_import'
        for ref in production_string_refs:
            reference_types[ref] = 'string_ref'
        for module, _ in production_from_imports:
            if module not in reference_types:
                reference_types[module] = 'direct_import'
        
        test_dependencies.append({
            "test_id": test['test_id'],
            "file_path": file_path,
            "class_name": test.get('class_name'),
            "method_name": test['method_name'],
            "referenced_classes": sorted(list(referenced_classes)),
            "reference_types": reference_types,  # NEW: Track how each class is referenced
            "import_count": len(referenced_classes)
        })
    
    # Statistics
    total_references = sum(len(td['referenced_classes']) for td in test_dependencies)
    tests_with_deps = sum(1 for td in test_dependencies if td['import_count'] > 0)
    
    # Most referenced modules
    module_counts = {}
    for td in test_dependencies:
        for module in td['referenced_classes']:
            # Get top-level module
            top_module = module.split('.')[0]
            module_counts[top_module] = module_counts.get(top_module, 0) + 1
    
    top_modules = sorted(module_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "total_tests": len(test_dependencies),
        "tests_with_dependencies": tests_with_deps,
        "total_references": total_references,
        "average_references_per_test": round(total_references / len(test_dependencies), 2) if test_dependencies else 0,
        "top_modules": dict(top_modules),
        "test_dependencies": test_dependencies,
        "file_dependencies": file_dependencies
    }


def main():
    """Main function to extract static dependencies."""
    print_header("Step 4: Extracting Static Dependencies")
    print()
    
    # Step 1: Build dependency mapping
    print_section("Analyzing test files for dependencies...")
    dependency_data = build_dependency_mapping()
    
    if not dependency_data:
        print("Error: Failed to build dependency mapping!")
        return
    
    print()
    
    # Step 2: Display summary
    print_section("Dependency Summary:")
    print_summary({
        "total_tests": dependency_data['total_tests'],
        "tests_with_dependencies": dependency_data['tests_with_dependencies'],
        "total_references": dependency_data['total_references'],
        "average_references": dependency_data['average_references_per_test']
    })
    print()
    
    # Step 3: Display top modules
    print_section("Most Referenced Modules (Top 10):")
    for module, count in list(dependency_data['top_modules'].items())[:10]:
        print_item(f"{module}:", count)
    print()
    
    # Step 4: Display sample dependencies
    print_section("Sample Test Dependencies (first 5):")
    sample_tests = [td for td in dependency_data['test_dependencies'] if td['import_count'] > 0][:5]
    for test_dep in sample_tests:
        test_desc = test_dep['method_name']
        if test_dep['class_name']:
            test_desc = f"{test_dep['class_name']}.{test_desc}"
        print_item(f"{test_dep['test_id']} ({test_desc}):", 
                  f"{test_dep['import_count']} references")
        if test_dep['referenced_classes']:
            refs_preview = ', '.join(test_dep['referenced_classes'][:3])
            if len(test_dep['referenced_classes']) > 3:
                refs_preview += f", ... (+{len(test_dep['referenced_classes']) - 3} more)"
            print_item("  References:", refs_preview)
    print()
    
    # Step 5: Save to JSON
    print_section("Saving results...")
    save_json(dependency_data, OUTPUT_FILE)
    print()
    
    print_header("Step 4 Complete!")
    print(f"Extracted dependencies for {dependency_data['total_tests']} tests")
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
