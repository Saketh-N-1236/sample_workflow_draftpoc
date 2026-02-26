"""
Step 3: Build Test Registry

This script creates a complete inventory of all tests in the repository.
It extracts test classes and test methods from each test file and assigns unique IDs.

What it does:
1. Loads test files from Step 1 output (or scans directly)
2. Parses each test file using AST
3. Extracts test classes (class Test*)
4. Extracts test methods (def test_*)
5. Generates unique test IDs
6. Maps test_id → file_path, class_name, method_name, test_type
7. Displays test count summary
8. Saves complete registry to JSON file

Run this script:
    python test_analysis/03_build_test_registry.py
"""

from pathlib import Path
import sys
import json

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.file_scanner import scan_directory, get_file_metadata
from utils.ast_parser import parse_file, extract_test_classes, extract_test_methods
from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_progress, print_summary
)

# Configuration
TEST_REPO_PATH = Path(__file__).parent.parent / "test_repository"
OUTPUT_DIR = Path(__file__).parent / "outputs"
STEP1_OUTPUT = OUTPUT_DIR / "01_test_files.json"
OUTPUT_FILE = OUTPUT_DIR / "03_test_registry.json"


def load_step1_output() -> list:
    """
    Load test files from Step 1 output if available.
    
    Returns:
        List of file paths from Step 1, or empty list if not found
    """
    if STEP1_OUTPUT.exists():
        try:
            with open(STEP1_OUTPUT, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Extract file paths from Step 1 output
                files_data = data.get('data', {}).get('files', [])
                return [Path(f['path']) for f in files_data]
        except Exception as e:
            print(f"Warning: Could not load Step 1 output: {e}")
    
    return []


def extract_test_type_enhanced(filepath: Path) -> str:
    """
    Enhanced test type detection that works with any repository structure.
    
    Args:
        filepath: Path to the test file
    
    Returns:
        Test type: 'unit', 'integration', or 'e2e'
    """
    from utils.file_scanner import _categorize_directory
    category = _categorize_directory(filepath)
    
    # Map category to test_type
    if category == 'integration':
        return 'integration'
    elif category == 'e2e':
        return 'e2e'
    else:
        return 'unit'  # Default


def extract_tests_from_file(filepath: Path, test_id_counter: int) -> tuple:
    """
    Extract all tests from a single test file.
    
    Args:
        filepath: Path to the test file
        test_id_counter: Starting counter for test IDs
    
    Returns:
        Tuple of (list of test dictionaries, new counter value)
    """
    tests = []
    
    # Parse the file
    tree = parse_file(filepath)
    if not tree:
        return tests, test_id_counter
    
    # Get file metadata
    file_metadata = get_file_metadata(filepath)
    # Use enhanced test type detection
    test_type = extract_test_type_enhanced(filepath)
    
    # Extract test classes
    test_classes = extract_test_classes(tree)
    
    # Extract standalone test methods (not in classes)
    all_test_methods = extract_test_methods(tree)
    
    # If there are test classes, extract methods from classes
    if test_classes:
        for test_class in test_classes:
            class_name = test_class['name']
            
            # Get methods for this class
            for method_name in test_class['methods']:
                if method_name.startswith('test_'):
                    test_id = f"test_{test_id_counter:04d}"
                    test_id_counter += 1
                    
                    tests.append({
                        "test_id": test_id,
                        "file_path": str(filepath),
                        "class_name": class_name,
                        "method_name": method_name,
                        "test_type": test_type,
                        "line_number": None  # Could be extracted if needed
                    })
    else:
        # No test classes, these are standalone test functions
        for test_method in all_test_methods:
            test_id = f"test_{test_id_counter:04d}"
            test_id_counter += 1
            
            tests.append({
                "test_id": test_id,
                "file_path": str(filepath),
                "class_name": None,  # Standalone function
                "method_name": test_method['name'],
                "test_type": test_type,
                "line_number": test_method.get('line_number')
            })
    
    return tests, test_id_counter


def build_test_registry() -> dict:
    """
    Build complete test registry from all test files.
    
    Returns:
        Dictionary with test registry data
    """
    # Try to load from Step 1, otherwise scan directly
    test_files = load_step1_output()
    if not test_files:
        print_section("Step 1 output not found, scanning test repository directly...")
        test_files = scan_directory(TEST_REPO_PATH)
    
    if not test_files:
        print("Error: No test files found!")
        return {}
    
    print_section(f"Processing {len(test_files)} test files...")
    
    all_tests = []
    test_id_counter = 1
    
    # Process each test file
    for i, filepath in enumerate(test_files):
        print_progress(i + 1, len(test_files), "files")
        
        file_tests, test_id_counter = extract_tests_from_file(filepath, test_id_counter)
        all_tests.extend(file_tests)
    
    print()  # New line after progress
    
    # Count statistics
    total_tests = len(all_tests)
    total_classes = len(set(t['class_name'] for t in all_tests if t['class_name']))
    
    # Count by test type
    by_type = {}
    for test in all_tests:
        test_type = test['test_type']
        by_type[test_type] = by_type.get(test_type, 0) + 1
    
    # Count by file
    by_file = {}
    for test in all_tests:
        file_path = test['file_path']
        by_file[file_path] = by_file.get(file_path, 0) + 1
    
    return {
        "total_tests": total_tests,
        "total_classes": total_classes,
        "total_files": len(test_files),
        "tests_by_type": by_type,
        "tests_by_file": by_file,
        "tests": all_tests
    }


def main():
    """Main function to build test registry."""
    print_header("Step 3: Building Test Registry")
    print()
    
    # Check if test repository exists
    if not TEST_REPO_PATH.exists():
        print(f"Error: Test repository not found at {TEST_REPO_PATH}")
        return
    
    # Step 1: Build registry
    print_section("Extracting tests from files...")
    registry_data = build_test_registry()
    
    if not registry_data:
        print("Error: Failed to build test registry!")
        return
    
    print()
    
    # Step 2: Display summary
    print_section("Registry Summary:")
    print_summary({
        "total_tests": registry_data['total_tests'],
        "total_classes": registry_data['total_classes'],
        "total_files": registry_data['total_files']
    })
    print()
    
    # Step 3: Display breakdown by type
    print_section("Tests by Type:")
    for test_type, count in sorted(registry_data['tests_by_type'].items()):
        print_item(f"{test_type.capitalize()}:", count)
    print()
    
    # Step 4: Display top files by test count
    print_section("Top Files by Test Count:")
    sorted_files = sorted(
        registry_data['tests_by_file'].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    for file_path, count in sorted_files:
        file_name = Path(file_path).name
        print_item(f"{file_name}:", f"{count} tests")
    print()
    
    # Step 5: Display sample tests
    print_section("Sample Tests (first 10):")
    sample_tests = registry_data['tests'][:10]
    for test in sample_tests:
        test_desc = f"{test['method_name']}"
        if test['class_name']:
            test_desc = f"{test['class_name']}.{test_desc}"
        print_item(f"{test['test_id']}:", test_desc)
    print()
    
    # Step 6: Save to JSON
    print_section("Saving results...")
    save_json(registry_data, OUTPUT_FILE)
    print()
    
    print_header("Step 3 Complete!")
    print(f"Registered {registry_data['total_tests']} tests from {registry_data['total_files']} files")
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
