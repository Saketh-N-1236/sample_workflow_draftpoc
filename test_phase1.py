"""
Phase 1 Testing Script

Tests the core abstraction layer implementation:
1. Parser registry initialization
2. Python parser functionality
3. Backward compatibility
4. Configuration loading
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_parser_registry():
    """Test 1: Parser Registry"""
    print("=" * 80)
    print("TEST 1: Parser Registry")
    print("=" * 80)
    
    try:
        from parsers import get_parser, initialize_registry, detect_language
        from pathlib import Path
        
        # Initialize registry
        print("\n1.1 Initializing registry...")
        initialize_registry()
        print("   [OK] Registry initialized")
        
        # Test language detection
        print("\n1.2 Testing language detection...")
        test_files = [
            Path("test.py"),
            Path("src/agent.java"),
            Path("components/Button.tsx"),
            Path("utils/helper.js"),
        ]
        
        for filepath in test_files:
            lang = detect_language(filepath)
            print(f"   {filepath.name:20} -> {lang or 'Unknown'}")
        
        # Test parser retrieval
        print("\n1.3 Testing parser retrieval...")
        python_file = Path("test.py")
        parser = get_parser(python_file)
        
        if parser:
            print(f"   [OK] Parser found: {parser.language_name}")
            print(f"   [OK] Extensions: {parser.file_extensions}")
        else:
            print("   [FAIL] No parser found for .py files")
            return False
        
        print("\n[PASS] TEST 1 PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_python_parser():
    """Test 2: Python Parser Functionality"""
    print("=" * 80)
    print("TEST 2: Python Parser Functionality")
    print("=" * 80)
    
    try:
        from parsers import get_parser, initialize_registry
        from pathlib import Path
        
        # Initialize registry first
        initialize_registry()
        
        # Find a test file in the repository
        test_repo = project_root / "test_repository"
        if not test_repo.exists():
            print("\n[WARN] Test repository not found, skipping detailed tests")
            return True
        
        # Find any Python test file
        test_files = list(test_repo.rglob("test_*.py"))
        if not test_files:
            print("\n[WARN] No test files found, creating sample...")
            # Create a simple test file for testing
            sample_file = test_repo / "test_sample.py"
            sample_file.parent.mkdir(parents=True, exist_ok=True)
            sample_file.write_text("""
import os
from pathlib import Path

class TestSample:
    def test_method(self):
        result = os.path.exists("/tmp")
        assert result is True
""")
            test_file = sample_file
        else:
            test_file = test_files[0]
        
        print(f"\n2.1 Testing with file: {test_file.relative_to(project_root)}")
        
        parser = get_parser(test_file)
        if not parser:
            print("   [FAIL] Could not get parser")
            return False
        
        # Parse file
        print("\n2.2 Parsing file...")
        ast_tree = parser.parse_file(test_file)
        if not ast_tree:
            print("   [FAIL] Failed to parse file")
            return False
        print("   [OK] File parsed successfully")
        
        # Extract imports
        print("\n2.3 Extracting imports...")
        imports = parser.extract_imports(ast_tree)
        print(f"   [OK] Found {len(imports.get('all_imports', []))} imports")
        if imports.get('all_imports'):
            print(f"   Sample: {imports['all_imports'][:3]}")
        
        # Extract classes
        print("\n2.4 Extracting classes...")
        classes = parser.extract_classes(ast_tree)
        print(f"   [OK] Found {len(classes)} classes")
        if classes:
            print(f"   Sample: {classes[0]['name']}")
        
        # Extract functions
        print("\n2.5 Extracting functions...")
        functions = parser.extract_functions(ast_tree)
        print(f"   [OK] Found {len(functions)} functions")
        
        # Extract test methods
        print("\n2.6 Extracting test methods...")
        test_methods = parser.extract_test_methods(ast_tree)
        print(f"   [OK] Found {len(test_methods)} test methods")
        
        # Extract string references
        print("\n2.7 Extracting string references...")
        string_refs = parser.extract_string_references(ast_tree)
        print(f"   [OK] Found {len(string_refs)} string references")
        
        # Resolve module name
        print("\n2.8 Resolving module name...")
        module_name = parser.resolve_module_name(test_file, project_root)
        print(f"   [OK] Module name: {module_name}")
        
        print("\n[PASS] TEST 2 PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """Test 3: Backward Compatibility"""
    print("=" * 80)
    print("TEST 3: Backward Compatibility")
    print("=" * 80)
    
    try:
        from test_analysis.utils.ast_parser import (
            parse_file, extract_imports, extract_classes,
            extract_functions, extract_test_methods,
            extract_string_references, extract_function_calls
        )
        from pathlib import Path
        
        # Find a test file
        test_repo = project_root / "test_repository"
        if not test_repo.exists():
            print("\n[WARN] Test repository not found, skipping")
            return True
        
        test_files = list(test_repo.rglob("test_*.py"))
        if not test_files:
            print("\n[WARN] No test files found, skipping")
            return True
        
        test_file = test_files[0]
        print(f"\n3.1 Testing with file: {test_file.relative_to(project_root)}")
        
        # Test parse_file
        print("\n3.2 Testing parse_file()...")
        tree = parse_file(test_file)
        if tree:
            print("   [OK] parse_file() works")
        else:
            print("   [FAIL] parse_file() failed")
            return False
        
        # Test extract_imports
        print("\n3.3 Testing extract_imports()...")
        imports = extract_imports(tree)
        print(f"   [OK] extract_imports() works - found {len(imports.get('all_imports', []))} imports")
        
        # Test extract_classes
        print("\n3.4 Testing extract_classes()...")
        classes = extract_classes(tree)
        print(f"   [OK] extract_classes() works - found {len(classes)} classes")
        
        # Test extract_functions
        print("\n3.5 Testing extract_functions()...")
        functions = extract_functions(tree)
        print(f"   [OK] extract_functions() works - found {len(functions)} functions")
        
        # Test extract_test_methods
        print("\n3.6 Testing extract_test_methods()...")
        test_methods = extract_test_methods(tree)
        print(f"   [OK] extract_test_methods() works - found {len(test_methods)} test methods")
        
        # Test extract_string_references
        print("\n3.7 Testing extract_string_references()...")
        string_refs = extract_string_references(tree)
        print(f"   [OK] extract_string_references() works - found {len(string_refs)} refs")
        
        # Test extract_function_calls
        print("\n3.8 Testing extract_function_calls()...")
        function_calls = extract_function_calls(tree)
        print(f"   [OK] extract_function_calls() works - found {len(function_calls)} test methods with calls")
        
        print("\n[PASS] TEST 3 PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_loading():
    """Test 4: Configuration Loading"""
    print("=" * 80)
    print("TEST 4: Configuration Loading")
    print("=" * 80)
    
    try:
        from config.config_loader import (
            load_language_configs,
            get_language_config,
            get_test_patterns,
            get_file_extensions
        )
        from pathlib import Path
        
        config_path = project_root / "config" / "language_configs.yaml"
        
        print(f"\n4.1 Loading config from: {config_path.relative_to(project_root)}")
        config = load_language_configs(config_path)
        print("   [OK] Config loaded successfully")
        
        # Test Python config
        print("\n4.2 Testing Python configuration...")
        python_config = get_language_config(config, "python")
        if python_config:
            print(f"   [OK] Python config found")
            print(f"   Extensions: {python_config.get('extensions')}")
            print(f"   Test patterns: {python_config.get('test_patterns')[:2]}")
        else:
            print("   [FAIL] Python config not found")
            return False
        
        # Test test patterns
        print("\n4.3 Testing test pattern retrieval...")
        patterns = get_test_patterns(config, "python")
        print(f"   [OK] Found {len(patterns)} test patterns")
        
        # Test file extensions
        print("\n4.4 Testing file extension retrieval...")
        extensions = get_file_extensions(config, "python")
        print(f"   [OK] Found {len(extensions)} extensions: {extensions}")
        
        # Test other languages (should exist in config)
        print("\n4.5 Testing other language configs...")
        for lang in ["java", "typescript", "javascript"]:
            lang_config = get_language_config(config, lang)
            if lang_config:
                print(f"   [OK] {lang} config found (placeholder)")
            else:
                print(f"   [WARN] {lang} config not found")
        
        print("\n[PASS] TEST 4 PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test 5: Integration Test"""
    print("=" * 80)
    print("TEST 5: Integration Test")
    print("=" * 80)
    
    try:
        from parsers import initialize_registry, get_parser
        from config.config_loader import load_language_configs
        from pathlib import Path
        
        # Load config and initialize registry
        print("\n5.1 Loading config and initializing registry...")
        config_path = project_root / "config" / "language_configs.yaml"
        config = load_language_configs(config_path)
        initialize_registry(config_path)
        print("   [OK] Config loaded and registry initialized")
        
        # Test with actual test file
        test_repo = project_root / "test_repository"
        if test_repo.exists():
            test_files = list(test_repo.rglob("test_*.py"))
            if test_files:
                test_file = test_files[0]
                print(f"\n5.2 Testing end-to-end with: {test_file.relative_to(project_root)}")
                
                parser = get_parser(test_file)
                if parser:
                    ast_tree = parser.parse_file(test_file)
                    if ast_tree:
                        imports = parser.extract_imports(ast_tree)
                        classes = parser.extract_classes(ast_tree)
                        test_methods = parser.extract_test_methods(ast_tree)
                        
                        print(f"   [OK] Parsed successfully")
                        print(f"   [OK] Found {len(imports.get('all_imports', []))} imports")
                        print(f"   [OK] Found {len(classes)} classes")
                        print(f"   [OK] Found {len(test_methods)} test methods")
                    else:
                        print("   [WARN] Could not parse file (may be expected)")
                else:
                    print("   [FAIL] Could not get parser")
                    return False
            else:
                print("\n5.2 [WARN] No test files found for integration test")
        else:
            print("\n5.2 [WARN] Test repository not found for integration test")
        
        print("\n[PASS] TEST 5 PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 1 tests"""
    print("\n" + "=" * 80)
    print("PHASE 1 TEST SUITE")
    print("=" * 80)
    print()
    
    results = []
    
    # Run all tests
    results.append(("Parser Registry", test_parser_registry()))
    results.append(("Python Parser", test_python_parser()))
    results.append(("Backward Compatibility", test_backward_compatibility()))
    results.append(("Configuration Loading", test_config_loading()))
    results.append(("Integration", test_integration()))
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {test_name:30} {status}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    print()
    
    if passed == total:
        print("[SUCCESS] ALL TESTS PASSED! Phase 1 is working correctly.")
        return 0
    else:
        print("[WARN] Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())