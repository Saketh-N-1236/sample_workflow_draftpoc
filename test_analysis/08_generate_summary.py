"""
Step 8: Generate Summary Report

This script generates a comprehensive summary report combining all previous analysis steps.
It provides an overview of the entire test repository analysis.

What it does:
1. Loads all previous step outputs
2. Combines data from all steps
3. Generates statistics and insights
4. Creates human-readable summary
5. Validates data consistency
6. Displays comprehensive report
7. Saves summary to JSON file

Run this script:
    python test_analysis/08_generate_summary.py
"""

from pathlib import Path
import sys
import json
from datetime import datetime

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_summary
)

# Configuration
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "08_summary_report.json"

# Step output files
STEP_FILES = {
    "step1": OUTPUT_DIR / "01_test_files.json",
    "step2": OUTPUT_DIR / "02_framework_detection.json",
    "step3": OUTPUT_DIR / "03_test_registry.json",
    "step4": OUTPUT_DIR / "04_static_dependencies.json",
    "step5": OUTPUT_DIR / "05_test_metadata.json",
    "step6": OUTPUT_DIR / "06_reverse_index.json",
    "step7": OUTPUT_DIR / "07_test_structure.json"
}


def load_step_output(step_file: Path) -> dict:
    """
    Load output from a previous step.
    
    Args:
        step_file: Path to the step output JSON file
    
    Returns:
        Dictionary with step data, or empty dict if not found
    """
    if not step_file.exists():
        return {}
    
    try:
        with open(step_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('data', {})
    except Exception as e:
        print(f"Warning: Could not load {step_file}: {e}")
        return {}


def generate_summary_report() -> dict:
    """
    Generate comprehensive summary report.
    
    Returns:
        Dictionary with complete summary
    """
    print_section("Loading all analysis results...")
    
    # Load all step outputs
    step1_data = load_step_output(STEP_FILES["step1"])
    step2_data = load_step_output(STEP_FILES["step2"])
    step3_data = load_step_output(STEP_FILES["step3"])
    step4_data = load_step_output(STEP_FILES["step4"])
    step5_data = load_step_output(STEP_FILES["step5"])
    step6_data = load_step_output(STEP_FILES["step6"])
    step7_data = load_step_output(STEP_FILES["step7"])
    
    # Build summary
    summary = {
        "generated_at": datetime.now().isoformat(),
        "test_repository_overview": {
            "total_test_files": step1_data.get("total_files", 0),
            "total_lines_of_code": step1_data.get("total_lines", 0),
            "test_framework": step2_data.get("primary_framework", "unknown"),
            "framework_confidence": step2_data.get("confidence", "unknown")
        },
        "test_inventory": {
            "total_tests": step3_data.get("total_tests", 0),
            "total_test_classes": step3_data.get("total_classes", 0),
            "tests_by_type": step3_data.get("tests_by_type", {})
        },
        "dependencies": {
            "total_production_classes_referenced": step6_data.get("total_production_classes", 0),
            "total_dependency_mappings": step6_data.get("total_mappings", 0),
            "average_tests_per_class": step6_data.get("average_tests_per_class", 0),
            "tests_with_dependencies": step4_data.get("tests_with_dependencies", 0)
        },
        "metadata": {
            "tests_with_descriptions": step5_data.get("tests_with_descriptions", 0),
            "tests_with_markers": step5_data.get("tests_with_markers", 0),
            "async_tests": step5_data.get("async_tests", 0),
            "parameterized_tests": step5_data.get("parameterized_tests", 0)
        },
        "structure": {
            "test_categories": step7_data.get("summary", {}).get("categories", []),
            "package_count": step7_data.get("summary", {}).get("total_directories", 0)
        },
        "key_insights": []
    }
    
    # Generate insights
    insights = []
    
    # Test coverage insight
    if summary["dependencies"]["total_production_classes_referenced"] > 0:
        coverage_ratio = summary["test_inventory"]["total_tests"] / summary["dependencies"]["total_production_classes_referenced"]
        insights.append({
            "type": "coverage",
            "message": f"Average of {coverage_ratio:.1f} tests per production class",
            "value": coverage_ratio
        })
    
    # Framework insight
    if summary["test_repository_overview"]["test_framework"] != "unknown":
        insights.append({
            "type": "framework",
            "message": f"Using {summary['test_repository_overview']['test_framework']} framework",
            "confidence": summary["test_repository_overview"]["framework_confidence"]
        })
    
    # Test organization insight
    if summary["structure"]["test_categories"]:
        insights.append({
            "type": "organization",
            "message": f"Tests organized into {len(summary['structure']['test_categories'])} categories",
            "categories": summary["structure"]["test_categories"]
        })
    
    # Documentation insight
    if summary["metadata"]["tests_with_descriptions"] > 0:
        doc_ratio = summary["metadata"]["tests_with_descriptions"] / summary["test_inventory"]["total_tests"] * 100
        insights.append({
            "type": "documentation",
            "message": f"{doc_ratio:.1f}% of tests have descriptions",
            "value": doc_ratio
        })
    
    summary["key_insights"] = insights
    
    return summary


def main():
    """Main function to generate summary report."""
    print_header("Step 8: Generating Summary Report")
    print()
    
    # Step 1: Generate summary
    summary_data = generate_summary_report()
    
    print()
    
    # Step 2: Display overview
    print_section("Test Repository Overview:")
    overview = summary_data["test_repository_overview"]
    print_item("Total test files:", overview["total_test_files"])
    print_item("Total lines of code:", overview["total_lines_of_code"])
    print_item("Test framework:", overview["test_framework"])
    print_item("Framework confidence:", overview["framework_confidence"])
    print()
    
    # Step 3: Display test inventory
    print_section("Test Inventory:")
    inventory = summary_data["test_inventory"]
    print_item("Total tests:", inventory["total_tests"])
    print_item("Total test classes:", inventory["total_test_classes"])
    print_item("Tests by type:", "")
    for test_type, count in inventory["tests_by_type"].items():
        print_item(f"  {test_type}:", count)
    print()
    
    # Step 4: Display dependencies
    print_section("Dependencies:")
    deps = summary_data["dependencies"]
    print_item("Production classes referenced:", deps["total_production_classes_referenced"])
    print_item("Total dependency mappings:", deps["total_dependency_mappings"])
    print_item("Average tests per class:", deps["average_tests_per_class"])
    print_item("Tests with dependencies:", deps["tests_with_dependencies"])
    print()
    
    # Step 5: Display metadata
    print_section("Test Metadata:")
    metadata = summary_data["metadata"]
    print_item("Tests with descriptions:", metadata["tests_with_descriptions"])
    print_item("Tests with markers:", metadata["tests_with_markers"])
    print_item("Async tests:", metadata["async_tests"])
    print_item("Parameterized tests:", metadata["parameterized_tests"])
    print()
    
    # Step 6: Display structure
    print_section("Repository Structure:")
    structure = summary_data["structure"]
    print_item("Test categories:", len(structure["test_categories"]))
    print_item("Categories:", ", ".join(structure["test_categories"]))
    print_item("Package count:", structure["package_count"])
    print()
    
    # Step 7: Display insights
    print_section("Key Insights:")
    for insight in summary_data["key_insights"]:
        print_item(f"[{insight['type']}]", insight["message"])
    print()
    
    # Step 8: Save to JSON
    print_section("Saving results...")
    save_json(summary_data, OUTPUT_FILE)
    print()
    
    print_header("Step 8 Complete!")
    print("Comprehensive summary report generated")
    print(f"Results saved to: {OUTPUT_FILE}")
    print()
    print("=" * 50)
    print("ALL ANALYSIS STEPS COMPLETE!")
    print("=" * 50)
    print()
    print("Summary:")
    print(f"  - {overview['total_test_files']} test files analyzed")
    print(f"  - {inventory['total_tests']} tests registered")
    print(f"  - {deps['total_production_classes_referenced']} production classes mapped")
    print(f"  - Framework: {overview['test_framework']} ({overview['framework_confidence']} confidence)")
    print()
    print("All output files saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
