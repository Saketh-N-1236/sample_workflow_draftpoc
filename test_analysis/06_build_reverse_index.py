"""
Step 6: Build Reverse Index

This script creates a reverse index mapping production code to tests.
This allows fast lookup of which tests reference a specific production class/module.

What it does:
1. Loads static dependencies from Step 4
2. Inverts the mapping: code → [list of tests]
3. Groups by production module/class
4. Creates index for fast lookup
5. Displays reverse index statistics
6. Saves reverse index to JSON file

Run this script:
    python test_analysis/06_build_reverse_index.py
"""

from pathlib import Path
import sys
import json
from collections import defaultdict

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_summary
)

# Configuration
OUTPUT_DIR = Path(__file__).parent / "outputs"
STEP4_OUTPUT = OUTPUT_DIR / "04_static_dependencies.json"
OUTPUT_FILE = OUTPUT_DIR / "06_reverse_index.json"


def build_reverse_index() -> dict:
    """
    Build reverse index from test dependencies.
    
    Returns:
        Dictionary with reverse index data
    """
    # Load dependencies from Step 4
    if not STEP4_OUTPUT.exists():
        print("Error: Step 4 output not found. Please run Step 4 first.")
        return {}
    
    with open(STEP4_OUTPUT, 'r', encoding='utf-8') as f:
        dependency_data = json.load(f)['data']
    
    test_dependencies = dependency_data['test_dependencies']
    
    print_section("Building reverse index...")
    
    # Build reverse mapping: production_code → [test_ids]
    reverse_index = defaultdict(list)
    
    for test_dep in test_dependencies:
        test_id = test_dep['test_id']
        referenced_classes = test_dep['referenced_classes']
        reference_types = test_dep.get('reference_types', {})  # Get reference types
        
        for ref_class in referenced_classes:
            # Get reference type for this class (default to 'direct_import')
            ref_type = reference_types.get(ref_class, 'direct_import')
            
            reverse_index[ref_class].append({
                "test_id": test_id,
                "file_path": test_dep['file_path'],
                "class_name": test_dep.get('class_name'),
                "method_name": test_dep['method_name'],
                "reference_type": ref_type  # NEW: Include reference type
            })
    
    # Convert defaultdict to regular dict and sort
    reverse_index_dict = {
        code: sorted(tests, key=lambda x: x['test_id'])
        for code, tests in reverse_index.items()
    }
    
    # Statistics
    total_mappings = sum(len(tests) for tests in reverse_index_dict.values())
    most_referenced = sorted(
        reverse_index_dict.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:20]
    
    # Group by top-level module
    module_groups = defaultdict(list)
    for code, tests in reverse_index_dict.items():
        top_module = code.split('.')[0]
        module_groups[top_module].extend([code])
    
    return {
        "total_production_classes": len(reverse_index_dict),
        "total_mappings": total_mappings,
        "average_tests_per_class": round(total_mappings / len(reverse_index_dict), 2) if reverse_index_dict else 0,
        "most_referenced_classes": [
            {
                "class": code,
                "test_count": len(tests),
                "tests": tests[:5]  # First 5 tests
            }
            for code, tests in most_referenced
        ],
        "module_groups": {
            module: len(classes)
            for module, classes in module_groups.items()
        },
        "reverse_index": reverse_index_dict
    }


def main():
    """Main function to build reverse index."""
    print_header("Step 6: Building Reverse Index")
    print()
    
    # Step 1: Build reverse index
    reverse_index_data = build_reverse_index()
    
    if not reverse_index_data:
        print("Error: Failed to build reverse index!")
        return
    
    print()
    
    # Step 2: Display summary
    print_section("Reverse Index Summary:")
    print_summary({
        "total_production_classes": reverse_index_data['total_production_classes'],
        "total_mappings": reverse_index_data['total_mappings'],
        "average_tests_per_class": reverse_index_data['average_tests_per_class']
    })
    print()
    
    # Step 3: Display most referenced classes
    print_section("Most Referenced Production Classes (Top 10):")
    for ref_class in reverse_index_data['most_referenced_classes'][:10]:
        print_item(f"{ref_class['class']}:", f"{ref_class['test_count']} tests")
        # Show sample tests
        if ref_class['tests']:
            test_names = [t['method_name'] for t in ref_class['tests']]
            test_preview = ', '.join(test_names[:3])
            if len(ref_class['tests']) > 3:
                test_preview += f", ... (+{len(ref_class['tests']) - 3} more)"
            print_item("  Sample tests:", test_preview)
    print()
    
    # Step 4: Display module groups
    print_section("Production Modules (Top 10):")
    sorted_modules = sorted(
        reverse_index_data['module_groups'].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]
    for module, class_count in sorted_modules:
        print_item(f"{module}:", f"{class_count} classes")
    print()
    
    # Step 5: Save to JSON
    print_section("Saving results...")
    save_json(reverse_index_data, OUTPUT_FILE)
    print()
    
    print_header("Step 6 Complete!")
    print(f"Created reverse index for {reverse_index_data['total_production_classes']} production classes")
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
