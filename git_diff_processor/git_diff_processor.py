"""
Git Diff to Test Selection Processor

This script processes git diff output to find which tests should be run
based on code changes. It shows what will be searched in the database
and then queries the database to find affected tests.

What it does:
1. Reads git diff from a file
2. Parses the diff to extract changed files/classes/methods
3. Displays what will be searched (for understanding)
4. Queries the database to find affected tests
5. Displays results with clear explanations

Usage:
    python git_diff_processor/git_diff_processor.py <diff_file_path>
    
    Or specify file interactively:
    python git_diff_processor/git_diff_processor.py
"""

import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path to import deterministic modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import deterministic database connection
from deterministic.db_connection import get_connection, test_connection, DB_SCHEMA
from deterministic.utils.db_helpers import get_tests_for_production_class

# Import diff parser
sys.path.insert(0, str(Path(__file__).parent))
from utils.diff_parser import (
    parse_git_diff, 
    read_diff_file, 
    build_search_queries,
    extract_production_classes_from_file,
    extract_test_file_candidates
)

# Import semantic search
from semantic_retrieval.semantic_search import find_tests_semantic


def print_header(title: str, width: int = 50) -> None:
    """Print a formatted header."""
    print("=" * width)
    print(title)
    print("=" * width)


def print_section(title: str, indent: int = 2) -> None:
    """Print a section header."""
    print(" " * indent + title)


def print_item(label: str, value: any = "", indent: int = 4) -> None:
    """Print a labeled item."""
    if value != "" and value is not None:
        print(" " * indent + f"{label}: {value}")
    else:
        print(" " * indent + label)


def display_parsed_changes(parsed_diff: Dict) -> None:
    """
    Display parsed diff changes in a beginner-friendly way.
    
    Args:
        parsed_diff: Dictionary from parse_git_diff
    """
    print_section("Parsed Changes:")
    print()
    
    print_item("Changed files", len(parsed_diff['changed_files']))
    for file in parsed_diff['changed_files']:
        # Find file info
        file_info = next((f for f in parsed_diff['file_changes'] if f['file'] == file), None)
        status = file_info['status'] if file_info else 'unknown'
        print_item(f"  - {file}", f"({status})")
    print()
    
    if parsed_diff['changed_classes']:
        print_item("Changed classes", len(parsed_diff['changed_classes']))
        for cls in parsed_diff['changed_classes']:
            print_item(f"  - {cls}", "")
    else:
        print_item("Changed classes", "None detected")
    print()
    
    if parsed_diff['changed_methods']:
        print_item("Changed methods", len(parsed_diff['changed_methods']))
        for method in parsed_diff['changed_methods'][:10]:  # Show first 10
            print_item(f"  - {method}", "")
        if len(parsed_diff['changed_methods']) > 10:
            print_item(f"  ... and {len(parsed_diff['changed_methods']) - 10} more", "")
    else:
        print_item("Changed methods", "None detected")
    print()


def display_search_strategy(search_queries: Dict) -> None:
    """
    Display what will be searched in the database.
    
    Args:
        search_queries: Dictionary from build_search_queries
    """
    print_section("What We'll Search in Database:")
    print()
    
    # Show function-level changes first (highest precision)
    if search_queries.get('changed_functions'):
        print_item("Function-level changes (highest precision)", len(search_queries['changed_functions']))
        for func_change in search_queries['changed_functions'][:10]:
            func_name = f"{func_change['module']}.{func_change['function']}"
            print_item(f"  - {func_name}", "(will match tests that call/patch this function)")
        if len(search_queries['changed_functions']) > 10:
            print_item(f"  ... and {len(search_queries['changed_functions']) - 10} more", "")
        print()
    
    if search_queries['exact_matches']:
        print_item("Exact production class matches", len(search_queries['exact_matches']))
        for match in search_queries['exact_matches'][:10]:
            print_item(f"  - {match}", "")
        if len(search_queries['exact_matches']) > 10:
            print_item(f"  ... and {len(search_queries['exact_matches']) - 10} more", "")
        print()
    
    if search_queries['module_matches']:
        print_item("Module-level patterns", len(search_queries['module_matches']))
        for pattern in search_queries['module_matches']:
            print_item(f"  - {pattern}", "(will match direct references in module)")
        print()
    
    if search_queries.get('test_file_candidates'):
        print_item("Direct test file candidates", len(search_queries['test_file_candidates']))
        for test_file in search_queries['test_file_candidates'][:10]:
            print_item(f"  - {test_file}", "")
        if len(search_queries['test_file_candidates']) > 10:
            print_item(f"  ... and {len(search_queries['test_file_candidates']) - 10} more", "")
        print()
    
    print_item("Database tables to query", "")
    if search_queries.get('changed_functions'):
        print_item("  - test_function_mapping", "(function-level - highest precision)")
    print_item("  - reverse_index", "(class/module-level - fast lookup)")
    print_item("  - test_registry", "(for direct test file matching)")
    print()


def query_tests_for_functions(conn, changed_functions: List[Dict[str, str]]) -> List[Dict]:
    """
    Query database for tests that call/patch specific functions.
    
    This is the most precise matching strategy - only selects tests that
    actually call or patch the changed functions.
    
    Args:
        conn: Database connection
        changed_functions: List of {'module': 'agent.langgraph_agent', 'function': 'initialize'}
    
    Returns:
        List of test dictionaries with match details
    """
    if not changed_functions:
        return []
    
    all_tests = []
    seen_test_ids = set()
    
    with conn.cursor() as cursor:
        for func_change in changed_functions:
            module_name = func_change['module']
            function_name = func_change['function']
            
            # Query test_function_mapping table
            cursor.execute(f"""
                SELECT DISTINCT 
                    tr.test_id, 
                    tr.class_name, 
                    tr.method_name, 
                    tr.file_path,
                    tr.test_type,
                    tfm.call_type,
                    tfm.source,
                    CASE WHEN tfm.source = 'patch_ref' THEN 1 ELSE 2 END as source_priority
                FROM {DB_SCHEMA}.test_function_mapping tfm
                JOIN {DB_SCHEMA}.test_registry tr ON tfm.test_id = tr.test_id
                WHERE tfm.module_name = %s
                AND tfm.function_name = %s
                ORDER BY 
                    source_priority,
                    tr.test_id
            """, (module_name, function_name))
            
            for row in cursor.fetchall():
                test_id = row[0]
                if test_id not in seen_test_ids:
                    seen_test_ids.add(test_id)
                    all_tests.append({
                        'test_id': test_id,
                        'class_name': row[1],
                        'method_name': row[2],
                        'test_file_path': row[3],
                        'test_type': row[4],
                        'call_type': row[5],
                        'source': row[6],
                        'matched_module': module_name,
                        'matched_function': function_name
                    })
    
    return all_tests


def query_tests_for_classes(conn, production_classes: List[str]) -> Dict[str, List[Dict]]:
    """
    Query database to find tests for given production classes.
    
    Args:
        conn: Database connection
        production_classes: List of production class/module names
    
    Returns:
        Dictionary mapping production_class -> list of test dictionaries
    """
    results = {}
    
    for prod_class in production_classes:
        tests = get_tests_for_production_class(conn, prod_class, schema=DB_SCHEMA)
        if tests:
            results[prod_class] = tests
    
    return results


def query_tests_module_pattern(conn, module_pattern: str, prefer_direct: bool = True, 
                                specific_classes: List[str] = None) -> List[Dict]:
    """
    Query database for tests matching a module pattern (e.g., 'agent.*').
    
    Prefers direct references (direct_import, string_ref) over indirect ones.
    If specific_classes is provided, only matches tests referencing those specific classes.
    
    Args:
        conn: Database connection
        module_pattern: Pattern like 'agent.*'
        prefer_direct: If True, prefer direct references over indirect
        specific_classes: Optional list of specific class names to match (filters broad module matches)
    
    Returns:
        List of test dictionaries with reference_type
    """
    module_prefix = module_pattern.replace('.*', '')
    
    with conn.cursor() as cursor:
        if prefer_direct:
            # Build WHERE clause with optional specific class filtering
            if specific_classes and len(specific_classes) > 0:
                # Only match specific classes within the module
                placeholders = ','.join(['%s'] * len(specific_classes))
                # Build parameters: 
                # 1. For CASE statement: module_prefix
                # 2. For IN clause: all specific_classes
                # 3. For OR clause: module_prefix
                params = [module_prefix] + list(specific_classes) + [module_prefix]
                cursor.execute(f"""
                    SELECT DISTINCT 
                        tr.test_id, 
                        tr.class_name, 
                        tr.method_name, 
                        tr.file_path,
                        ri.reference_type,
                        CASE WHEN ri.production_class = %s THEN 1 ELSE 2 END as exact_match_priority,
                        CASE WHEN ri.reference_type IN ('direct_import', 'string_ref') THEN 1 ELSE 2 END as ref_type_priority
                    FROM {DB_SCHEMA}.reverse_index ri
                    JOIN {DB_SCHEMA}.test_registry tr ON ri.test_id = tr.test_id
                    WHERE ri.production_class IN ({placeholders})
                       OR (ri.production_class = %s AND ri.reference_type IN ('direct_import', 'string_ref'))
                    ORDER BY 
                        exact_match_priority,
                        ref_type_priority,
                        tr.test_id
                """, params)
            else:
                # Prefer exact module match and direct references
                cursor.execute(f"""
                    SELECT DISTINCT 
                        tr.test_id, 
                        tr.class_name, 
                        tr.method_name, 
                        tr.file_path,
                        ri.reference_type,
                        CASE WHEN ri.production_class = %s THEN 1 ELSE 2 END as exact_match_priority,
                        CASE WHEN ri.reference_type IN ('direct_import', 'string_ref') THEN 1 ELSE 2 END as ref_type_priority
                    FROM {DB_SCHEMA}.reverse_index ri
                    JOIN {DB_SCHEMA}.test_registry tr ON ri.test_id = tr.test_id
                    WHERE ri.production_class = %s
                       OR (ri.production_class LIKE %s 
                           AND ri.reference_type IN ('direct_import', 'string_ref'))
                    ORDER BY 
                        exact_match_priority,
                        ref_type_priority,
                        tr.test_id
                """, (module_prefix, module_prefix, f"{module_prefix}.%"))
        else:
            # Fallback to original broad match
            cursor.execute(f"""
                SELECT DISTINCT tr.test_id, tr.class_name, tr.method_name, tr.file_path, ri.reference_type
                FROM {DB_SCHEMA}.reverse_index ri
                JOIN {DB_SCHEMA}.test_registry tr ON ri.test_id = tr.test_id
                WHERE ri.production_class LIKE %s
                ORDER BY tr.test_id
            """, (f"{module_prefix}.%",))
        
        results = cursor.fetchall()
        # Extract test fields including reference_type
        return [
            {
                'test_id': row[0],
                'class_name': row[1],
                'method_name': row[2],
                'test_file_path': row[3],
                'reference_type': row[4] if len(row) > 4 else 'direct_import'
            }
            for row in results
        ]


def find_direct_test_files_enhanced(conn, test_file_candidates: List[str], 
                                     module_name: str = None, 
                                     file_path: str = None) -> List[Dict]:
    """
    Enhanced direct test file matching with multiple strategies.
    
    Works with any test repository structure and finds tests using:
    1. Exact filename matches
    2. Pattern matches (test_*.py)
    3. Path-based searches
    4. Module name-based searches
    
    Args:
        conn: Database connection
        test_file_candidates: List of test file names to search for
        module_name: Optional module name (e.g., "agent.agent_pool")
        file_path: Optional production file path for additional patterns
    
    Returns:
        List of test dictionaries with match details
    """
    if not test_file_candidates:
        return []
    
    direct_tests = []
    seen_test_ids = set()  # Avoid duplicates
    
    with conn.cursor() as cursor:
        # Strategy 1: Exact filename matches
        for test_file in test_file_candidates:
            # Remove wildcard patterns for exact match
            exact_file = test_file.replace('*.py', '.py')
            
            patterns = [
                f"%{exact_file}",  # Filename anywhere in path
                f"%\\{exact_file}",  # Filename at end (Windows)
                f"%/{exact_file}",  # Filename at end (Unix)
            ]
            
            for pattern in patterns:
                cursor.execute(f"""
                    SELECT DISTINCT test_id, class_name, method_name, file_path, test_type
                    FROM {DB_SCHEMA}.test_registry
                    WHERE file_path LIKE %s
                    ORDER BY test_id
                """, (pattern,))
                
                for row in cursor.fetchall():
                    test_id = row[0]
                    if test_id not in seen_test_ids:
                        seen_test_ids.add(test_id)
                        direct_tests.append({
                            'test_id': test_id,
                            'class_name': row[1],
                            'method_name': row[2],
                            'test_file_path': row[3],
                            'test_type': row[4],
                            'match_type': 'direct_test_file',
                            'match_strategy': 'exact_filename'
                        })
        
        # Strategy 2: Pattern-based matches (for parameterized tests)
        for test_file in test_file_candidates:
            if '*.py' in test_file:
                # Extract base name before wildcard
                base_name = test_file.replace('test_', '').replace('_*.py', '').replace('*.py', '')
                
                # Try patterns: test_<base>_*.py, test_*<base>*.py
                pattern1 = f"%test_{base_name}_%"
                pattern2 = f"%test_%{base_name}%"
                
                for pattern in [pattern1, pattern2]:
                    cursor.execute(f"""
                        SELECT DISTINCT test_id, class_name, method_name, file_path, test_type
                        FROM {DB_SCHEMA}.test_registry
                        WHERE file_path LIKE %s
                        ORDER BY test_id
                    """, (pattern,))
                    
                    for row in cursor.fetchall():
                        test_id = row[0]
                        if test_id not in seen_test_ids:
                            seen_test_ids.add(test_id)
                            direct_tests.append({
                                'test_id': test_id,
                                'class_name': row[1],
                                'method_name': row[2],
                                'test_file_path': row[3],
                                'test_type': row[4],
                                'match_type': 'direct_test_file',
                                'match_strategy': 'pattern_match'
                            })
        
        # Strategy 3: Module name-based search (if module_name provided)
        if module_name:
            # Extract base name from module
            module_basename = module_name.split('.')[-1]
            
            # Search for any test file containing the module basename
            cursor.execute(f"""
                SELECT DISTINCT test_id, class_name, method_name, file_path, test_type
                FROM {DB_SCHEMA}.test_registry
                WHERE file_path LIKE %s
                   OR file_path LIKE %s
                ORDER BY test_id
            """, (f"%test_{module_basename}%", f"%{module_basename}%"))
            
            for row in cursor.fetchall():
                test_id = row[0]
                if test_id not in seen_test_ids:
                    seen_test_ids.add(test_id)
                    direct_tests.append({
                        'test_id': test_id,
                        'class_name': row[1],
                        'method_name': row[2],
                        'test_file_path': row[3],
                        'test_type': row[4],
                        'match_type': 'direct_test_file',
                        'match_strategy': 'module_basename'
                    })
        
        # Strategy 4: File path-based search (if file_path provided)
        if file_path:
            from pathlib import Path
            path_obj = Path(file_path)
            file_stem = path_obj.stem
            
            # Search for test files with similar names
            cursor.execute(f"""
                SELECT DISTINCT test_id, class_name, method_name, file_path, test_type
                FROM {DB_SCHEMA}.test_registry
                WHERE file_path LIKE %s
                   OR file_path LIKE %s
                ORDER BY test_id
            """, (f"%{file_stem}%", f"%test_{file_stem}%"))
            
            for row in cursor.fetchall():
                test_id = row[0]
                if test_id not in seen_test_ids:
                    seen_test_ids.add(test_id)
                    direct_tests.append({
                        'test_id': test_id,
                        'class_name': row[1],
                        'method_name': row[2],
                        'test_file_path': row[3],
                        'test_type': row[4],
                        'match_type': 'direct_test_file',
                        'match_strategy': 'file_path_based'
                    })
    
    return direct_tests


def find_direct_test_files(conn, test_file_candidates: List[str]) -> List[Dict]:
    """
    Find test files that directly test changed production files.
    
    This is a wrapper that calls the enhanced version for backward compatibility.
    
    Args:
        conn: Database connection
        test_file_candidates: List of test file names to search for
    
    Returns:
        List of test dictionaries
    """
    return find_direct_test_files_enhanced(conn, test_file_candidates)


def find_affected_tests(conn, search_queries: Dict, file_changes: List[Dict] = None) -> Dict[str, Any]:
    """
    Find all affected tests using multiple search strategies with enhanced matching.
    
    Strategies (in priority order):
    0. Function-level matching (very high confidence) - NEW
    1. Direct test files (high confidence)
    2. Integration/e2e tests (high confidence)
    3. Exact class/module matches (high confidence)
    4. Module patterns with direct references (medium confidence)
    
    Args:
        conn: Database connection
        search_queries: Dictionary with search strategies
        file_changes: List of file change dictionaries (for filtering import-only changes)
    
    Returns:
        Dictionary with test results and metadata
    """
    all_tests = {}  # test_id -> test info with match details
    match_details = {}  # test_id -> list of match reasons
    
    # Strategy 0: Function-level matching (very high confidence) - NEW
    if search_queries.get('changed_functions'):
        print_section("Querying database (Function-level matching - highest precision)...")
        function_tests = query_tests_for_functions(conn, search_queries['changed_functions'])
        
        if function_tests:
            print_item(f"  Found {len(function_tests)} test(s) via function-level matching", "")
            
            # Group by function to show what matched
            by_function = {}
            for test in function_tests:
                func_key = f"{test['matched_module']}.{test['matched_function']}"
                if func_key not in by_function:
                    by_function[func_key] = []
                by_function[func_key].append(test)
            
            # Show which functions matched (first 10)
            print_item("  Matched functions", "")
            for func_key, tests in list(by_function.items())[:10]:
                test_count = len(tests)
                test_names = [f"{t.get('class_name', '')}.{t.get('method_name', '')}" if t.get('class_name') else t.get('method_name', '') for t in tests[:3]]
                test_list = ", ".join(test_names)
                if test_count > 3:
                    test_list += f" ... (+{test_count - 3} more)"
                print_item(f"    - {func_key}", f"({test_count} test(s): {test_list})")
            if len(by_function) > 10:
                print_item(f"    ... and {len(by_function) - 10} more functions", "")
            
            for test in function_tests:
                test_id = test['test_id']
                if test_id not in all_tests:
                    all_tests[test_id] = test
                    match_details[test_id] = []
                match_details[test_id].append({
                    'type': 'function_level',
                    'module': test['matched_module'],
                    'function': test['matched_function'],
                    'call_type': test.get('call_type'),
                    'source': test.get('source'),
                    'confidence': 'very_high'
                })
        else:
            print_item("  No function-level matches found", "")
            print_item("  (Falling back to file-level matching)", "")
        print()
    
    # Strategy 1: Direct test files (high confidence) - Enhanced
    if search_queries.get('test_file_candidates'):
        print_section("Querying database (Direct test files - enhanced multi-strategy)...")
        
        # Build module name and file path mappings for enhanced search
        module_file_map = {}
        if file_changes:
            from utils.diff_parser import extract_production_classes_from_file
            for file_change in file_changes:
                file_path = file_change.get('file', '')
                if file_path and file_path.endswith('.py'):
                    classes = extract_production_classes_from_file(file_path)
                    if classes:
                        module_file_map[classes[0]] = file_path
        
        # Use enhanced direct test file finder
        direct_tests = []
        for candidate in search_queries['test_file_candidates']:
            # Try to find matching module/file for this candidate
            module_name = None
            file_path = None
            for mod, fp in module_file_map.items():
                if candidate.replace('test_', '').replace('.py', '') in mod or \
                   candidate.replace('test_', '').replace('.py', '') in fp:
                    module_name = mod
                    file_path = fp
                    break
            
            enhanced_results = find_direct_test_files_enhanced(
                conn, [candidate], 
                module_name=module_name,
                file_path=file_path
            )
            direct_tests.extend(enhanced_results)
        
        # Remove duplicates
        seen_ids = set()
        unique_direct_tests = []
        for test in direct_tests:
            if test['test_id'] not in seen_ids:
                seen_ids.add(test['test_id'])
                unique_direct_tests.append(test)
        direct_tests = unique_direct_tests
        
        print_item(f"  Found {len(direct_tests)} direct test file(s)", "")
        
        # Group by test file to show which files matched
        matched_files = {}
        for test in direct_tests:
            test_file = test.get('test_file_path', 'unknown')
            if test_file not in matched_files:
                matched_files[test_file] = []
            matched_files[test_file].append(test)
        
        # Show which test files matched (first 10)
        if matched_files:
            print_item("  Matched test files", "")
            for test_file, tests in list(matched_files.items())[:10]:
                test_count = len(tests)
                test_names = [f"{t.get('class_name', '')}.{t.get('method_name', '')}" if t.get('class_name') else t.get('method_name', '') for t in tests[:3]]
                test_list = ", ".join(test_names)
                if test_count > 3:
                    test_list += f" ... (+{test_count - 3} more)"
                match_strategy = tests[0].get('match_strategy', 'unknown')
                print_item(f"    - {test_file}", f"({test_count} test(s), {match_strategy}: {test_list})")
            if len(matched_files) > 10:
                print_item(f"    ... and {len(matched_files) - 10} more test files", "")
        
        for test in direct_tests:
            test_id = test['test_id']
            if test_id not in all_tests:
                all_tests[test_id] = test
                match_details[test_id] = []
            match_details[test_id].append({
                'type': 'direct_file',
                'test_file': test.get('test_file_path', ''),
                'match_strategy': test.get('match_strategy', 'exact_filename'),
                'confidence': 'very_high'
            })
        print()
    
    # Strategy 1.5: Integration tests for changed modules
    if file_changes:
        print_section("Querying database (Integration/e2e tests)...")
        from utils.diff_parser import extract_production_classes_from_file, analyze_file_change_type
        
        integration_tests_found = []
        for file_change in file_changes:
            file_path = file_change.get('file', '')
            change_type = analyze_file_change_type(file_change)
            
            # Skip import-only changes
            if change_type == 'import_only':
                continue
            
            if file_path and file_path.endswith('.py'):
                classes = extract_production_classes_from_file(file_path)
                for module_name in classes[:1]:  # Check first class only
                    integration_tests = find_integration_tests_for_module(conn, module_name)
                    for test in integration_tests:
                        test_id = test['test_id']
                        if test_id not in all_tests:
                            all_tests[test_id] = test
                            match_details[test_id] = []
                        match_details[test_id].append({
                            'type': 'integration',
                            'module': module_name,
                            'confidence': 'high'
                        })
                        integration_tests_found.append(test)
        
        if integration_tests_found:
            print_item(f"  Found {len(integration_tests_found)} integration/e2e test(s)", "")
            # Group by test type
            by_type = {}
            for test in integration_tests_found:
                test_type = test.get('test_type', 'unknown')
                if test_type not in by_type:
                    by_type[test_type] = []
                by_type[test_type].append(test)
            
            for test_type, tests in by_type.items():
                print_item(f"    {test_type.capitalize()} tests", f"{len(tests)} test(s)")
        else:
            print_item("  No integration/e2e tests found", "")
        print()
    
    # Strategy 2: Exact matches (high confidence) - includes string references from patch()
    if search_queries['exact_matches']:
        print_section("Querying database (Exact matches - includes string refs from patch/Mock)...")
        exact_results = query_tests_for_classes(conn, search_queries['exact_matches'])
        
        if exact_results:
            for prod_class, tests in exact_results.items():
                # Count by reference type
                string_refs = sum(1 for t in tests if t.get('reference_type') == 'string_ref')
                direct_imports = len(tests) - string_refs
                
                ref_info = []
                if string_refs > 0:
                    ref_info.append(f"{string_refs} via patch/Mock")
                if direct_imports > 0:
                    ref_info.append(f"{direct_imports} via import")
                
                ref_detail = f" ({', '.join(ref_info)})" if ref_info else ""
                print_item(f"  {prod_class}", f"{len(tests)} tests{ref_detail}")
                
                for test in tests:
                    test_id = test['test_id']
                    if test_id not in all_tests:
                        all_tests[test_id] = test
                        match_details[test_id] = []
                    match_details[test_id].append({
                        'type': 'exact',
                        'class': prod_class,
                        'reference_type': test.get('reference_type', 'direct_import'),
                        'confidence': 'high'
                    })
        else:
            print_item("  No exact matches found", "")
            # Debug: Check what's actually in the database
            if search_queries['exact_matches']:
                with conn.cursor() as cursor:
                    first_match = search_queries['exact_matches'][0]
                    cursor.execute(f"""
                        SELECT DISTINCT production_class, reference_type
                        FROM {DB_SCHEMA}.reverse_index 
                        WHERE production_class LIKE %s OR production_class = %s
                        LIMIT 5
                    """, (f"{first_match}%", first_match))
                    sample_classes = cursor.fetchall()
                    if sample_classes:
                        print_item("  Sample production classes in database", 
                                  ", ".join([f"{row[0]} ({row[1]})" for row in sample_classes[:3]]))
                    else:
                        # Check if database has any data
                        cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.reverse_index")
                        count = cursor.fetchone()[0]
                        if count == 0:
                            print_item("  WARNING: reverse_index table is empty!", "")
                            print_item("    Re-run test analysis to extract string references", "")
                            print_item("      1. python test_analysis/04_extract_static_dependencies.py", "")
                            print_item("      2. python test_analysis/06_build_reverse_index.py", "")
                            print_item("      3. python deterministic/04_load_reverse_index.py", "")
        print()
    
    # Strategy 3: Module-level matches (prefer direct references, skip import-only changes)
    if search_queries['module_matches']:
        print_section("Querying database (Module patterns - direct references only)...")
        
        # Build map of module -> specific changed classes for better filtering
        from utils.diff_parser import analyze_file_change_type, extract_production_classes_from_file
        module_to_classes = {}  # module_prefix -> set of changed classes
        code_changed_modules = set()
        
        if file_changes:
            for file_change in file_changes:
                change_type = analyze_file_change_type(file_change)
                if change_type == 'code':  # Only include modules with actual code changes
                    file_path = file_change['file']
                    classes = extract_production_classes_from_file(file_path)
                    for class_name in classes:
                        if '.' in class_name:
                            module_part = class_name.split('.')[0]
                            code_changed_modules.add(module_part)
                            if module_part not in module_to_classes:
                                module_to_classes[module_part] = set()
                            module_to_classes[module_part].add(class_name)
        
        for module_pattern in search_queries['module_matches']:
            module_prefix = module_pattern.replace('.*', '')
            
            # Skip if this module only had import-only changes
            if code_changed_modules and module_prefix not in code_changed_modules:
                print_item(f"  {module_pattern}", "0 tests (skipped - import-only changes)")
                continue
            
            # Get specific classes that changed in this module for better filtering
            specific_classes = list(module_to_classes.get(module_prefix, []))
            
            # Use prefer_direct=True and filter by specific changed classes
            module_tests = query_tests_module_pattern(
                conn, module_pattern, 
                prefer_direct=True,
                specific_classes=specific_classes if specific_classes else None
            )
            
            # Count by reference type
            string_refs = sum(1 for t in module_tests if t.get('reference_type') == 'string_ref')
            direct_imports = len(module_tests) - string_refs
            ref_info = []
            if string_refs > 0:
                ref_info.append(f"{string_refs} via patch/Mock")
            if direct_imports > 0:
                ref_info.append(f"{direct_imports} via import")
            ref_detail = f" ({', '.join(ref_info)})" if ref_info else ""
            
            print_item(f"  {module_pattern}", f"{len(module_tests)} tests{ref_detail}")
            
            for test in module_tests:
                test_id = test['test_id']
                if test_id not in all_tests:
                    all_tests[test_id] = test
                    match_details[test_id] = []
                match_details[test_id].append({
                    'type': 'module',
                    'pattern': module_pattern,
                    'reference_type': test.get('reference_type', 'direct_import'),
                    'confidence': 'medium'
                })
        print()
    
    # Strategy 4: Semantic search (catches what name matching misses)
    changed_functions_for_semantic = search_queries.get('changed_functions', [])
    if changed_functions_for_semantic:
        print_section("Querying database (Semantic search - meaning-based)...")
        try:
            semantic_matches = asyncio.run(
                find_tests_semantic(conn, changed_functions_for_semantic)
            )

            # Only add tests NOT already found by strategies 0-3
            semantic_added = 0
            for test in semantic_matches:
                test_id = test['test_id']
                if test_id not in all_tests:
                    all_tests[test_id] = test
                    match_details[test_id] = [{
                        'type':       'semantic',
                        'similarity': test['similarity'],
                        'confidence': 'medium'
                    }]
                    semantic_added += 1

            if semantic_added > 0:
                print_item(
                    f"  Found {semantic_added} additional test(s) via semantic search",
                    "(not found by name matching)"
                )
            else:
                print_item("  Semantic search: no additional tests found", "")

        except Exception as e:
            # Semantic is optional — don't fail if Ollama is not running
            print_item("  Semantic search skipped", f"(Ollama unavailable: {e})")
        print()
    
    # Attach confidence score to every matched test
    for test_id, test in all_tests.items():
        matches   = match_details.get(test_id, [])
        test_type = test.get('test_type')
        test['confidence_score'] = calculate_confidence_score(matches, test_type)

    # Sort by score descending — highest confidence runs first
    sorted_tests = sorted(
        all_tests.values(),
        key=lambda t: t.get('confidence_score', 0),
        reverse=True
    )

    return {
        'tests':         sorted_tests,
        'match_details': match_details,
        'total_tests':   len(all_tests)
    }


def find_tests_ast_only(conn, search_queries: Dict, file_changes: List[Dict] = None) -> Dict[str, Any]:
    """
    Find tests using only AST-based strategies (0-3), excluding semantic search.
    
    Returns:
        Dictionary with test results from AST-based matching only
    """
    all_tests = {}
    match_details = {}
    
    # Strategy 0: Function-level matching
    if search_queries.get('changed_functions'):
        function_tests = query_tests_for_functions(conn, search_queries['changed_functions'])
        for test in function_tests:
            test_id = test['test_id']
            if test_id not in all_tests:
                all_tests[test_id] = test
                match_details[test_id] = []
            match_details[test_id].append({
                'type': 'function_level',
                'module': test.get('matched_module', ''),
                'function': test.get('matched_function', ''),
                'source': test.get('source', ''),
                'confidence': 'very_high'
            })
    
    # Strategy 1: Direct test files
    if search_queries.get('test_file_candidates'):
        direct_tests = find_direct_test_files_enhanced(
            conn, 
            search_queries['test_file_candidates']
        )
        for test in direct_tests:
            test_id = test['test_id']
            if test_id not in all_tests:
                all_tests[test_id] = test
                match_details[test_id] = []
            match_details[test_id].append({
                'type': 'direct_file',
                'test_file': test.get('test_file_path', ''),
                'match_strategy': test.get('match_strategy', 'exact_filename'),
                'confidence': 'very_high'
            })
    
    # Strategy 1.5: Integration tests
    if file_changes:
        for file_change in file_changes:
            file_path = file_change.get('file', '')
            if file_path and file_path.endswith('.py'):
                from utils.diff_parser import extract_production_classes_from_file, analyze_file_change_type
                change_type = analyze_file_change_type(file_change)
                if change_type != 'import_only':
                    classes = extract_production_classes_from_file(file_path)
                    for module_name in classes[:1]:
                        integration_tests = find_integration_tests_for_module(conn, module_name)
                        for test in integration_tests:
                            test_id = test['test_id']
                            if test_id not in all_tests:
                                all_tests[test_id] = test
                                match_details[test_id] = []
                            match_details[test_id].append({
                                'type': 'integration',
                                'module': module_name,
                                'confidence': 'high'
                            })
    
    # Strategy 2: Exact matches
    if search_queries.get('exact_matches'):
        for prod_class in search_queries['exact_matches']:
            exact_tests = query_tests_for_classes(conn, [prod_class])
            for test_list in exact_tests.values():
                for test in test_list:
                    test_id = test['test_id']
                    if test_id not in all_tests:
                        all_tests[test_id] = test
                        match_details[test_id] = []
                    match_details[test_id].append({
                        'type': 'exact',
                        'class': prod_class,
                        'reference_type': test.get('reference_type', 'direct_import'),
                        'confidence': 'high'
                    })
    
    # Strategy 3: Module patterns
    if search_queries.get('module_matches'):
        for module_pattern in search_queries['module_matches']:
            module_tests = query_tests_module_pattern(conn, module_pattern, prefer_direct=True)
            for test in module_tests:
                test_id = test['test_id']
                if test_id not in all_tests:
                    all_tests[test_id] = test
                    match_details[test_id] = []
                match_details[test_id].append({
                    'type': 'module',
                    'pattern': module_pattern,
                    'reference_type': test.get('reference_type', 'direct_import'),
                    'confidence': 'medium'
                })
    
    # Calculate scores
    for test_id, test in all_tests.items():
        matches = match_details.get(test_id, [])
        test_type = test.get('test_type')
        test['confidence_score'] = calculate_confidence_score(matches, test_type)
    
    # Sort by score
    sorted_tests = sorted(
        all_tests.values(),
        key=lambda t: t.get('confidence_score', 0),
        reverse=True
    )
    
    return {
        'tests': sorted_tests,
        'match_details': match_details,
        'total_tests': len(all_tests),
        'method': 'AST'
    }


def find_tests_semantic_only(conn, search_queries: Dict) -> Dict[str, Any]:
    """
    Find tests using only semantic search (vector embeddings).
    
    Returns:
        Dictionary with test results from semantic search only
    """
    all_tests = {}
    match_details = {}
    
    changed_functions = search_queries.get('changed_functions', [])
    if not changed_functions:
        return {
            'tests': [],
            'match_details': {},
            'total_tests': 0,
            'method': 'Semantic'
        }
    
    try:
        semantic_matches = asyncio.run(
            find_tests_semantic(conn, changed_functions)
        )
        
        for test in semantic_matches:
            test_id = test['test_id']
            all_tests[test_id] = test
            match_details[test_id] = [{
                'type': 'semantic',
                'similarity': test.get('similarity', 0),
                'confidence': 'medium'
            }]
        
        # Sort by similarity (descending)
        sorted_tests = sorted(
            all_tests.values(),
            key=lambda t: t.get('similarity', 0),
            reverse=True
        )
        
        return {
            'tests': sorted_tests,
            'match_details': match_details,
            'total_tests': len(all_tests),
            'method': 'Semantic'
        }
    except Exception as e:
        return {
            'tests': [],
            'match_details': {},
            'total_tests': 0,
            'method': 'Semantic',
            'error': str(e)
        }


def compare_ast_vs_semantic(ast_results: Dict, semantic_results: Dict) -> Dict[str, Any]:
    """
    Compare results from AST-based matching vs semantic search.
    
    Returns:
        Dictionary with comparison statistics
    """
    ast_test_ids = {t['test_id'] for t in ast_results['tests']}
    semantic_test_ids = {t['test_id'] for t in semantic_results['tests']}
    
    only_ast = ast_test_ids - semantic_test_ids
    only_semantic = semantic_test_ids - ast_test_ids
    both = ast_test_ids & semantic_test_ids
    
    return {
        'ast_only': list(only_ast),
        'semantic_only': list(only_semantic),
        'both': list(both),
        'ast_count': len(ast_test_ids),
        'semantic_count': len(semantic_test_ids),
        'overlap_count': len(both),
        'ast_only_count': len(only_ast),
        'semantic_only_count': len(only_semantic),
        'overlap_percentage': round((len(both) / max(len(ast_test_ids), 1)) * 100, 1) if ast_test_ids else 0
    }


def save_comparison_report(ast_results: Dict, semantic_results: Dict, 
                          comparison: Dict, diff_file_path: str = None, 
                          output_dir: Path = None) -> Path:
    """
    Save comparison report between AST and semantic methods.
    """
    from datetime import datetime
    
    if output_dir is None:
        output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if diff_file_path:
        diff_name = Path(diff_file_path).stem
        output_filename = f"comparison_ast_vs_semantic_{diff_name}_{timestamp}.txt"
    else:
        output_filename = f"comparison_ast_vs_semantic_{timestamp}.txt"
    
    output_path = output_dir / output_filename
    
    lines = []
    lines.append("=" * 80)
    lines.append("AST vs SEMANTIC SEARCH COMPARISON REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if diff_file_path:
        lines.append(f"Diff File: {diff_file_path}")
    lines.append("")
    
    # Summary statistics
    lines.append("-" * 80)
    lines.append("SUMMARY STATISTICS")
    lines.append("-" * 80)
    lines.append("")
    lines.append(f"AST-based matching found:     {comparison['ast_count']} tests")
    lines.append(f"Semantic search found:        {comparison['semantic_count']} tests")
    lines.append(f"Found by both methods:        {comparison['overlap_count']} tests")
    lines.append(f"Found only by AST:            {comparison['ast_only_count']} tests")
    lines.append(f"Found only by Semantic:       {comparison['semantic_only_count']} tests")
    if comparison['ast_count'] > 0:
        lines.append(f"Overlap percentage:           {comparison['overlap_percentage']}%")
    lines.append("")
    
    # Tests found by both
    if comparison['both']:
        lines.append("-" * 80)
        lines.append(f"TESTS FOUND BY BOTH METHODS ({len(comparison['both'])} tests)")
        lines.append("-" * 80)
        lines.append("")
        for test_id in comparison['both']:
            ast_test = next((t for t in ast_results['tests'] if t['test_id'] == test_id), None)
            semantic_test = next((t for t in semantic_results['tests'] if t['test_id'] == test_id), None)
            if ast_test and semantic_test:
                test_name = f"{ast_test.get('class_name', '')}.{ast_test.get('method_name', '')}" if ast_test.get('class_name') else ast_test.get('method_name', '')
                ast_score = ast_test.get('confidence_score', 0)
                semantic_sim = int(semantic_test.get('similarity', 0) * 100)
                lines.append(f"  {test_id}: {test_name}")
                lines.append(f"    AST Score: {ast_score} | Semantic Similarity: {semantic_sim}%")
        lines.append("")
    
    # Tests found only by AST
    if comparison['ast_only']:
        lines.append("-" * 80)
        lines.append(f"TESTS FOUND ONLY BY AST ({len(comparison['ast_only'])} tests)")
        lines.append("-" * 80)
        lines.append("")
        for test_id in comparison['ast_only']:
            test = next((t for t in ast_results['tests'] if t['test_id'] == test_id), None)
            if test:
                test_name = f"{test.get('class_name', '')}.{test.get('method_name', '')}" if test.get('class_name') else test.get('method_name', '')
                score = test.get('confidence_score', 0)
                lines.append(f"  [{score:3d}] {test_id}: {test_name}")
        lines.append("")
    
    # Tests found only by Semantic
    if comparison['semantic_only']:
        lines.append("-" * 80)
        lines.append(f"TESTS FOUND ONLY BY SEMANTIC SEARCH ({len(comparison['semantic_only'])} tests)")
        lines.append("-" * 80)
        lines.append("")
        for test_id in comparison['semantic_only']:
            test = next((t for t in semantic_results['tests'] if t['test_id'] == test_id), None)
            if test:
                test_name = f"{test.get('class_name', '')}.{test.get('method_name', '')}" if test.get('class_name') else test.get('method_name', '')
                similarity = int(test.get('similarity', 0) * 100)
                lines.append(f"  [{similarity:3d}%] {test_id}: {test_name}")
        lines.append("")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return output_path


def get_all_tests_from_database(conn) -> Dict[str, Dict]:
    """
    Get all tests from the test_registry table.
    
    Args:
        conn: Database connection
    
    Returns:
        Dictionary mapping test_id -> test dictionary
    """
    all_tests = {}
    
    with conn.cursor() as cursor:
        cursor.execute(f"""
            SELECT test_id, file_path, class_name, method_name, test_type
            FROM {DB_SCHEMA}.test_registry
            ORDER BY test_id
        """)
        
        for row in cursor.fetchall():
            test_id, file_path, class_name, method_name, test_type = row
            all_tests[test_id] = {
                'test_id': test_id,
                'file_path': file_path,
                'class_name': class_name,
                'method_name': method_name,
                'test_type': test_type
            }
    
    return all_tests


def find_integration_tests_for_module(conn, production_class: str) -> List[Dict]:
    """
    Find integration/e2e tests that reference a production module.
    
    Args:
        conn: Database connection
        production_class: Production class/module name (e.g., "agent.langgraph_agent")
    
    Returns:
        List of test dictionaries (integration/e2e tests only)
    """
    integration_tests = []
    
    with conn.cursor() as cursor:
        # Query for integration/e2e tests that reference this production class
        cursor.execute(f"""
            SELECT DISTINCT 
                tr.test_id, 
                tr.class_name, 
                tr.method_name, 
                tr.file_path,
                tr.test_type,
                ri.reference_type
            FROM {DB_SCHEMA}.reverse_index ri
            JOIN {DB_SCHEMA}.test_registry tr ON ri.test_id = tr.test_id
            WHERE ri.production_class = %s
              AND tr.test_type IN ('integration', 'e2e')
            ORDER BY tr.test_type, tr.test_id
        """, (production_class,))
        
        for row in cursor.fetchall():
            integration_tests.append({
                'test_id': row[0],
                'class_name': row[1],
                'method_name': row[2],
                'test_file_path': row[3],
                'test_type': row[4],
                'reference_type': row[5],
                'match_type': 'integration_test'
            })
    
    return integration_tests


def diagnose_missing_tests(conn, changed_files: List[Dict], 
                          search_queries: Dict) -> Dict[str, Any]:
    """
    Diagnose why expected tests might be missing.
    
    Args:
        conn: Database connection
        changed_files: List of changed file dictionaries
        search_queries: Search queries that were used
    
    Returns:
        Dictionary with diagnostic information for each changed file
    """
    diagnostics = {}
    
    from pathlib import Path
    from utils.diff_parser import extract_production_classes_from_file, extract_test_file_candidates
    
    with conn.cursor() as cursor:
        for file_change in changed_files:
            file_path = file_change.get('file', '')
            if not file_path or not file_path.endswith('.py'):
                continue
            
            # Extract module and test candidates
            classes = extract_production_classes_from_file(file_path)
            test_candidates = extract_test_file_candidates(file_path)
            
            if not classes:
                continue
            
            module_name = classes[0] if classes else None
            module_basename = module_name.split('.')[-1] if module_name else Path(file_path).stem
            
            # Check what patterns we're looking for
            expected_patterns = test_candidates
            
            # Check what exists in database
            found_tests = []
            for pattern in expected_patterns[:5]:  # Check first 5 patterns
                exact_pattern = pattern.replace('*.py', '.py')
                cursor.execute(f"""
                    SELECT test_id, file_path, test_type, class_name, method_name
                    FROM {DB_SCHEMA}.test_registry
                    WHERE file_path LIKE %s
                    LIMIT 10
                """, (f"%{exact_pattern}",))
                
                for row in cursor.fetchall():
                    found_tests.append({
                        'test_id': row[0],
                        'file_path': row[1],
                        'test_type': row[2],
                        'class_name': row[3],
                        'method_name': row[4]
                    })
            
            # Check what references exist in reverse_index
            found_references = []
            if module_name:
                cursor.execute(f"""
                    SELECT DISTINCT ri.test_id, ri.reference_type, tr.file_path, tr.test_type
                    FROM {DB_SCHEMA}.reverse_index ri
                    JOIN {DB_SCHEMA}.test_registry tr ON ri.test_id = tr.test_id
                    WHERE ri.production_class = %s
                    LIMIT 10
                """, (module_name,))
                
                for row in cursor.fetchall():
                    found_references.append({
                        'test_id': row[0],
                        'reference_type': row[1],
                        'file_path': row[2],
                        'test_type': row[3]
                    })
            
            # Generate suggestions
            suggestions = []
            if not found_tests and not found_references:
                suggestions.append("Test file might not be indexed. Run test repository indexer.")
                suggestions.append(f"Expected patterns: {', '.join(expected_patterns[:3])}")
            elif not found_tests and found_references:
                suggestions.append("Tests exist but don't follow naming convention. Using reference matching.")
                suggestions.append(f"Found {len(found_references)} tests via reverse_index")
            elif found_tests:
                suggestions.append(f"Found {len(found_tests)} direct test file matches")
            
            # Check for integration tests
            integration_count = sum(1 for t in found_references if t.get('test_type') in ('integration', 'e2e'))
            if integration_count > 0:
                suggestions.append(f"Found {integration_count} integration/e2e tests")
            
            diagnostics[file_path] = {
                'module_name': module_name,
                'module_basename': module_basename,
                'expected_patterns': expected_patterns,
                'tests_in_db': found_tests,
                'references_in_db': found_references,
                'found_direct': len(found_tests) > 0,
                'found_references': len(found_references) > 0,
                'suggestions': suggestions
            }
    
    return diagnostics


def find_unused_tests(conn, affected_test_ids: set) -> List[Dict]:
    """
    Find tests that are NOT affected by the changes.
    
    Args:
        conn: Database connection
        affected_test_ids: Set of test IDs that are affected
    
    Returns:
        List of test dictionaries that are not affected
    """
    all_tests = get_all_tests_from_database(conn)
    unused_tests = []
    
    for test_id, test in all_tests.items():
        if test_id not in affected_test_ids:
            unused_tests.append(test)
    
    return unused_tests


def calculate_confidence_score(
    match_details: list,
    test_type: str,
) -> int:
    """
    Calculate 0-100 confidence score from match_details list.

    Scoring:
      Match type weights (cumulative — a test can have multiple matches):
        function_level                        → +50
        exact + direct_import                 → +45
        exact + string_ref  (via patch/Mock)  → +40
        direct_file                           → +35
        integration                           → +25
        module pattern                        → +15

      Function-level precision bonus:
        any match of type 'function_level'    → +20 extra

      Test type bonus (applied once):
        unit                                  → +15
        integration                           → +5
        e2e / unknown / None                  → +0

    Capped at 100.
    """
    score = 0
    has_function_level = False

    for match in match_details:
        mtype    = match.get('type', '')
        ref_type = match.get('reference_type', '')

        if mtype == 'function_level':
            score += 50
            has_function_level = True
        elif mtype == 'exact' and ref_type == 'direct_import':
            score += 45
        elif mtype == 'exact' and ref_type == 'string_ref':
            score += 40
        elif mtype == 'direct_file':
            score += 35
        elif mtype == 'integration':
            score += 25
        elif mtype == 'module':
            score += 15

    # Function-level precision bonus
    if has_function_level:
        score += 20

    # Test type bonus
    test_type_lower = (test_type or '').lower()
    if test_type_lower == 'unit':
        score += 15
    elif test_type_lower == 'integration':
        score += 5

    return min(score, 100)


def get_total_test_count(conn) -> int:
    """Get total number of tests in test_registry for reduction % calculation."""
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.test_registry")
        return cursor.fetchone()[0]


def generate_pytest_commands(scored_tests: list, total_in_repo: int) -> dict:
    """
    Convert scored test list into three ready-to-run pytest commands.

    scored_tests — already sorted by confidence_score descending.
    Each test dict must have: test_file_path, class_name, method_name,
                              confidence_score, test_type

    Returns dict:
      run_all   — all selected tests
      run_high  — score >= 60 only
      run_fast  — score >= 60 AND test_type == 'unit' only
      stats     — counts and reduction percentage
    """

    def to_node_id(t: dict) -> str:
        # test_file_path is the correct key (not file_path) for all strategies
        # But some strategies return file_path, so use fallback
        file_path  = t.get('test_file_path') or t.get('file_path', '')
        class_name = t.get('class_name', '')
        method     = t.get('method_name', '')
        if class_name:
            return f"{file_path}::{class_name}::{method}"
        return f"{file_path}::{method}"

    all_tests  = scored_tests
    high_tests = [t for t in scored_tests
                  if t.get('confidence_score', 0) >= 60]
    fast_tests = [t for t in high_tests
                  if (t.get('test_type') or '').lower() == 'unit']

    def build_cmd(tests: list) -> str:
        if not tests:
            return "# No tests matched this filter"
        node_ids = [to_node_id(t) for t in tests]
        return "pytest " + " \\\n       ".join(node_ids) + " -v"

    selected      = len(all_tests)
    reduction_pct = (
        round((1 - selected / total_in_repo) * 100, 1)
        if total_in_repo > 0 else 0.0
    )

    return {
        "run_all":  build_cmd(all_tests),
        "run_high": build_cmd(high_tests),
        "run_fast": build_cmd(fast_tests),
        "stats": {
            "total_in_repo": total_in_repo,
            "selected":      selected,
            "high_priority": len(high_tests),
            "fast_subset":   len(fast_tests),
            "reduction_pct": reduction_pct,
        }
    }


def display_results(results: Dict, conn=None) -> None:
    """
    Display test selection results in a beginner-friendly way.
    
    Args:
        results: Dictionary from find_affected_tests
        conn: Optional database connection to show unused tests
    """
    print_section("Test Selection Results:")
    print()
    
    if results['total_tests'] == 0:
        print_item("No tests found!", "")
        print()
        print_item("Possible reasons", "")
        print_item("  - Changed files are not referenced by any tests", "")
        print_item("  - Changed files are test files themselves", "")
        print_item("  - Production class names don't match database", "")
        
        # Show unused tests if connection available
        if conn:
            print()
            print_section("All Tests (Not Affected):")
            unused_tests = find_unused_tests(conn, set())
            print_item(f"Total tests in repository", len(unused_tests))
            if unused_tests:
                print_item("Sample tests (first 10)", "")
                for test in unused_tests[:10]:
                    test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
                    test_type = test.get('test_type') or 'unknown'
                    print_item(f"  {test['test_id']}", f"{test_name} ({test_type})")
        return
    
    # Score-based display — tests already sorted by score from find_affected_tests()
    affected_test_ids = set()

    print_item(f"Found {results['total_tests']} affected test(s) — ranked by confidence", "")
    print()

    for test in results['tests']:
        test_id   = test['test_id']
        affected_test_ids.add(test_id)
        score     = test.get('confidence_score', 0)
        test_name = (
            f"{test['class_name']}.{test['method_name']}"
            if test.get('class_name')
            else test.get('method_name', '')
        )
        test_type = test.get('test_type') or 'unknown'
        matches   = results['match_details'].get(test_id, [])

        print_item(f"  [{score:3d}] {test_id}:", f"{test_name} ({test_type})")

        # Show top 2 match reasons
        shown = 0
        for m in matches:
            if shown >= 2:
                break
            mtype    = m.get('type', '')
            ref_type = m.get('reference_type', '')

            if mtype == 'function_level':
                func  = f"{m.get('module', '')}.{m.get('function', '')}"
                src   = m.get('source', '')
                label = '(via patch)' if src == 'patch_ref' else '(via call)'
                print_item(f"       -> function:", f"{func} {label}")
                shown += 1
            elif mtype == 'exact':
                label = '(via patch/Mock)' if ref_type == 'string_ref' else '(via import)'
                print_item(f"       -> class:", f"{m.get('class', '')} {label}")
                shown += 1
            elif mtype == 'direct_file':
                print_item(f"       -> direct file:", m.get('match_strategy', ''))
                shown += 1
            elif mtype == 'integration':
                print_item(f"       -> integration for:", m.get('module', ''))
                shown += 1
            elif mtype == 'module':
                print_item(f"       -> module pattern:", m.get('pattern', ''))
                shown += 1
            elif mtype == 'semantic':
                sim_pct = int(m.get('similarity', 0) * 100)
                print_item(f"       -> semantic similarity:", f"{sim_pct}%")
                shown += 1

    print()
    print_item("Score guide:",
        "85-100: function+unit  |  60-84: exact match  |  35-59: direct file  |  <35: module/pattern")
    print()
    
    # Score-based summary
    scores = [t.get('confidence_score', 0) for t in results['tests']]
    print_section("Summary:")
    print_item("Total tests to run", results['total_tests'])
    if scores:
        band_85 = sum(1 for s in scores if s >= 85)
        band_60 = sum(1 for s in scores if 60 <= s < 85)
        band_35 = sum(1 for s in scores if 35 <= s < 60)
        band_lo = sum(1 for s in scores if s < 35)
        if band_85: print_item("Score 85-100 (function-level precision)", band_85)
        if band_60: print_item("Score 60-84  (exact class/import match)", band_60)
        if band_35: print_item("Score 35-59  (direct file match)", band_35)
        if band_lo: print_item("Score  0-34  (module/pattern match)", band_lo)
        print_item("Highest score", max(scores))
        print_item("Lowest score",  min(scores))
    print()
    
    # Pytest commands
    if results['tests'] and conn:
        try:
            total_in_repo = get_total_test_count(conn)
            commands      = generate_pytest_commands(results['tests'], total_in_repo)
            stats         = commands['stats']

            print()
            print("=" * 70)
            print("PYTEST COMMANDS")
            print("=" * 70)
            print()
            print(
                f"Run ALL selected "
                f"({stats['selected']} of {stats['total_in_repo']} tests, "
                f"{stats['reduction_pct']}% reduction):"
            )
            print()
            print(commands['run_all'])
            print()
            print(
                f"Run HIGH PRIORITY only "
                f"(score >= 60, {stats['high_priority']} tests):"
            )
            print()
            print(commands['run_high'])
            print()
            print(
                f"Run FAST subset "
                f"(unit + score >= 60, {stats['fast_subset']} tests):"
            )
            print()
            print(commands['run_fast'])
            print()
        except Exception as e:
            print_item("Pytest command generation skipped", str(e))
    
    # Display unused tests if connection available
    if conn:
        print_section("Tests NOT Affected (Unused):")
        unused_tests = find_unused_tests(conn, affected_test_ids)
        print_item(f"Total unused tests", len(unused_tests))
        print()
        
        if unused_tests:
            # Group by test type
            by_type = {}
            for test in unused_tests:
                test_type = test.get('test_type', 'unknown')
                if test_type not in by_type:
                    by_type[test_type] = []
                by_type[test_type].append(test)
            
            # Display by type
            for test_type, tests in sorted(by_type.items()):
                print_item(f"{test_type.capitalize()} tests (unused)", len(tests))
                for test in tests[:5]:  # Show first 5 of each type
                    test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
                    print_item(f"  {test['test_id']}", test_name)
                if len(tests) > 5:
                    print_item(f"  ... and {len(tests) - 5} more {test_type} tests", "")
                print()
            
            # Overall summary
            print_section("Unused Tests Summary:")
            all_tests_count = len(get_all_tests_from_database(conn))
            print_item("Total tests in repository", all_tests_count)
            print_item("Affected tests", len(affected_test_ids))
            print_item("Unused tests", len(unused_tests))
            if all_tests_count > 0:
                reduction_pct = round((len(unused_tests) / all_tests_count) * 100, 1)
                print_item("Test reduction", f"{len(unused_tests)} tests ({reduction_pct}%) can be skipped")
            print()


def save_results_to_file(results: Dict, conn=None, diff_file_path: str = None, output_dir: Path = None) -> Path:
    """
    Save complete test selection results to a file.
    
    Args:
        results: Dictionary from find_affected_tests
        conn: Optional database connection to include unused tests
        diff_file_path: Path to the diff file (for naming output file)
        output_dir: Directory to save output file (default: git_diff_processor/outputs)
    
    Returns:
        Path to the saved output file
    """
    from datetime import datetime
    
    # Determine output directory
    if output_dir is None:
        output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if diff_file_path:
        diff_name = Path(diff_file_path).stem
        output_filename = f"test_selection_{diff_name}_{timestamp}.txt"
    else:
        output_filename = f"test_selection_{timestamp}.txt"
    
    output_path = output_dir / output_filename
    
    # Build output content
    lines = []
    lines.append("=" * 80)
    lines.append("TEST SELECTION RESULTS")
    lines.append("=" * 80)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if diff_file_path:
        lines.append(f"Diff File: {diff_file_path}")
    lines.append("")
    
    if results['total_tests'] == 0:
        lines.append("No tests found!")
        lines.append("")
        lines.append("Possible reasons:")
        lines.append("  - Changed files are not referenced by any tests")
        lines.append("  - Changed files are test files themselves")
        lines.append("  - Production class names don't match database")
        
        if conn:
            lines.append("")
            lines.append("-" * 80)
            lines.append("ALL TESTS (NOT AFFECTED)")
            lines.append("-" * 80)
            unused_tests = find_unused_tests(conn, set())
            lines.append(f"Total tests in repository: {len(unused_tests)}")
            if unused_tests:
                lines.append("")
                for test in unused_tests:
                    test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
                    test_type = test.get('test_type') or 'unknown'
                    lines.append(f"  {test['test_id']}: {test_name} ({test_type})")
    else:
        # Tests already sorted by score from find_affected_tests()
        affected_test_ids = set()
        for test in results['tests']:
            affected_test_ids.add(test['test_id'])

        scores = [t.get('confidence_score', 0) for t in results['tests']]

        lines.append(f"Found {results['total_tests']} affected test(s)")
        lines.append("")
        lines.append("-" * 80)
        lines.append(f"RANKED TEST LIST (sorted by confidence score 0-100)")
        lines.append("-" * 80)
        lines.append("")

        for test in results['tests']:
            test_id   = test['test_id']
            score     = test.get('confidence_score', 0)
            test_name = (
                f"{test['class_name']}.{test['method_name']}"
                if test.get('class_name')
                else test.get('method_name', '')
            )
            test_type = test.get('test_type') or 'unknown'
            test_file = test.get('test_file_path', 'unknown')
            matches   = results['match_details'].get(test_id, [])

            lines.append(f"  [{score:3d}] {test_id}: {test_name} ({test_type})")
            lines.append(f"         File: {test_file}")

            for m in matches:
                mtype    = m.get('type', '')
                ref_type = m.get('reference_type', '')

                if mtype == 'function_level':
                    func  = f"{m.get('module', '')}.{m.get('function', '')}"
                    src   = m.get('source', '')
                    label = '(via patch)' if src == 'patch_ref' else '(via call)'
                    lines.append(f"         Matched function: {func} {label}")
                elif mtype == 'exact':
                    label = '(via patch/Mock)' if ref_type == 'string_ref' else '(via import)'
                    lines.append(f"         Matched class: {m.get('class', '')} {label}")
                elif mtype == 'direct_file':
                    lines.append(
                        f"         Matched via: {m.get('match_strategy', 'direct_file')}")
                elif mtype == 'integration':
                    lines.append(f"         Integration test for: {m.get('module', '')}")
                elif mtype == 'module':
                    lines.append(f"         Module pattern: {m.get('pattern', '')}")
                elif mtype == 'semantic':
                    sim_pct = int(m.get('similarity', 0) * 100)
                    lines.append(f"         Semantic similarity: {sim_pct}%")

            lines.append("")
        
        lines.append("-" * 80)
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total tests to run: {results['total_tests']}")
        if scores:
            lines.append(f"Highest score: {max(scores)}")
            lines.append(f"Lowest score:  {min(scores)}")
            lines.append(
                f"Score 85-100:  {sum(1 for s in scores if s >= 85)}")
            lines.append(
                f"Score 60-84:   {sum(1 for s in scores if 60 <= s < 85)}")
            lines.append(
                f"Score 35-59:   {sum(1 for s in scores if 35 <= s < 60)}")
            lines.append(
                f"Score  0-34:   {sum(1 for s in scores if s < 35)}")
        lines.append("")
        
        # Pytest commands section
        if conn:
            try:
                total_in_repo = get_total_test_count(conn)
                commands      = generate_pytest_commands(results['tests'], total_in_repo)
                stats         = commands['stats']

                lines.append("")
                lines.append("=" * 70)
                lines.append("PYTEST COMMANDS")
                lines.append("=" * 70)
                lines.append("")
                lines.append(
                    f"Run ALL selected ({stats['selected']} of "
                    f"{stats['total_in_repo']} tests, "
                    f"{stats['reduction_pct']}% reduction):"
                )
                lines.append("")
                lines.append(commands['run_all'])
                lines.append("")
                lines.append(
                    f"Run HIGH PRIORITY only "
                    f"(score >= 60, {stats['high_priority']} tests):"
                )
                lines.append("")
                lines.append(commands['run_high'])
                lines.append("")
                lines.append(
                    f"Run FAST subset "
                    f"(unit + score >= 60, {stats['fast_subset']} tests):"
                )
                lines.append("")
                lines.append(commands['run_fast'])
                lines.append("")
            except Exception as e:
                lines.append(f"# Pytest command generation skipped: {e}")
                lines.append("")
        
        # Write unused tests (ALL of them)
        if conn:
            lines.append("-" * 80)
            lines.append("TESTS NOT AFFECTED (UNUSED)")
            lines.append("-" * 80)
            unused_tests = find_unused_tests(conn, affected_test_ids)
            lines.append(f"Total unused tests: {len(unused_tests)}")
            lines.append("")
            
            if unused_tests:
                # Group by test type
                by_type = {}
                for test in unused_tests:
                    test_type = test.get('test_type', 'unknown')
                    if test_type not in by_type:
                        by_type[test_type] = []
                    by_type[test_type].append(test)
                
                # Write by type (ALL tests, not just first 5)
                for test_type, tests in sorted(by_type.items()):
                    lines.append(f"{test_type.capitalize()} tests (unused): {len(tests)}")
                    for test in tests:
                        test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
                        test_file = test.get('test_file_path', 'unknown')
                        lines.append(f"  {test['test_id']}: {test_name}")
                        lines.append(f"    File: {test_file}")
                    lines.append("")
                
                # Overall summary
                lines.append("-" * 80)
                lines.append("UNUSED TESTS SUMMARY")
                lines.append("-" * 80)
                all_tests_count = len(get_all_tests_from_database(conn))
                lines.append(f"Total tests in repository: {all_tests_count}")
                lines.append(f"Affected tests: {len(affected_test_ids)}")
                lines.append(f"Unused tests: {len(unused_tests)}")
                if all_tests_count > 0:
                    reduction_pct = round((len(unused_tests) / all_tests_count) * 100, 1)
                    lines.append(f"Test reduction: {len(unused_tests)} tests ({reduction_pct}%) can be skipped")
                lines.append("")
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return output_path


def main():
    """Main function to process git diff and find affected tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Git Diff to Test Selection')
    parser.add_argument('diff_file', nargs='?', help='Path to git diff file')
    parser.add_argument('--reindex', action='store_true', 
                       help='Re-index test repository before selection')
    parser.add_argument('--verify', action='store_true',
                       help='Verify indexing completeness')
    parser.add_argument('--diagnose', action='store_true',
                       help='Run diagnostics')
    parser.add_argument('--test-repo', default=None,
                       help='Path to test repository (default: test_repository)')
    parser.add_argument('--deduplicate', action='store_true',
                       help='Find and remove duplicate test entries')
    parser.add_argument('--remove-duplicates', action='store_true',
                       help='Actually remove duplicates (use with --deduplicate)')
    
    args = parser.parse_args()
    
    # Import indexing utilities
    sys.path.insert(0, str(Path(__file__).parent))
    from utils.indexing_utils import verify_indexing_completeness, reindex_missing_files, diagnose_integration_tests
    from utils.deduplicate_tests import find_duplicate_tests, remove_duplicate_tests
    
    # Determine test repo path
    if args.test_repo:
        test_repo_path = args.test_repo
    else:
        test_repo_path = str(Path(__file__).parent.parent / "test_repository")
    
    # Handle verify, reindex, diagnose options
    if args.verify:
        print_header("Verifying Indexing Completeness")
        print()
        with get_connection() as conn:
            verification = verify_indexing_completeness(test_repo_path, conn)
            print_section("Indexing Verification Results:")
            print_item("Files on disk", verification['total_on_disk'])
            print_item("Files indexed", verification['total_indexed'])
            print_item("Coverage", f"{verification['coverage_percent']:.1f}%")
            
            if verification.get('missing_files'):
                print()
                print_section("Missing Files:")
                for missing in verification['missing_files'][:20]:  # Show first 20
                    print_item(f"  - {Path(missing).name}", str(missing))
                if len(verification['missing_files']) > 20:
                    print_item(f"  ... and {len(verification['missing_files']) - 20} more", "")
        return
    
    if args.reindex:
        print_header("Re-indexing Test Repository")
        print()
        with get_connection() as conn:
            result = reindex_missing_files(test_repo_path, conn)
            print_section("Re-indexing Results:")
            print_item("Files indexed", str(result.get('indexed', 0)))
            print_item("Tests added", str(result.get('tests_added', 0)))
            print_item("Duplicates avoided", str(result.get('duplicates_avoided', 0)))
            print_item("Errors", str(len(result.get('errors', []))))
            
            if result.get('errors'):
                print()
                print_section("Errors:")
                for error in result['errors'][:10]:
                    print_item(f"  - {Path(error['file']).name}", error['error'])
        return
    
    if args.diagnose:
        print_header("Diagnostics: Integration Tests")
        print()
        with get_connection() as conn:
            diag = diagnose_integration_tests(conn)
            print_section("Integration Test Diagnostics:")
            print_item("Total integration/e2e tests", diag['total_integration_tests'])
            
            if diag['agent_flow_tests']:
                print_item("test_agent_flow.py found", f"{len(diag['agent_flow_tests'])} test(s)")
            else:
                print_item("test_agent_flow.py", "NOT FOUND in database")
            
            if diag.get('suggestions'):
                print()
                print_section("Suggestions:")
                for suggestion in diag['suggestions']:
                    print_item(f"  - {suggestion}", "")
        return
    
    if args.deduplicate:
        print_header("Finding Duplicate Tests")
        print()
        with get_connection() as conn:
            duplicates_info = find_duplicate_tests(conn)
            print_section("Duplicate Analysis:")
            print_item("Total tests in database", str(duplicates_info['total_tests']))
            print_item("Unique tests", str(duplicates_info['unique_tests']))
            print_item("Duplicate groups", str(duplicates_info['duplicate_groups']))
            print_item("Duplicate tests to remove", str(duplicates_info['duplicate_tests']))
            
            if duplicates_info['duplicate_groups'] > 0:
                print()
                print_section("Sample Duplicates (first 5 groups):")
                for i, (key, tests) in enumerate(list(duplicates_info['duplicates'].items())[:5]):
                    normalized_path, class_name, method_name = key
                    print_item(f"  Group {i+1}: {Path(normalized_path).name}", f"{len(tests)} duplicates")
                    for test in tests[:3]:
                        print_item(f"    - {test['test_id']}", f"path: {test['file_path'][:60]}...")
                    if len(tests) > 3:
                        print_item(f"    ... and {len(tests) - 3} more", "")
                
                if args.remove_duplicates:
                    print()
                    print_section("Removing Duplicates...")
                    result = remove_duplicate_tests(conn, dry_run=False)
                    print_item("Tests removed", result['removed'])
                    print_item("Tests kept", result['kept'])
                    print()
                    print_item("Duplicates removed successfully!", "")
                else:
                    print()
                    print_item("To remove duplicates, run with --remove-duplicates flag", "")
        return
    
    # Normal processing
    print_header("Git Diff to Test Selection")
    print()
    
    # Step 1: Get diff file path
    if args.diff_file:
        user_path = Path(args.diff_file)
    elif len(sys.argv) > 1:
        user_path = Path(sys.argv[1])
    else:
        user_path = None
    
    if user_path:
        # If absolute path, use it directly
        if user_path.is_absolute():
            diff_file_path = user_path
        else:
            # Try multiple locations in order:
            # 1. Relative to script directory (git_diff_processor/)
            script_dir_path = Path(__file__).parent / user_path
            # 2. Relative to current working directory
            cwd_path = Path.cwd() / user_path
            
            # Check in order of preference
            if script_dir_path.exists():
                diff_file_path = script_dir_path
            elif cwd_path.exists():
                diff_file_path = cwd_path
            else:
                # Use the path as-is (will show error if not found)
                diff_file_path = user_path
    else:
        # Default to sample_diffs folder
        default_path = Path(__file__).parent / "sample_diffs" / "diff_commit1.txt"
        if default_path.exists():
            diff_file_path = default_path
            print_section(f"Using default diff file: {diff_file_path}")
        else:
            print_section("No diff file specified!")
            print_item("Usage", "python git_diff_processor.py <path_to_diff_file>")
            print()
            print_item("Options", "--verify, --reindex, --diagnose")
            print()
            print_item("Or save your git diff to", str(default_path))
            return
    
    # Step 2: Test database connection
    print_section("Testing database connection...")
    if not test_connection():
        print()
        print("ERROR: Cannot connect to database!")
        print("Please ensure the deterministic database is set up and .env is configured.")
        return
    print()
    
    # Step 3: Read git diff file
    print_section("Step 1: Reading git diff file...")
    try:
        # Show resolved path (absolute for clarity)
        resolved_path = diff_file_path.resolve()
        diff_content = read_diff_file(diff_file_path)
        print_item("File", str(resolved_path))
        print_item("File size", f"{len(diff_content)} characters")
        print_item("Status", "[OK] File read successfully")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    except Exception as e:
        print(f"ERROR: Could not read file: {e}")
        return
    print()
    
    # Step 4: Parse git diff
    print_section("Step 2: Parsing git diff...")
    parsed_diff = parse_git_diff(diff_content)
    
    # Filter and show production Python files
    from utils.diff_parser import is_production_python_file
    production_files = [f for f in parsed_diff['file_changes'] 
                       if is_production_python_file(f['file'])]
    non_production_files = [f for f in parsed_diff['file_changes'] 
                            if not is_production_python_file(f['file'])]
    
    print_item("Total changed files", len(parsed_diff['file_changes']))
    print_item("Production Python files", len(production_files))
    print_item("Non-production files (filtered)", len(non_production_files))
    if non_production_files:
        print_item("  (Skipping: artifacts, data files, frontend, config, etc.)", "")
    print()
    
    display_parsed_changes(parsed_diff)
    
    # Step 5: Build search queries
    print_section("Step 3: Building search strategy...")
    search_queries = build_search_queries(parsed_diff['file_changes'])
    display_search_strategy(search_queries)
    
    # Step 6: Query database
    print_section("Step 4: Querying database for affected tests...")
    
    # Diagnostic: Check database contents
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.reverse_index")
                reverse_index_count = cursor.fetchone()[0]
                cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.test_registry")
                test_registry_count = cursor.fetchone()[0]
                
                if reverse_index_count == 0:
                    print_item("WARNING: reverse_index table is empty!", "")
                    print_item("  Please run test analysis and load data", "")
                    print_item("    1. python test_analysis/04_extract_static_dependencies.py", "")
                    print_item("    2. python test_analysis/06_build_reverse_index.py", "")
                    print_item("    3. python deterministic/04_load_reverse_index.py", "")
                    print()
                elif test_registry_count == 0:
                    print_item("WARNING: test_registry table is empty!", "")
                    print_item("  Please load test registry data", "")
                    print_item("    python deterministic/02_load_test_registry.py", "")
                    print()
                else:
                    print_item(f"Database status", f"{reverse_index_count} reverse_index entries, {test_registry_count} tests")
                    print()
            
            # Step 4a: Run AST-based matching separately
            print_section("Step 4a: AST-Based Matching (Strategies 0-3)...")
            ast_results = find_tests_ast_only(conn, search_queries, parsed_diff.get('file_changes', []))
            print_item(f"AST-based matching found", f"{ast_results['total_tests']} tests")
            print()
            
            # Step 4b: Run Semantic search separately
            print_section("Step 4b: Semantic Search (Vector Embeddings)...")
            semantic_results = find_tests_semantic_only(conn, search_queries)
            if semantic_results.get('error'):
                print_item("Semantic search failed", semantic_results['error'])
            else:
                print_item(f"Semantic search found", f"{semantic_results['total_tests']} tests")
            print()
            
            # Step 4c: Compare results
            print_section("Step 4c: Comparing AST vs Semantic Results...")
            comparison = compare_ast_vs_semantic(ast_results, semantic_results)
            print_item("AST-based matching found", f"{comparison['ast_count']} tests")
            print_item("Semantic search found", f"{comparison['semantic_count']} tests")
            print_item("Found by both methods", f"{comparison['overlap_count']} tests")
            print_item("Found only by AST", f"{comparison['ast_only_count']} tests")
            print_item("Found only by Semantic", f"{comparison['semantic_only_count']} tests")
            if comparison['ast_count'] > 0:
                print_item("Overlap percentage", f"{comparison['overlap_percentage']}%")
            print()
            
            # Step 4d: Save separate output files
            print_section("Step 4d: Saving Separate Results...")
            
            # Save AST results
            ast_output = save_results_to_file(
                ast_results, 
                conn, 
                diff_file_path,
                output_dir=Path(__file__).parent / "outputs"
            )
            # Rename to include method
            ast_final = ast_output.parent / f"ast_only_{ast_output.name}"
            ast_output.rename(ast_final)
            print_item("AST results saved to", str(ast_final))
            
            # Save Semantic results
            if semantic_results['total_tests'] > 0:
                semantic_output = save_results_to_file(
                    semantic_results,
                    conn,
                    diff_file_path,
                    output_dir=Path(__file__).parent / "outputs"
                )
                semantic_final = semantic_output.parent / f"semantic_only_{semantic_output.name}"
                semantic_output.rename(semantic_final)
                print_item("Semantic results saved to", str(semantic_final))
            else:
                print_item("Semantic results", "No tests found, skipping file save")
            
            # Save comparison report
            comparison_output = save_comparison_report(
                ast_results,
                semantic_results,
                comparison,
                diff_file_path,
                output_dir=Path(__file__).parent / "outputs"
            )
            print_item("Comparison report saved to", str(comparison_output))
            print()
            
            # Step 4e: Run combined results (original behavior)
            results = find_affected_tests(conn, search_queries, parsed_diff.get('file_changes', []))
            
            # Step 6.5: Run diagnostics if tests seem missing
            expected_candidates = len(search_queries.get('test_file_candidates', []))
            if results['total_tests'] == 0 or (expected_candidates > 0 and results['total_tests'] < expected_candidates * 2):
                print_section("Diagnostics: Checking for missing tests...")
                diagnostics = diagnose_missing_tests(
                    conn, 
                    parsed_diff.get('file_changes', []),
                    search_queries
                )
                
                if diagnostics:
                    print_item("Diagnostic summary", "")
                    for file_path, diag in list(diagnostics.items())[:5]:
                        # Path is already imported at top of file
                        print_item(f"  {Path(file_path).name}", "")
                        if diag.get('suggestions'):
                            for suggestion in diag['suggestions'][:2]:
                                print_item(f"    - {suggestion}", "")
                    if len(diagnostics) > 5:
                        print_item(f"    ... and {len(diagnostics) - 5} more files", "")
                print()
            
            # Step 7: Display results (pass connection to show unused tests)
            print_section("Step 5: Results")
            print()
            display_results(results, conn)
            
            # Step 8: Save complete results to file
            print_section("Saving results to file...")
            output_file = save_results_to_file(results, conn, diff_file_path)
            print_item("Results saved to", str(output_file))
            print()
            
            print_header("Processing Complete!")
            print(f"Selected {results['total_tests']} test(s) to run based on code changes")
            
    except Exception as e:
        print(f"ERROR: Database query failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
