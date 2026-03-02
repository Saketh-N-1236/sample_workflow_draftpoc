"""
Step 4b: Extract Function Calls

This script extracts function-level mappings from test files.
It identifies which specific functions each test calls or patches.

What it does:
1. Loads test registry from Step 3
2. Parses each test file using AST
3. Extracts function calls from test method bodies (e.g., agent.initialize())
4. Extracts string references from patch() calls (e.g., 'agent.langgraph_agent.initialize')
5. Maps test → module.function relationships
6. Displays function call statistics
7. Saves mappings to JSON file

Run this script:
    python test_analysis/04b_extract_function_calls.py
"""

from pathlib import Path
import sys
import json
from typing import Optional

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.ast_parser import parse_file, extract_function_calls, extract_string_references
from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_progress, print_summary
)

# Configuration
OUTPUT_DIR = Path(__file__).parent / "outputs"
STEP3_OUTPUT = OUTPUT_DIR / "03_test_registry.json"
OUTPUT_FILE = OUTPUT_DIR / "04b_function_calls.json"

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


def extract_function_from_string_ref(string_ref: str) -> tuple:
    """
    Extract module and function name from a string reference.
    
    Examples:
        'agent.langgraph_agent.initialize' → ('agent.langgraph_agent', 'initialize')
        'agent.langgraph_agent.LangGraphAgent' → ('agent.langgraph_agent', 'LangGraphAgent')
        'agent' → (None, None)  # Too short, likely not a function
    
    Args:
        string_ref: String reference like 'agent.langgraph_agent.initialize'
    
    Returns:
        Tuple of (module_name, function_name) or (None, None) if can't parse
    """
    if not string_ref or '.' not in string_ref:
        return (None, None)
    
    # Split on last dot to separate module from function/class
    parts = string_ref.rsplit('.', 1)
    if len(parts) != 2:
        return (None, None)
    
    module_name, function_name = parts
    
    # Filter out non-production modules
    if not is_production_import(module_name):
        return (None, None)
    
    # Module should have at least one dot (e.g., 'agent.langgraph_agent')
    # Single word like 'agent' is too broad
    if '.' not in module_name:
        return (None, None)
    
    return (module_name, function_name)


def resolve_object_to_module(object_name: str, imports_data: dict, file_path: str) -> Optional[str]:
    """
    Attempt to resolve an object name to its module.
    
    For example, if test has 'from agent.langgraph_agent import LangGraphAgent'
    and calls 'agent.initialize()', try to resolve 'agent' to 'agent.langgraph_agent'.
    
    This is a best-effort approach. For MVP, we'll store the object name as-is
    and rely on string references for precise matching.
    
    Args:
        object_name: Object name (e.g., 'agent')
        imports_data: Import data from extract_imports()
        file_path: Path to test file (for context)
    
    Returns:
        Module name if resolved, None otherwise
    """
    # Check from_imports for exact match
    for module, names in imports_data.get('from_imports', []):
        if object_name in names and is_production_import(module):
            return module
    
    # Check if object_name matches a class name in imports
    # This is heuristic - in real code, we'd need more sophisticated analysis
    return None


def extract_function_mappings_from_file(filepath: Path, test_methods: list, imports_data: dict) -> list:
    """
    Extract function-level mappings from a test file.
    
    Args:
        filepath: Path to the test file
        test_methods: List of test method names in this file
        imports_data: Import data for resolving object names
    
    Returns:
        List of function mapping dictionaries
    """
    tree = parse_file(filepath)
    if not tree:
        return []
    
    mappings = []
    
    # Extract function calls from test methods
    function_calls = extract_function_calls(tree)
    
    # Create a map of test_method -> calls
    calls_by_method = {fc['test_method']: fc['calls'] for fc in function_calls}
    
    # Extract string references (patch() calls)
    string_refs = extract_string_references(tree)
    
    # Process each test method
    for test_method in test_methods:
        # Get function calls for this test method
        calls = calls_by_method.get(test_method, [])
        
        # Process direct calls and method calls
        for call in calls:
            function_name = call['function']
            object_name = call.get('object')
            call_type = call['type']
            
            # Try to resolve object to module
            module_name = None
            if object_name:
                module_name = resolve_object_to_module(object_name, imports_data, filepath)
            
            # If we couldn't resolve, we'll store it with object_name
            # The database query can match on function_name alone
            mappings.append({
                'test_method': test_method,
                'function_name': function_name,
                'module_name': module_name,  # May be None
                'object_name': object_name,  # For context
                'call_type': call_type,  # 'direct' or 'method'
                'source': 'method_call',
                'line_number': call.get('line_number')
            })
        
        # Process string references (patch() calls)
        # These are more precise - they have full module.function paths
        for string_ref in string_refs:
            module_name, function_name = extract_function_from_string_ref(string_ref)
            
            if module_name and function_name:
                mappings.append({
                    'test_method': test_method,
                    'function_name': function_name,
                    'module_name': module_name,
                    'object_name': None,
                    'call_type': 'patch_ref',
                    'source': 'patch_ref',
                    'line_number': None
                })
    
    return mappings


def build_function_mapping() -> dict:
    """
    Build function-level mapping for all tests.
    
    Returns:
        Dictionary with function mapping data
    """
    # Load test registry from Step 3
    if not STEP3_OUTPUT.exists():
        print("Error: Step 3 output not found. Please run Step 3 first.")
        return {}
    
    with open(STEP3_OUTPUT, 'r', encoding='utf-8') as f:
        registry_data = json.load(f)['data']
    
    tests = registry_data['tests']
    test_files = {}
    
    # Group tests by file
    for test in tests:
        file_path = test['file_path']
        if file_path not in test_files:
            test_files[file_path] = []
        test_files[file_path].append(test)
    
    print_section(f"Processing {len(test_files)} test files...")
    
    # Extract function mappings for each file
    all_mappings = []
    file_mappings = {}
    
    for i, (filepath_str, file_tests) in enumerate(test_files.items()):
        print_progress(i + 1, len(test_files), "files")
        
        filepath = Path(filepath_str)
        
        # Get imports for this file (to help resolve object names)
        tree = parse_file(filepath)
        imports_data = {}
        if tree:
            from utils.ast_parser import extract_imports
            imports_data = extract_imports(tree)
        
        # Get test method names
        test_method_names = [t['method_name'] for t in file_tests]
        
        # Extract function mappings
        file_function_mappings = extract_function_mappings_from_file(
            filepath, test_method_names, imports_data
        )
        
        # Map to test_ids
        for mapping in file_function_mappings:
            # Find the test that corresponds to this method
            matching_test = next(
                (t for t in file_tests if t['method_name'] == mapping['test_method']),
                None
            )
            
            if matching_test:
                all_mappings.append({
                    'test_id': matching_test['test_id'],
                    'file_path': filepath_str,
                    'class_name': matching_test.get('class_name'),
                    'method_name': mapping['test_method'],
                    'module_name': mapping['module_name'],
                    'function_name': mapping['function_name'],
                    'object_name': mapping.get('object_name'),
                    'call_type': mapping['call_type'],
                    'source': mapping['source'],
                    'line_number': mapping.get('line_number')
                })
        
        file_mappings[filepath_str] = file_function_mappings
    
    print()  # New line after progress
    
    # Statistics
    total_mappings = len(all_mappings)
    tests_with_function_calls = len(set(m['test_id'] for m in all_mappings))
    
    # Count by source type
    by_source = {}
    for mapping in all_mappings:
        source = mapping['source']
        by_source[source] = by_source.get(source, 0) + 1
    
    # Count by call type
    by_call_type = {}
    for mapping in all_mappings:
        call_type = mapping['call_type']
        by_call_type[call_type] = by_call_type.get(call_type, 0) + 1
    
    # Most called functions
    function_counts = {}
    for mapping in all_mappings:
        if mapping['module_name'] and mapping['function_name']:
            key = f"{mapping['module_name']}.{mapping['function_name']}"
            function_counts[key] = function_counts.get(key, 0) + 1
    
    top_functions = sorted(function_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "total_tests": len(tests),
        "tests_with_function_calls": tests_with_function_calls,
        "total_mappings": total_mappings,
        "average_mappings_per_test": round(total_mappings / len(tests), 2) if tests else 0,
        "mappings_by_source": by_source,
        "mappings_by_call_type": by_call_type,
        "top_functions": dict(top_functions),
        "test_function_mappings": all_mappings
    }


def main():
    """Main function to extract function calls."""
    print_header("Step 4b: Extracting Function Calls")
    print()
    
    # Step 1: Build function mapping
    print_section("Analyzing test files for function calls...")
    mapping_data = build_function_mapping()
    
    if not mapping_data:
        print("Error: Failed to build function mapping!")
        return
    
    print()
    
    # Step 2: Display summary
    print_section("Function Mapping Summary:")
    print_summary({
        "total_tests": mapping_data['total_tests'],
        "tests_with_function_calls": mapping_data['tests_with_function_calls'],
        "total_mappings": mapping_data['total_mappings'],
        "average_mappings_per_test": mapping_data['average_mappings_per_test']
    })
    print()
    
    # Step 3: Display by source type
    print_section("Mappings by Source Type:")
    for source, count in sorted(mapping_data['mappings_by_source'].items(), key=lambda x: x[1], reverse=True):
        print_item(f"{source}:", count)
    print()
    
    # Step 4: Display by call type
    print_section("Mappings by Call Type:")
    for call_type, count in sorted(mapping_data['mappings_by_call_type'].items(), key=lambda x: x[1], reverse=True):
        print_item(f"{call_type}:", count)
    print()
    
    # Step 5: Display top functions
    if mapping_data['top_functions']:
        print_section("Most Called Functions (Top 10):")
        for func, count in list(mapping_data['top_functions'].items())[:10]:
            print_item(f"{func}:", count)
        print()
    
    # Step 6: Display sample mappings
    print_section("Sample Function Mappings (first 5):")
    sample_mappings = [m for m in mapping_data['test_function_mappings'] if m['module_name']][:5]
    for mapping in sample_mappings:
        test_desc = mapping['method_name']
        if mapping['class_name']:
            test_desc = f"{mapping['class_name']}.{test_desc}"
        func_desc = f"{mapping['module_name']}.{mapping['function_name']}"
        print_item(f"{mapping['test_id']} ({test_desc}):", func_desc)
        print_item("  Source:", mapping['source'])
    print()
    
    # Step 7: Save to JSON
    print_section("Saving results...")
    save_json(mapping_data, OUTPUT_FILE)
    print()
    
    print_header("Step 4b Complete!")
    print(f"Extracted {mapping_data['total_mappings']} function mappings from {mapping_data['total_tests']} tests")
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
