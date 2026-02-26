"""
Step 7: Map Test Structure

This script maps the test repository structure and organization.
It identifies directory hierarchy, package organization, and test relationships.

What it does:
1. Loads test files from Step 1
2. Analyzes directory structure (unit/, integration/, e2e/)
3. Maps package/module organization
4. Identifies shared utilities (conftest.py, fixtures)
5. Maps test inheritance patterns
6. Displays structure visualization
7. Saves structure map to JSON file

Run this script:
    python test_analysis/07_map_test_structure.py
"""

from pathlib import Path
import sys
import json
from collections import defaultdict

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.file_scanner import scan_directory, get_file_metadata, group_files_by_category
from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_summary
)

# Configuration
TEST_REPO_PATH = Path(__file__).parent.parent / "test_repository"
OUTPUT_DIR = Path(__file__).parent / "outputs"
STEP1_OUTPUT = OUTPUT_DIR / "01_test_files.json"
OUTPUT_FILE = OUTPUT_DIR / "07_test_structure.json"


def analyze_directory_structure(repo_path: Path) -> dict:
    """
    Analyze the directory structure of the test repository.
    
    Returns:
        Dictionary with directory structure information
    """
    structure = {
        "root_path": str(repo_path),
        "directories": {},
        "files_by_directory": defaultdict(list),
        "package_structure": {}
    }
    
    # Scan all test files
    test_files = scan_directory(repo_path)
    
    # Group by category
    grouped = group_files_by_category(test_files)
    
    # Analyze each file
    for filepath in test_files:
        metadata = get_file_metadata(filepath)
        directory = metadata['directory']
        
        # Get relative path parts
        relative_path = filepath.relative_to(repo_path)
        path_parts = relative_path.parts
        
        # Store file in directory group
        structure["files_by_directory"][directory].append({
            "path": str(relative_path),
            "name": filepath.name,
            "line_count": metadata['line_count']
        })
        
        # Build package structure
        if len(path_parts) > 1:
            package = path_parts[0]  # First directory level
            if package not in structure["package_structure"]:
                structure["package_structure"][package] = {
                    "files": [],
                    "subdirectories": set()
                }
            
            structure["package_structure"][package]["files"].append({
                "name": filepath.name,
                "path": str(relative_path),
                "category": directory
            })
            
            # Track subdirectories
            if len(path_parts) > 2:
                structure["package_structure"][package]["subdirectories"].add(path_parts[1])
    
    # Convert sets to lists for JSON serialization
    for package in structure["package_structure"]:
        structure["package_structure"][package]["subdirectories"] = list(
            structure["package_structure"][package]["subdirectories"]
        )
    
    # Add directory statistics
    structure["directories"] = {
        category: {
            "file_count": len(files),
            "total_lines": sum(f['line_count'] for f in files)
        }
        for category, files in structure["files_by_directory"].items()
    }
    
    return structure


def find_shared_utilities(repo_path: Path) -> dict:
    """
    Find shared test utilities like conftest.py and fixtures.
    
    Returns:
        Dictionary with shared utility information
    """
    utilities = {
        "conftest_files": [],
        "fixture_directories": [],
        "shared_modules": []
    }
    
    # Find conftest.py files
    for conftest in repo_path.rglob("conftest.py"):
        utilities["conftest_files"].append({
            "path": str(conftest.relative_to(repo_path)),
            "directory": str(conftest.parent.relative_to(repo_path))
        })
    
    # Find fixture directories
    fixtures_dir = repo_path / "fixtures"
    if fixtures_dir.exists():
        utilities["fixture_directories"].append({
            "path": str(fixtures_dir.relative_to(repo_path)),
            "files": [f.name for f in fixtures_dir.glob("*.json")] + 
                     [f.name for f in fixtures_dir.glob("*.py") if f.name != "__init__.py"]
        })
    
    return utilities


def build_structure_map() -> dict:
    """
    Build complete structure map.
    
    Returns:
        Dictionary with complete structure information
    """
    print_section("Analyzing directory structure...")
    directory_structure = analyze_directory_structure(TEST_REPO_PATH)
    
    print_section("Finding shared utilities...")
    shared_utilities = find_shared_utilities(TEST_REPO_PATH)
    
    return {
        "directory_structure": directory_structure,
        "shared_utilities": shared_utilities,
        "summary": {
            "total_directories": len(directory_structure["package_structure"]),
            "total_files": sum(
                len(files) for files in directory_structure["files_by_directory"].values()
            ),
            "categories": list(directory_structure["directories"].keys())
        }
    }


def main():
    """Main function to map test structure."""
    print_header("Step 7: Mapping Test Structure")
    print()
    
    # Check if test repository exists
    if not TEST_REPO_PATH.exists():
        print(f"Error: Test repository not found at {TEST_REPO_PATH}")
        return
    
    # Step 1: Build structure map
    structure_data = build_structure_map()
    
    print()
    
    # Step 2: Display summary
    print_section("Structure Summary:")
    print_summary({
        "total_directories": structure_data['summary']['total_directories'],
        "total_files": structure_data['summary']['total_files'],
        "categories": len(structure_data['summary']['categories'])
    })
    print()
    
    # Step 3: Display directory breakdown
    print_section("Directory Breakdown:")
    for category, stats in structure_data['directory_structure']['directories'].items():
        print_item(f"{category.capitalize()}:", 
                  f"{stats['file_count']} files, {stats['total_lines']} lines")
    print()
    
    # Step 4: Display package structure
    print_section("Package Structure:")
    for package, info in structure_data['directory_structure']['package_structure'].items():
        print_item(f"{package}/:", f"{len(info['files'])} files")
        if info['subdirectories']:
            print_item("  Subdirectories:", ", ".join(info['subdirectories']))
    print()
    
    # Step 5: Display shared utilities
    print_section("Shared Utilities:")
    if structure_data['shared_utilities']['conftest_files']:
        print_item("conftest.py files:", len(structure_data['shared_utilities']['conftest_files']))
        for conftest in structure_data['shared_utilities']['conftest_files']:
            print_item(f"  - {conftest['path']}:", f"in {conftest['directory']}")
    
    if structure_data['shared_utilities']['fixture_directories']:
        print_item("Fixture directories:", len(structure_data['shared_utilities']['fixture_directories']))
        for fixture_dir in structure_data['shared_utilities']['fixture_directories']:
            print_item(f"  - {fixture_dir['path']}:", f"{len(fixture_dir['files'])} files")
    print()
    
    # Step 6: Save to JSON
    print_section("Saving results...")
    save_json(structure_data, OUTPUT_FILE)
    print()
    
    print_header("Step 7 Complete!")
    print(f"Mapped structure for {structure_data['summary']['total_files']} files")
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
