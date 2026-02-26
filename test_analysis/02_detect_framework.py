"""
Step 2: Detect Test Framework

This script identifies which test framework is being used in the test repository.
It analyzes test files, configuration files, and import patterns to determine the framework.

What it does:
1. Checks for pytest.ini or setup.cfg configuration files
2. Analyzes test file imports (pytest, unittest)
3. Checks for framework-specific patterns (@pytest.mark, unittest.TestCase)
4. Analyzes conftest.py for pytest-specific configuration
5. Displays framework detection results
6. Saves results to JSON file

Run t his script:
    python test_analysis/02_detect_framework.py
"""

from pathlib import Path
import sys
import re

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.file_scanner import scan_directory
from utils.ast_parser import parse_file, extract_imports
from utils.output_formatter import (
    print_header, print_section, print_item, print_list,
    save_json, print_progress
)

# Configuration
TEST_REPO_PATH = Path(__file__).parent.parent / "test_repository"
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "02_framework_detection.json"


def check_config_files(repo_path: Path) -> dict:
    """
    Check for test framework configuration files.
    
    Looks for:
    - pytest.ini
    - setup.cfg (may contain pytest config)
    - pyproject.toml (may contain pytest config)
    - tox.ini (may contain pytest config)
    
    Returns:
        Dictionary with configuration file findings
    """
    findings = {
        "pytest_ini": None,
        "setup_cfg": None,
        "pyproject_toml": None,
        "tox_ini": None,
        "config_found": False
    }
    
    # Check for pytest.ini
    pytest_ini = repo_path / "pytest.ini"
    if pytest_ini.exists():
        findings["pytest_ini"] = str(pytest_ini)
        findings["config_found"] = True
        # Try to read basic info
        try:
            with open(pytest_ini, 'r', encoding='utf-8') as f:
                content = f.read()
                findings["pytest_ini_content"] = content[:500]  # First 500 chars
        except:
            pass
    
    # Check for setup.cfg
    setup_cfg = repo_path / "setup.cfg"
    if setup_cfg.exists():
        findings["setup_cfg"] = str(setup_cfg)
        findings["config_found"] = True
    
    # Check for pyproject.toml
    pyproject_toml = repo_path / "pyproject.toml"
    if pyproject_toml.exists():
        findings["pyproject_toml"] = str(pyproject_toml)
        findings["config_found"] = True
    
    # Check for tox.ini
    tox_ini = repo_path / "tox.ini"
    if tox_ini.exists():
        findings["tox_ini"] = str(tox_ini)
        findings["config_found"] = True
    
    return findings


def check_conftest(repo_path: Path) -> dict:
    """
    Check for conftest.py file (pytest-specific).
    
    Returns:
        Dictionary with conftest.py findings
    """
    findings = {
        "conftest_found": False,
        "conftest_path": None,
        "has_fixtures": False,
        "has_pytest_imports": False
    }
    
    conftest = repo_path / "conftest.py"
    if conftest.exists():
        findings["conftest_found"] = True
        findings["conftest_path"] = str(conftest)
        
        # Parse conftest.py to check for pytest usage
        tree = parse_file(conftest)
        if tree:
            imports = extract_imports(tree)
            
            # Check for pytest imports
            if any('pytest' in imp.lower() for imp in imports['all_imports']):
                findings["has_pytest_imports"] = True
            
            # Check for @pytest.fixture decorators (simple regex check)
            try:
                with open(conftest, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if '@pytest.fixture' in content or 'pytest.fixture' in content:
                        findings["has_fixtures"] = True
            except:
                pass
    
    return findings


def analyze_test_files(repo_path: Path) -> dict:
    """
    Analyze test files to detect framework usage patterns.
    
    Returns:
        Dictionary with framework detection results
    """
    test_files = scan_directory(repo_path)
    
    framework_indicators = {
        "pytest": {
            "files_with_import": 0,
            "files_with_markers": 0,
            "files_with_fixtures": 0,
            "total_indicators": 0
        },
        "unittest": {
            "files_with_import": 0,
            "files_with_testcase": 0,
            "total_indicators": 0
        }
    }
    
    # Analyze each test file
    for i, filepath in enumerate(test_files):
        print_progress(i + 1, len(test_files), "files")
        
        tree = parse_file(filepath)
        if not tree:
            continue
        
        # Extract imports
        imports = extract_imports(tree)
        all_imports_str = ' '.join(imports['all_imports']).lower()
        
        # Check for pytest
        if 'pytest' in all_imports_str:
            framework_indicators["pytest"]["files_with_import"] += 1
            framework_indicators["pytest"]["total_indicators"] += 1
        
        # Check for unittest
        if 'unittest' in all_imports_str:
            framework_indicators["unittest"]["files_with_import"] += 1
            framework_indicators["unittest"]["total_indicators"] += 1
        
        # Check file content for patterns
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Check for pytest markers
                if '@pytest.mark' in content or 'pytest.mark' in content:
                    framework_indicators["pytest"]["files_with_markers"] += 1
                    framework_indicators["pytest"]["total_indicators"] += 1
                
                # Check for pytest fixtures
                if '@pytest.fixture' in content:
                    framework_indicators["pytest"]["files_with_fixtures"] += 1
                    framework_indicators["pytest"]["total_indicators"] += 1
                
                # Check for unittest.TestCase
                if 'TestCase' in content and 'unittest' in content:
                    framework_indicators["unittest"]["files_with_testcase"] += 1
                    framework_indicators["unittest"]["total_indicators"] += 1
        except:
            pass
    
    print()  # New line after progress
    
    return framework_indicators


def determine_framework(config_findings: dict, conftest_findings: dict, 
                        file_indicators: dict) -> dict:
    """
    Determine the primary test framework based on all indicators.
    
    Returns:
        Dictionary with framework determination results
    """
    result = {
        "primary_framework": "unknown",
        "confidence": "low",
        "indicators": []
    }
    
    pytest_score = 0
    unittest_score = 0
    
    # Score from config files
    if config_findings.get("pytest_ini"):
        pytest_score += 3
        result["indicators"].append("pytest.ini found")
    
    # Score from conftest.py
    if conftest_findings.get("conftest_found"):
        pytest_score += 2
        result["indicators"].append("conftest.py found")
    
    if conftest_findings.get("has_pytest_imports"):
        pytest_score += 1
        result["indicators"].append("conftest.py uses pytest")
    
    # Score from file analysis
    pytest_file_score = file_indicators["pytest"]["total_indicators"]
    unittest_file_score = file_indicators["unittest"]["total_indicators"]
    
    pytest_score += pytest_file_score
    unittest_score += unittest_file_score
    
    # Determine primary framework
    if pytest_score > unittest_score and pytest_score > 0:
        result["primary_framework"] = "pytest"
        if pytest_score >= 5:
            result["confidence"] = "high"
        elif pytest_score >= 3:
            result["confidence"] = "medium"
    elif unittest_score > pytest_score and unittest_score > 0:
        result["primary_framework"] = "unittest"
        if unittest_score >= 3:
            result["confidence"] = "high"
        else:
            result["confidence"] = "medium"
    elif pytest_score == unittest_score and pytest_score > 0:
        result["primary_framework"] = "mixed"
        result["confidence"] = "medium"
    
    result["pytest_score"] = pytest_score
    result["unittest_score"] = unittest_score
    
    return result


def main():
    """Main function to detect test framework."""
    print_header("Step 2: Detecting Test Framework")
    print()
    
    # Check if test repository exists
    if not TEST_REPO_PATH.exists():
        print(f"Error: Test repository not found at {TEST_REPO_PATH}")
        return
    
    # Step 1: Check configuration files
    print_section("Checking configuration files...")
    config_findings = check_config_files(TEST_REPO_PATH)
    
    if config_findings["config_found"]:
        print_item("Configuration files found:", "Yes")
        if config_findings["pytest_ini"]:
            print_item("  - pytest.ini:", config_findings["pytest_ini"])
        if config_findings["setup_cfg"]:
            print_item("  - setup.cfg:", config_findings["setup_cfg"])
        if config_findings["pyproject_toml"]:
            print_item("  - pyproject.toml:", config_findings["pyproject_toml"])
    else:
        print_item("Configuration files found:", "No")
    print()
    
    # Step 2: Check for conftest.py
    print_section("Checking for conftest.py...")
    conftest_findings = check_conftest(TEST_REPO_PATH)
    
    if conftest_findings["conftest_found"]:
        print_item("conftest.py found:", "Yes")
        print_item("  Path:", conftest_findings["conftest_path"])
        print_item("  Has pytest imports:", conftest_findings["has_pytest_imports"])
        print_item("  Has fixtures:", conftest_findings["has_fixtures"])
    else:
        print_item("conftest.py found:", "No")
    print()
    
    # Step 3: Analyze test files
    print_section("Analyzing test files for framework patterns...")
    file_indicators = analyze_test_files(TEST_REPO_PATH)
    
    print_section("Framework indicators found:")
    print_item("Pytest indicators:", file_indicators["pytest"]["total_indicators"])
    print_item("  - Files with pytest import:", file_indicators["pytest"]["files_with_import"])
    print_item("  - Files with pytest markers:", file_indicators["pytest"]["files_with_markers"])
    print_item("  - Files with pytest fixtures:", file_indicators["pytest"]["files_with_fixtures"])
    print()
    print_item("Unittest indicators:", file_indicators["unittest"]["total_indicators"])
    print_item("  - Files with unittest import:", file_indicators["unittest"]["files_with_import"])
    print_item("  - Files with TestCase:", file_indicators["unittest"]["files_with_testcase"])
    print()
    
    # Step 4: Determine primary framework
    print_section("Determining primary framework...")
    framework_result = determine_framework(config_findings, conftest_findings, file_indicators)
    
    print_item("Primary framework:", framework_result["primary_framework"])
    print_item("Confidence:", framework_result["confidence"])
    print_item("Pytest score:", framework_result["pytest_score"])
    print_item("Unittest score:", framework_result["unittest_score"])
    print()
    
    if framework_result["indicators"]:
        print_section("Key indicators:")
        for indicator in framework_result["indicators"]:
            print_item("  -", indicator)
        print()
    
    # Step 5: Prepare output data
    output_data = {
        "primary_framework": framework_result["primary_framework"],
        "confidence": framework_result["confidence"],
        "pytest_score": framework_result["pytest_score"],
        "unittest_score": framework_result["unittest_score"],
        "config_files": config_findings,
        "conftest": conftest_findings,
        "file_indicators": file_indicators,
        "indicators": framework_result["indicators"]
    }
    
    # Step 6: Save to JSON
    print_section("Saving results...")
    save_json(output_data, OUTPUT_FILE)
    print()
    
    print_header("Step 2 Complete!")
    print(f"Framework detected: {framework_result['primary_framework']} (confidence: {framework_result['confidence']})")
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
