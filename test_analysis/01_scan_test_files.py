"""
Step 1: Scan Test Files

This script discovers all test files in the test repository.
It recursively scans the directory and identifies test files based on naming patterns.

What it does:
1. Scans the test_repository directory recursively
2. Identifies test files (test_*.py, *_test.py patterns)
3. Extracts file metadata (path, size, line count)
4. Categorizes files by directory (unit, integration, e2e)
5. Displays results in console
6. Saves results to JSON file

Run this script:
    python test_analysis/01_scan_test_files.py
"""

from pathlib import Path
import sys
 
# Add utils to path so we can import our utility modules
sys.path.insert(0, str(Path(__file__).parent))

from utils.file_scanner import scan_directory, get_file_metadata, group_files_by_category
from utils.output_formatter import (
    print_header, print_section, print_item, print_list, 
    print_summary, save_json, print_progress
)

# Configuration: Path to test repository
TEST_REPO_PATH = Path(__file__).parent.parent / "test_repository"
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "01_test_files.json"


def main():
    """
    Main function to scan test files.
    
    This function:
    1. Scans the test repository directory
    2. Extracts metadata for each test file
    3. Groups files by category
    4. Displays results
    5. Saves to JSON
    """
    # Print header
    print_header("Step 1: Scanning Test Files")
    print()
    
    # Check if test repository exists
    if not TEST_REPO_PATH.exists():
        print(f"Error: Test repository not found at {TEST_REPO_PATH}")
        print("Please ensure the test_repository directory exists.")
        return
    
    print_section(f"Scanning directory: {TEST_REPO_PATH}")
    print()
    
    # Step 1: Scan for test files
    print_section("Discovering test files...")
    test_files = scan_directory(TEST_REPO_PATH)
    
    if not test_files:
        print("No test files found!")
        return
    
    print_item("Found test files:", len(test_files))
    print()
    
    # Step 2: Extract metadata for each file
    print_section("Extracting file metadata...")
    file_metadata = []
    total_lines = 0
    total_size = 0
    
    for i, filepath in enumerate(test_files):
        print_progress(i + 1, len(test_files), "files")
        metadata = get_file_metadata(filepath)
        file_metadata.append(metadata)
        total_lines += metadata['line_count']
        total_size += metadata['size_bytes']
    
    print()  # New line after progress
    print()
    
    # Step 3: Group files by category
    print_section("Categorizing files...")
    grouped_files = group_files_by_category(test_files)
    
    # Display categorized results
    for category, files in grouped_files.items():
        if files:
            print_item(f"{category.capitalize()} tests:", len(files))
    
    print()
    
    # Step 4: Display sample files
    print_section("Sample test files found:")
    print_list([f"{m['path']} ({m['line_count']} lines)" for m in file_metadata[:10]], 
               max_items=10)
    print()
    
    # Step 5: Prepare output data
    output_data = {
        "scan_directory": str(TEST_REPO_PATH),
        "total_files": len(test_files),
        "total_lines": total_lines,
        "total_size_bytes": total_size,
        "categories": {
            category: len(files) 
            for category, files in grouped_files.items()
        },
        "files": file_metadata
    }
    
    # Step 6: Display summary
    print_section("Summary:")
    print_summary({
        "total_files": len(test_files),
        "total_lines": total_lines,
        "total_size_kb": round(total_size / 1024, 2),
        "unit_tests": len(grouped_files['unit']),
        "integration_tests": len(grouped_files['integration']),
        "e2e_tests": len(grouped_files['e2e']),
        "other_tests": len(grouped_files['other'])
    })
    print()
    
    # Step 7: Save to JSON
    print_section("Saving results...")
    save_json(output_data, OUTPUT_FILE)
    print()
    
    print_header("Step 1 Complete!")
    print(f"Results saved to: {OUTPUT_FILE}")
    print(f"Found {len(test_files)} test files with {total_lines} total lines of code")


if __name__ == "__main__":
    main()
