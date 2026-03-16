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
import logging

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)

from utils.language_parser import parse_file, extract_imports, extract_string_references
from utils.universal_parser import get_parser, detect_language
from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_progress, print_summary
)
from utils.config import get_output_dir
from utils.dependency_plugins import get_registry

# Configuration
OUTPUT_DIR = get_output_dir()
STEP3_OUTPUT = OUTPUT_DIR / "03_test_registry.json"
OUTPUT_FILE = OUTPUT_DIR / "04_static_dependencies.json"

# Universal test framework imports to exclude (language-agnostic)
TEST_FRAMEWORK_IMPORTS = {
    'pytest', 'unittest', 'mock', 'unittest.mock',
    'pytest_mock', 'pytest_asyncio', 'pytest_cov',
    'test', 'tests', 'testing',
    # JavaScript/Node.js test frameworks
    'jest', 'mocha', 'chai', 'sinon', 'supertest', 'express',
    'ava', 'tape', 'jasmine', 'vitest',
    # Java test frameworks
    'junit', 'testng', 'mockito', 'hamcrest', 'assertj',
    'org.junit', 'org.testng', 'org.mockito',
    # Other
    'rspec', 'minitest', 'nunit', 'xunit', 'testing'
}


def is_production_import(import_name: str, language: str = 'python') -> bool:
    """
    Language-aware check if an import is likely production code (not test framework).
    
    Args:
        import_name: The import module name
        language: Programming language (python, java, javascript, etc.)
    
    Returns:
        True if it's likely production code, False if it's test framework
    """
    import_lower = import_name.lower()
    
    # Universal test framework exclusions
    TEST_KEYWORDS = {
        'pytest', 'unittest', 'mock', 'junit', 'testng', 'mockito',
        'hamcrest', 'assertj', 'jest', 'mocha', 'chai', 'sinon',
        'jasmine', 'vitest', 'rspec', 'minitest', 'nunit', 'xunit',
        'testing', 'test', 'spec'
    }
    
    # Java-specific: exclude java.* and javax.* standard library
    if language == 'java':
        first_part = import_name.split('.')[0]
        # Exclude standard library (java.*, javax.*, sun.*)
        if first_part in ('java', 'javax', 'sun', 'com.sun'):
            return False
        # Exclude test framework packages (org.junit.*, org.testng.*, org.mockito.*, etc.)
        if import_lower.startswith('org.junit') or import_lower.startswith('org.testng') or \
           import_lower.startswith('org.mockito') or import_lower.startswith('org.hamcrest') or \
           import_lower.startswith('org.assertj') or import_lower.startswith('junit') or \
           'mockito' in import_lower or 'hamcrest' in import_lower or 'assertj' in import_lower:
            return False
        # For Java, if it's not standard library or test framework, it's likely production code
        # Don't filter based on generic 'test' keyword - Java packages can have 'test' in them
        return True
    
    # Python standard library check
    if language == 'python':
        stdlib = {'os', 'sys', 'pathlib', 'json', 'datetime', 'typing',
                  'collections', 'itertools', 'functools', 'asyncio',
                  'abc', 'dataclasses', 'enum', 'logging', 're', 'io',
                  'time', 'copy', 'math', 'random', 'string', 'struct'}
        first_part = import_name.split('.')[0]
        if first_part in stdlib:
            return False
    
    # Check against test keywords (but be lenient for Java - only check if it's clearly a test framework)
    parts = import_name.lower().replace('/', '.').split('.')
    # For Java, we already handled test frameworks above, so skip generic test keyword check
    if language == 'java':
        return True  # Already filtered test frameworks above
    # For other languages, check for test keywords
    return not any(kw in parts for kw in TEST_KEYWORDS)


def extract_dependencies_from_file(filepath: Path) -> dict:
    """
    Extract dependencies from a single test file using language-specific plugins.
    
    Args:
        filepath: Path to the test file
    
    Returns:
        Dictionary with dependency information
    """
    # Get language-specific plugin
    try:
        registry = get_registry()
        plugin = registry.get_plugin_for_file(filepath)
        
        if plugin:
            # Use plugin for language-specific extraction
            result = plugin.extract_dependencies(filepath)
            # Add backward compatibility fields
            result['from_imports'] = []  # Not used for non-Python languages
            logger.debug(f"Plugin {plugin.language} extracted {len(result.get('production_imports', []))} production imports from {filepath.name}")
            return result
    except Exception as e:
        logger.warning(f"Plugin extraction failed for {filepath.name}: {e}, falling back to universal parser")
    
    # Fallback to universal parser if no plugin available or plugin failed
    try:
        language = detect_language(filepath)
        parser = get_parser()
        parsed = parser.parse_file(filepath)
        
        all_imports = parsed.get('imports', [])
        
        if parsed.get('error'):
            return {
                "file_path": str(filepath),
                "language": language,
                "imports": [],
                "production_imports": [],
                "production_classes": [],
                "total_import_count": 0,
                "production_import_count": 0,
                "string_references": [],
                "production_string_references": [],
                "from_imports": [],
                "all_production_references": []
            }
        
        # Filter for production code (not test frameworks)
        production_imports = [imp for imp in all_imports if is_production_import(imp, language)]
        
        # Extract string-based references (patch() calls, etc.) - try language parser as fallback
        string_refs = []
        try:
            tree = parse_file(filepath)
            if tree:
                string_refs = extract_string_references(tree, filepath)
        except Exception:
            pass  # Not critical if this fails
        
        # Filter string references for production code
        production_string_refs = [
            ref for ref in string_refs
            if is_production_import(ref, language)
        ]
        
        # Combine all production references (imports + string refs)
        all_production_refs = set(production_imports)
        all_production_refs.update(production_string_refs)
        
        return {
            "file_path": str(filepath),
            "language": language,
            "imports": all_imports,
            "production_imports": production_imports,
            "production_classes": [],
            "string_references": string_refs,
            "production_string_references": production_string_refs,
            "from_imports": [],
            "total_import_count": len(all_imports),
            "production_import_count": len(production_imports),
            "all_production_references": sorted(list(all_production_refs))
        }
    except Exception as e:
        logger.error(f"Failed to extract dependencies from {filepath.name}: {e}")
        # Return empty result on error
        language = detect_language(filepath)
        return {
            "file_path": str(filepath),
            "language": language,
            "imports": [],
            "production_imports": [],
            "production_classes": [],
            "total_import_count": 0,
            "production_import_count": 0,
            "string_references": [],
            "production_string_references": [],
            "from_imports": [],
            "all_production_references": []
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
        production_classes = file_deps.get('production_classes', [])  # Extracted class names from plugins
        production_from_imports = file_deps.get('production_from_imports', [])
        production_string_refs = file_deps.get('production_string_references', [])
        
        # Extract all referenced classes/modules (imports + string refs + extracted classes)
        referenced_classes = set(production_imports)  # Full import paths
        referenced_classes.update(production_string_refs)  # Add string-based references
        referenced_classes.update(production_classes)  # Add extracted class names (e.g., "LoginRequest")
        
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
        
        # Get total imports (including test framework) for debugging
        all_imports = file_deps.get('imports', [])
        
        test_dependencies.append({
            "test_id": test['test_id'],
            "file_path": file_path,
            "class_name": test.get('class_name'),
            "method_name": test['method_name'],
            "referenced_classes": sorted(list(referenced_classes)),
            "reference_types": reference_types,  # NEW: Track how each class is referenced
            "import_count": len(all_imports),  # Total imports (including test framework)
            "production_import_count": len(referenced_classes)  # Production imports only
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
