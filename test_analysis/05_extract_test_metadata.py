"""
Step 5: Extract Test Metadata

This script extracts metadata from tests including names, descriptions, tags, and characteristics.

What it does:
1. Loads test registry from Step 3
2. Parses each test file using AST
3. Extracts test method names and patterns
4. Extracts docstrings (test descriptions)
5. Extracts pytest markers (@pytest.mark.slow, @pytest.mark.asyncio)
6. Extracts test parameters (parameterized tests)
7. Identifies test patterns and characteristics
8. Displays metadata summary
9. Saves metadata to JSON file

Run this script:
    python test_analysis/05_extract_test_metadata.py
"""

from pathlib import Path
import sys
import json
import re
import ast
# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.language_parser import parse_file, extract_test_methods
from utils.ast_parser import extract_functions, extract_docstrings
from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_progress, print_summary
)
from utils.config import get_output_dir

# Configuration
OUTPUT_DIR = get_output_dir()
STEP3_OUTPUT = OUTPUT_DIR / "03_test_registry.json"
OUTPUT_FILE = OUTPUT_DIR / "05_test_metadata.json"


def extract_test_metadata_from_file(filepath: Path, test_methods: list) -> dict:
    """
    Extract metadata for test methods in a file.
    
    Args:
        filepath: Path to the test file
        test_methods: List of test method names to extract metadata for
    
    Returns:
        Dictionary mapping method names to their metadata
    """
    tree = parse_file(filepath)
    if not tree:
        return {}
    
    # Get language-specific test methods with metadata
    extracted_tests = extract_test_methods(tree, filepath)
    
    # For Python files, also extract functions and docstrings
    all_functions = []
    docstrings = {'functions': {}}
    if filepath.suffix == '.py':
        try:
            from utils.ast_parser import extract_functions, extract_docstrings
            all_functions = extract_functions(tree)
            docstrings = extract_docstrings(tree)
        except Exception:
            pass
    
    # Build metadata for each test method
    metadata = {}
    
    # Create a map of test names to extracted test data
    test_map = {test['name']: test for test in extracted_tests}
    
    if filepath.suffix == '.py':
        # For Python files, use function-based extraction
        for func in all_functions:
            func_name = func['name']
            if func_name.startswith('test_'):
                # Extract markers from decorators
                markers = []
                for decorator in func.get('decorators', []):
                    if 'pytest.mark' in str(decorator).lower():
                        marker_match = re.search(r'mark\.(\w+)', str(decorator), re.IGNORECASE)
                        if marker_match:
                            markers.append(marker_match.group(1).lower())
                
                # Get docstring
                description = docstrings.get('functions', {}).get(func_name, '')
                
                # Identify test pattern from name
                pattern = _identify_test_pattern(func_name)
                
                # Check if async
                is_async = func.get('is_async', False)
                
                # Check if parameterized
                is_parameterized = len(func.get('parameters', [])) > 1 or 'parametrize' in str(func.get('decorators', [])).lower()
                
                metadata[func_name] = {
                    "name": func_name,
                    "description": description,
                    "markers": markers,
                    "is_async": is_async,
                    "is_parameterized": is_parameterized,
                    "pattern": pattern,
                    "line_number": func.get('line_number')
                }
    else:
        # For JavaScript and other languages, use extracted test data
        for test_name in test_methods:
            test_data = test_map.get(test_name, {})
            
            # Identify test pattern from name
            pattern = _identify_test_pattern(test_name)
            
            # Get async status from extracted test data
            is_async = test_data.get('is_async', False)
            
            # Check if test name suggests parameterized (contains "with" or "for")
            is_parameterized = 'with' in test_name.lower() or 'for' in test_name.lower()
            
            metadata[test_name] = {
                "name": test_name,
                "description": "",  # JavaScript tests don't have docstrings in the same way
                "markers": [],  # Jest/Mocha markers would need special extraction
                "is_async": is_async,
                "is_parameterized": is_parameterized,
                "pattern": pattern,
                "line_number": test_data.get('line_number')
            }
        
        # Also add metadata for tests that were extracted but not in test_methods list
        for test_data in extracted_tests:
            test_name = test_data.get('name')
            if test_name and test_name not in metadata:
                pattern = _identify_test_pattern(test_name)
                is_async = test_data.get('is_async', False)
                is_parameterized = 'with' in test_name.lower() or 'for' in test_name.lower()
                
                metadata[test_name] = {
                    "name": test_name,
                    "description": "",
                    "markers": [],
                    "is_async": is_async,
                    "is_parameterized": is_parameterized,
                    "pattern": pattern,
                    "line_number": test_data.get('line_number')
                }
    
    return metadata


def _identify_test_pattern(test_name: str) -> str:
    """
    Identify test pattern from test name (language-agnostic).
    
    Args:
        test_name: Name of the test method
    
    Returns:
        Pattern identifier (e.g., 'should', 'when', 'test_', 'jest', etc.)
    """
    test_name_lower = test_name.lower()
    
    # BDD patterns (common in JavaScript/Jest)
    if 'should' in test_name_lower:
        return 'should_pattern'
    elif 'when' in test_name_lower or 'given' in test_name_lower:
        return 'bdd_pattern'
    elif test_name.startswith('test_'):
        return 'test_prefix'
    # Jest/Mocha patterns
    elif test_name.startswith('test(') or test_name.startswith('it('):
        return 'jest_pattern'
    # Generic test patterns
    elif 'test' in test_name_lower:
        return 'test_pattern'
    else:
        return 'other'


def build_test_metadata() -> dict:
    """
    Build metadata for all tests.
    
    Returns:
        Dictionary with test metadata
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
    
    # Extract metadata for each file
    all_metadata = []
    file_metadata_map = {}
    
    for i, (filepath_str, file_tests) in enumerate(test_files.items()):
        print_progress(i + 1, len(test_files), "files")
        
        filepath = Path(filepath_str)
        test_method_names = [t['method_name'] for t in file_tests]
        
        # Extract metadata from file
        file_metadata = extract_test_metadata_from_file(filepath, test_method_names)
        file_metadata_map[filepath_str] = file_metadata
        
        # Map metadata to tests
        for test in file_tests:
            method_name = test['method_name']
            method_metadata = file_metadata.get(method_name, {})
            
            # Use line_number from test registry if not in metadata
            line_number = method_metadata.get('line_number') or test.get('line_number')
            
            # Get pattern - use from metadata or identify from name
            pattern = method_metadata.get('pattern')
            if not pattern or pattern == 'unknown':
                pattern = _identify_test_pattern(method_name)
            
            test_metadata = {
                "test_id": test['test_id'],
                "file_path": test['file_path'],
                "class_name": test.get('class_name'),
                "method_name": method_name,
                "name": method_metadata.get('name', method_name),
                "description": method_metadata.get('description', ''),
                "markers": method_metadata.get('markers', []),
                "is_async": method_metadata.get('is_async', False),
                "is_parameterized": method_metadata.get('is_parameterized', False),
                "pattern": pattern,
                "line_number": line_number
            }
            
            all_metadata.append(test_metadata)
    
    print()  # New line after progress
    
    # Statistics
    tests_with_descriptions = sum(1 for m in all_metadata if m['description'])
    tests_with_markers = sum(1 for m in all_metadata if m['markers'])
    async_tests = sum(1 for m in all_metadata if m['is_async'])
    parameterized_tests = sum(1 for m in all_metadata if m['is_parameterized'])
    
    # Marker counts
    marker_counts = {}
    for m in all_metadata:
        for marker in m['markers']:
            marker_counts[marker] = marker_counts.get(marker, 0) + 1
    
    # Pattern counts
    pattern_counts = {}
    for m in all_metadata:
        pattern = m['pattern']
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    
    return {
        "total_tests": len(all_metadata),
        "tests_with_descriptions": tests_with_descriptions,
        "tests_with_markers": tests_with_markers,
        "async_tests": async_tests,
        "parameterized_tests": parameterized_tests,
        "marker_counts": marker_counts,
        "pattern_counts": pattern_counts,
        "test_metadata": all_metadata
    }


def main():
    """Main function to extract test metadata."""
    print_header("Step 5: Extracting Test Metadata")
    print()
    
    # Step 1: Build metadata
    print_section("Extracting metadata from test files...")
    metadata_data = build_test_metadata()
    
    if not metadata_data:
        print("Error: Failed to extract metadata!")
        return
    
    print()
    
    # Step 2: Display summary
    print_section("Metadata Summary:")
    print_summary({
        "total_tests": metadata_data['total_tests'],
        "tests_with_descriptions": metadata_data['tests_with_descriptions'],
        "tests_with_markers": metadata_data['tests_with_markers'],
        "async_tests": metadata_data['async_tests'],
        "parameterized_tests": metadata_data['parameterized_tests']
    })
    print()
    
    # Step 3: Display marker counts
    if metadata_data['marker_counts']:
        print_section("Pytest Markers Found:")
        for marker, count in sorted(metadata_data['marker_counts'].items(), key=lambda x: x[1], reverse=True):
            print_item(f"@{marker}:", count)
        print()
    
    # Step 4: Display pattern counts
    print_section("Test Naming Patterns:")
    for pattern, count in sorted(metadata_data['pattern_counts'].items(), key=lambda x: x[1], reverse=True):
        print_item(f"{pattern}:", count)
    print()
    
    # Step 5: Display sample metadata
    print_section("Sample Test Metadata (first 5):")
    sample_tests = metadata_data['test_metadata'][:5]
    for test_meta in sample_tests:
        test_desc = test_meta['method_name']
        if test_meta['class_name']:
            test_desc = f"{test_meta['class_name']}.{test_desc}"
        print_item(f"{test_meta['test_id']} ({test_desc}):", "")
        if test_meta['description']:
            desc_preview = test_meta['description'][:60] + "..." if len(test_meta['description']) > 60 else test_meta['description']
            print_item("  Description:", desc_preview)
        if test_meta['markers']:
            print_item("  Markers:", ", ".join(test_meta['markers']))
        if test_meta['is_async']:
            print_item("  Type:", "Async")
    print()
    
    # Step 6: Save to JSON
    print_section("Saving results...")
    save_json(metadata_data, OUTPUT_FILE)
    print()
    
    print_header("Step 5 Complete!")
    print(f"Extracted metadata for {metadata_data['total_tests']} tests")
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
