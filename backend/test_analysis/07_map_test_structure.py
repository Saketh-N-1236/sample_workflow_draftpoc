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
import logging
from collections import defaultdict

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.file_scanner import scan_directory, get_file_metadata, group_files_by_category
from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_summary
)
from utils.config import get_test_repo_path, get_output_dir

logger = logging.getLogger(__name__)

# Configuration
TEST_REPO_PATH = get_test_repo_path()
OUTPUT_DIR = get_output_dir()
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
    
    # Load test registry to count tests per directory
    test_counts_by_dir = defaultdict(int)
    test_registry_file = OUTPUT_DIR / "03_test_registry.json"
    if test_registry_file.exists():
        try:
            with open(test_registry_file, 'r', encoding='utf-8') as f:
                registry_data = json.load(f)
                # Handle wrapped and unwrapped formats
                data = registry_data.get('data', registry_data)
                tests = data.get('tests', [])
                for test in tests:
                    file_path = test.get('file_path', '')
                    if file_path:
                        try:
                            # Normalize path and get directory
                            file_path_obj = Path(file_path)
                            # Get relative directory path
                            if file_path_obj.is_absolute():
                                try:
                                    dir_key = str(file_path_obj.relative_to(repo_path).parent)
                                except ValueError:
                                    # If not relative to repo_path, use absolute parent
                                    dir_key = str(file_path_obj.parent)
                            else:
                                dir_key = str(file_path_obj.parent)
                            # Normalize separators
                            dir_key = dir_key.replace('\\', '/')
                            test_counts_by_dir[dir_key] += 1
                        except Exception as e:
                            logger.debug(f"Could not process file path {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Could not load test registry for test counts: {e}")
    
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
    
    # Build a map of file paths to test counts from test registry
    # Load test registry again to get file-level counts
    file_test_counts = defaultdict(int)
    file_test_counts_by_name = defaultdict(int)  # Fallback: count by filename
    if test_registry_file.exists():
        try:
            with open(test_registry_file, 'r', encoding='utf-8') as f:
                registry_data = json.load(f)
                data = registry_data.get('data', registry_data)
                tests = data.get('tests', [])
                for test in tests:
                    file_path = test.get('file_path', '')
                    if file_path:
                        try:
                            # Normalize the file path for matching
                            file_path_obj = Path(file_path)
                            if file_path_obj.is_absolute():
                                try:
                                    # Get relative path from repo root
                                    rel_path = file_path_obj.relative_to(repo_path)
                                    file_key = str(rel_path).replace('\\', '/')
                                except ValueError:
                                    # Use absolute path if can't make relative
                                    file_key = str(file_path_obj).replace('\\', '/')
                            else:
                                file_key = str(file_path_obj).replace('\\', '/')
                            file_test_counts[file_key] += 1
                            # Also index by filename for fallback matching
                            file_test_counts_by_name[file_path_obj.name] += 1
                        except Exception as e:
                            logger.debug(f"Could not process file path {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Could not load test registry for file-level test counts: {e}")
    
    # Add directory statistics with test counts
    structure["directories"] = {}
    for category, files in structure["files_by_directory"].items():
        # Calculate test count for this category by matching actual file paths
        category_test_count = 0
        matched_files = set()  # Track which files we've matched to avoid double counting
        
        for file_info in files:
            # Get the file path (relative)
            file_path_relative = file_info.get('path', '')
            if not file_path_relative:
                continue
                
            try:
                # Normalize the path for matching
                file_path_normalized = file_path_relative.replace('\\', '/')
                
                # Try exact match first
                if file_path_normalized in file_test_counts:
                    category_test_count += file_test_counts[file_path_normalized]
                    matched_files.add(file_path_normalized)
                else:
                    # Try matching by filename (in case paths differ slightly)
                    file_name = Path(file_path_relative).name
                    if file_name not in matched_files:
                        # Check if this filename exists in test registry
                        if file_name in file_test_counts_by_name:
                            category_test_count += file_test_counts_by_name[file_name]
                            matched_files.add(file_name)
            except Exception as e:
                logger.debug(f"Could not match file for {file_path_relative}: {e}")
        
        structure["directories"][category] = {
            "file_count": len(files),
            "test_count": category_test_count,
            "total_lines": sum(f['line_count'] for f in files)
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
    Build complete structure map with test counts.
    
    Returns:
        Dictionary with complete structure information including structure_rows for DB
    """
    print_section("Analyzing directory structure...")
    directory_structure = analyze_directory_structure(TEST_REPO_PATH)
    
    print_section("Finding shared utilities...")
    shared_utilities = find_shared_utilities(TEST_REPO_PATH)
    
    # Build structure_rows for database insertion (includes test_count)
    structure_rows = []
    directories = directory_structure.get('directories', {})
    files_by_directory = directory_structure.get('files_by_directory', {})
    
    for category, stats in directories.items():
        structure_rows.append({
            "category": category,
            "directory_path": category,
            "file_count": stats.get('file_count', 0),
            "test_count": stats.get('test_count', 0),
            "total_lines": stats.get('total_lines', 0),
        })
    
    return {
        "directory_structure": directory_structure,
        "shared_utilities": shared_utilities,
        "structure_rows": structure_rows,  # For DB loader
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
