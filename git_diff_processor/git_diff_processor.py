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
    print_item("  - reverse_index", "(primary - fast lookup)")
    print_item("  - test_registry", "(for direct test file matching)")
    print()


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
    1. Direct test files (highest confidence)
    2. Exact class/module matches (high confidence)
    3. Module patterns with direct references (medium confidence)
    
    Args:
        conn: Database connection
        search_queries: Dictionary with search strategies
        file_changes: List of file change dictionaries (for filtering import-only changes)
    
    Returns:
        Dictionary with test results and metadata
    """
    all_tests = {}  # test_id -> test info with match details
    match_details = {}  # test_id -> list of match reasons
    
    # Strategy 1: Direct test files (highest confidence) - Enhanced
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
    
    return {
        'tests': list(all_tests.values()),
        'match_details': match_details,
        'total_tests': len(all_tests)
    }


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
    
    print_item(f"Found {results['total_tests']} affected test(s)", "")
    print()
    
    # Group by confidence
    high_confidence = []
    medium_confidence = []
    affected_test_ids = set()
    
    for test in results['tests']:
        test_id = test['test_id']
        affected_test_ids.add(test_id)
        matches = results['match_details'].get(test_id, [])
        
        # Determine overall confidence
        has_exact = any(m['type'] == 'exact' for m in matches)
        confidence = 'high' if has_exact else 'medium'
        
        test_info = {
            'test': test,
            'matches': matches,
            'confidence': confidence
        }
        
        if confidence == 'high':
            high_confidence.append(test_info)
        else:
            medium_confidence.append(test_info)
    
    # Display high confidence first
    if high_confidence:
        print_item("High Confidence Matches (Exact class matches)", len(high_confidence))
        for test_info in high_confidence[:10]:
            test = test_info['test']
            test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
            print_item(f"  {test['test_id']}:", test_name)
            
            # Show match reasons with reference types
            exact_matches = [m for m in test_info['matches'] if m['type'] == 'exact']
            if exact_matches:
                matched_classes = []
                for m in exact_matches[:3]:
                    class_name = m['class']
                    ref_type = m.get('reference_type', 'direct_import')
                    if ref_type == 'string_ref':
                        matched_classes.append(f"{class_name} (via patch/Mock)")
                    else:
                        matched_classes.append(class_name)
                if len(exact_matches) > 3:
                    matched_classes.append(f"... (+{len(exact_matches) - 3} more)")
                print_item(f"    Matched classes", ", ".join(matched_classes))
        print()
    
    # Display medium confidence
    if medium_confidence:
        print_item("Medium Confidence Matches (Module patterns)", len(medium_confidence))
        for test_info in medium_confidence[:10]:
            test = test_info['test']
            test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
            print_item(f"  {test['test_id']}:", test_name)
        print()
    
    # Summary
    print_section("Summary:")
    print_item("Total tests to run", results['total_tests'])
    print_item("High confidence", len(high_confidence))
    print_item("Medium confidence", len(medium_confidence))
    print()
    
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
        lines.append(f"Found {results['total_tests']} affected test(s)")
        lines.append("")
        
        # Group by confidence
        high_confidence = []
        medium_confidence = []
        affected_test_ids = set()
        
        for test in results['tests']:
            test_id = test['test_id']
            affected_test_ids.add(test_id)
            matches = results['match_details'].get(test_id, [])
            
            # Determine overall confidence
            has_exact = any(m['type'] == 'exact' for m in matches)
            confidence = 'high' if has_exact else 'medium'
            
            test_info = {
                'test': test,
                'matches': matches,
                'confidence': confidence
            }
            
            if confidence == 'high':
                high_confidence.append(test_info)
            else:
                medium_confidence.append(test_info)
        
        # Write high confidence tests (ALL of them, not just first 10)
        if high_confidence:
            lines.append("-" * 80)
            lines.append(f"HIGH CONFIDENCE MATCHES (Exact class matches): {len(high_confidence)}")
            lines.append("-" * 80)
            lines.append("")
            
            for test_info in high_confidence:
                test = test_info['test']
                test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
                test_type = test.get('test_type') or 'unknown'
                test_file = test.get('test_file_path', 'unknown')
                
                lines.append(f"  {test['test_id']}: {test_name}")
                lines.append(f"    Test Type: {test_type}")
                lines.append(f"    File: {test_file}")
                
                # Show all match reasons
                exact_matches = [m for m in test_info['matches'] if m['type'] == 'exact']
                if exact_matches:
                    matched_classes = []
                    for m in exact_matches:
                        class_name = m['class']
                        ref_type = m.get('reference_type', 'direct_import')
                        if ref_type == 'string_ref':
                            matched_classes.append(f"{class_name} (via patch/Mock)")
                        else:
                            matched_classes.append(f"{class_name} (via import)")
                    lines.append(f"    Matched classes: {', '.join(matched_classes)}")
                
                # Show other match types
                other_matches = [m for m in test_info['matches'] if m['type'] != 'exact']
                if other_matches:
                    match_types = {}
                    for m in other_matches:
                        match_type = m.get('type', 'unknown')
                        if match_type not in match_types:
                            match_types[match_type] = []
                        if match_type == 'direct_file':
                            match_types[match_type].append(m.get('test_file', ''))
                        elif match_type == 'integration':
                            match_types[match_type].append(m.get('module', ''))
                    for match_type, values in match_types.items():
                        lines.append(f"    Also matched via: {match_type} ({', '.join(set(values))})")
                
                lines.append("")
        
        # Write medium confidence tests (ALL of them)
        if medium_confidence:
            lines.append("-" * 80)
            lines.append(f"MEDIUM CONFIDENCE MATCHES (Module patterns): {len(medium_confidence)}")
            lines.append("-" * 80)
            lines.append("")
            
            for test_info in medium_confidence:
                test = test_info['test']
                test_name = f"{test['class_name']}.{test['method_name']}" if test['class_name'] else test['method_name']
                test_type = test.get('test_type') or 'unknown'
                test_file = test.get('test_file_path', 'unknown')
                
                lines.append(f"  {test['test_id']}: {test_name}")
                lines.append(f"    Test Type: {test_type}")
                lines.append(f"    File: {test_file}")
                
                # Show match reasons
                for m in test_info['matches']:
                    match_type = m.get('type', 'unknown')
                    if match_type == 'module_pattern':
                        lines.append(f"    Matched via module pattern: {m.get('pattern', 'unknown')}")
                    elif match_type == 'direct_file':
                        lines.append(f"    Matched via direct file: {m.get('test_file', 'unknown')}")
                
                lines.append("")
        
        # Summary
        lines.append("-" * 80)
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total tests to run: {results['total_tests']}")
        lines.append(f"High confidence: {len(high_confidence)}")
        lines.append(f"Medium confidence: {len(medium_confidence)}")
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
