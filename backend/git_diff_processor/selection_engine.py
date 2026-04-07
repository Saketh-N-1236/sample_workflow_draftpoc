"""Core DB + semantic selection logic (shared by CLI and API)."""
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from deterministic.db_connection import DB_SCHEMA
from deterministic.utils.db_helpers import get_tests_for_production_class
from deterministic.parsing.diff_parser import (
    analyze_file_change_type,
    extract_production_classes_from_file,
)
from semantic.retrieval.semantic_search import find_tests_semantic

from git_diff_processor.cli_output import print_section, print_item

def query_tests_for_functions(conn, changed_functions: List[Dict[str, str]], schema: str = None) -> List[Dict]:
    """
    Query database for tests that call/patch specific functions.
    
    This is the most precise matching strategy - only selects tests that
    actually call or patch the changed functions.
    
    Args:
        conn: Database connection
        changed_functions: List of {'module': 'agent.langgraph_agent', 'function': 'initialize'}
        schema: Database schema name (defaults to DB_SCHEMA if not provided)
    
    Returns:
        List of test dictionaries with match details
    """
    if not changed_functions:
        return []
    
    target_schema = schema or DB_SCHEMA
    all_tests = []
    seen_test_ids = set()
    
    import logging
    logger = logging.getLogger(__name__)
    
    with conn.cursor() as cursor:
        for func_change in changed_functions:
            module_name = func_change['module']
            function_name = func_change['function']
            
            # Debug: Log what we're searching for
            logger.debug(f"[{target_schema}] Searching for function: {module_name}.{function_name}")
            
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
                FROM {target_schema}.test_function_mapping tfm
                JOIN {target_schema}.test_registry tr ON tfm.test_id = tr.test_id
                WHERE tfm.module_name = %s
                AND tfm.function_name = %s
                ORDER BY 
                    source_priority,
                    tr.test_id
            """, (module_name, function_name))
            
            rows = cursor.fetchall()
            if not rows:
                # Debug: Check if table exists and has data
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {target_schema}.test_function_mapping
                """)
                total_mappings = cursor.fetchone()[0]
                cursor.execute(f"""
                    SELECT DISTINCT module_name, function_name 
                    FROM {target_schema}.test_function_mapping 
                    LIMIT 5
                """)
                sample_mappings = cursor.fetchall()
                logger.debug(f"[{target_schema}] No matches found. Total mappings in DB: {total_mappings}")
                if sample_mappings:
                    logger.debug(f"[{target_schema}] Sample mappings: {sample_mappings[:3]}")
            
            for row in rows:
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


def query_tests_for_classes(conn, production_classes: List[str], schema: str = None) -> Dict[str, List[Dict]]:
    """
    Query database to find tests for given production classes.
    
    Args:
        conn: Database connection
        production_classes: List of production class/module names
        schema: Database schema name (defaults to DB_SCHEMA if not provided)
    
    Returns:
        Dictionary mapping production_class -> list of test dictionaries
    """
    target_schema = schema or DB_SCHEMA
    results = {}
    
    import logging
    logger = logging.getLogger(__name__)
    
    for prod_class in production_classes:
        logger.debug(f"[{target_schema}] Searching for class: {prod_class}")
        tests = get_tests_for_production_class(conn, prod_class, schema=target_schema)
        if tests:
            results[prod_class] = tests
            logger.debug(f"[{target_schema}] Found {len(tests)} tests for {prod_class}")
        else:
            # Debug: Check what's in reverse_index
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {target_schema}.reverse_index 
                    WHERE production_class = %s
                """, (prod_class,))
                count = cursor.fetchone()[0]
                if count == 0:
                    # Check for similar entries
                    cursor.execute(f"""
                        SELECT DISTINCT production_class 
                        FROM {target_schema}.reverse_index 
                        WHERE production_class LIKE %s
                        LIMIT 5
                    """, (f"%{prod_class.split('.')[-1]}%",))
                    similar = cursor.fetchall()
                    logger.debug(f"[{target_schema}] No matches for {prod_class}. Similar entries: {[s[0] for s in similar]}")
    
    return results


def compute_diff_impact(
    conn,
    schema: str,
    search_queries: Dict,
    tests: List[Dict],
    match_details: Dict[str, List[Dict]],
) -> tuple:
    """
    Compute coverage gaps and breakage warnings from diff symbols and selected tests.
    Annotates tests that reference deleted/renamed symbols with will_fail_reason.

    Args:
        conn: Database connection
        schema: Target schema (e.g. test_repo_261b672a)
        search_queries: From build_search_queries (deleted_symbols, added_symbols, renamed_symbols)
        tests: List of selected test dicts (with test_id)
        match_details: test_id -> list of match dicts (type, class, etc.)

    Returns:
        (coverage_gaps, breakage_warnings, test_breakage_map)
        - coverage_gaps: list of { type, symbol?, message?, test_id? }
        - breakage_warnings: list of strings
        - test_breakage_map: test_id -> will_fail_reason string
    """
    target_schema = schema or DB_SCHEMA
    coverage_gaps = []
    breakage_warnings = []
    test_breakage_map = {}

    deleted = list(search_queries.get('deleted_symbols') or [])
    added = list(search_queries.get('added_symbols') or [])
    renamed = list(search_queries.get('renamed_symbols') or [])
    deleted_or_renamed_old = set(deleted) | {r.get('old') for r in renamed if r.get('old')}

    # Breakage: renamed symbols
    for r in renamed:
        old_sym = r.get('old') or ''
        new_sym = r.get('new') or ''
        if old_sym and new_sym:
            coverage_gaps.append({
                'type': 'RENAME',
                'symbol': old_sym,
                'new_symbol': new_sym,
                'message': f"Symbol '{old_sym}' was renamed to '{new_sym}'. Tests referencing '{old_sym}' may fail.",
            })
            breakage_warnings.append(
                f"Symbol '{old_sym}' was renamed to '{new_sym}'. Tests referencing '{old_sym}' may fail."
            )

    # Breakage: deleted symbols
    for sym in deleted:
        breakage_warnings.append(
            f"Symbol '{sym}' was removed. Tests referencing '{sym}' may fail."
        )

    # Coverage gap: new symbols with zero test coverage
    for sym in added:
        if not sym:
            continue
        class_results = query_tests_for_classes(conn, [sym], schema=target_schema)
        if not class_results.get(sym):
            coverage_gaps.append({
                'type': 'NEW_SYMBOL_ZERO_COVERAGE',
                'symbol': sym,
                'message': f"New symbol '{sym}' has no tests in the registry.",
            })

    # Per-test: annotate tests that reference deleted or old-renamed symbols
    for test in tests:
        test_id = test.get('test_id')
        if not test_id:
            continue
        matches = match_details.get(test_id, [])
        for m in matches:
            if m.get('type') != 'exact':
                continue
            cls = m.get('class') or ''
            if cls in deleted_or_renamed_old:
                if cls in deleted:
                    test_breakage_map[test_id] = f"References deleted symbol '{cls}'."
                else:
                    pair = next((r for r in renamed if r.get('old') == cls), None)
                    new_sym = pair.get('new', '') if pair else ''
                    test_breakage_map[test_id] = f"References renamed symbol '{cls}' (now '{new_sym}')."
                break

    return coverage_gaps, breakage_warnings, test_breakage_map


def query_tests_module_pattern(conn, module_pattern: str, prefer_direct: bool = True, 
                                specific_classes: List[str] = None, require_direct: bool = False, schema: str = None) -> List[Dict]:
    """
    Query database for tests matching a module pattern (e.g., 'agent.*').
    
    Prefers direct references (direct_import, string_ref) over indirect ones.
    If specific_classes is provided, only matches tests referencing those specific classes.
    If require_direct is True, only returns tests with at least one direct reference.
    
    Args:
        conn: Database connection
        module_pattern: Pattern like 'agent.*'
        prefer_direct: If True, prefer direct references over indirect
        specific_classes: Optional list of specific class names to match (filters broad module matches)
        require_direct: If True, only return tests with direct references (filters false positives)
        schema: Database schema name (defaults to DB_SCHEMA if not provided)
    
    Returns:
        List of test dictionaries with reference_type
    """
    target_schema = schema or DB_SCHEMA
    module_prefix = module_pattern.replace('.*', '')
    
    with conn.cursor() as cursor:
        if prefer_direct or require_direct:
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
                    FROM {target_schema}.reverse_index ri
                    JOIN {target_schema}.test_registry tr ON ri.test_id = tr.test_id
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
                    FROM {target_schema}.reverse_index ri
                    JOIN {target_schema}.test_registry tr ON ri.test_id = tr.test_id
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
                FROM {target_schema}.reverse_index ri
                JOIN {target_schema}.test_registry tr ON ri.test_id = tr.test_id
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
                                     file_path: str = None, schema: str = None) -> List[Dict]:
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
        schema: Database schema name (defaults to DB_SCHEMA if not provided)
    
    Returns:
        List of test dictionaries with match details
    """
    target_schema = schema or DB_SCHEMA
    if not test_file_candidates:
        return []
    
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"[{target_schema}] Searching for test files: {test_file_candidates[:5]}")
    
    direct_tests = []
    seen_test_ids = set()  # Avoid duplicates
    
    with conn.cursor() as cursor:
        # Debug: Check total tests in registry
        cursor.execute(f"SELECT COUNT(*) FROM {target_schema}.test_registry")
        total_tests = cursor.fetchone()[0]
        logger.debug(f"[{target_schema}] Total tests in registry: {total_tests}")
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
                    FROM {target_schema}.test_registry
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
                        FROM {target_schema}.test_registry
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
                FROM {target_schema}.test_registry
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
                FROM {target_schema}.test_registry
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


def find_affected_tests(conn, search_queries: Dict, file_changes: List[Dict] = None, prefer_function_level: bool = True, schema: str = None, semantic_config: Dict = None, diff_content: str = None) -> Dict[str, Any]:
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
        prefer_function_level: If True, only use module patterns if no function matches found
        schema: Database schema name (defaults to DB_SCHEMA if not provided)
    
    Returns:
        Dictionary with test results and metadata
    """
    target_schema = schema or DB_SCHEMA
    all_tests = {}  # test_id -> test info with match details
    match_details = {}  # test_id -> list of match reasons
    has_function_matches = False
    
    # Strategy 0: Function-level matching (very high confidence) - NEW
    if search_queries.get('changed_functions'):
        print_section("Querying database (Function-level matching - highest precision)...")
        function_tests = query_tests_for_functions(conn, search_queries['changed_functions'], schema=target_schema)
        
        if function_tests:
            has_function_matches = True
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
                file_path=file_path,
                schema=target_schema
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
                    integration_tests = find_integration_tests_for_module(conn, module_name, schema=target_schema)
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
        exact_results = query_tests_for_classes(conn, search_queries['exact_matches'], schema=target_schema)
        
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
            # Debug: Show what we searched for and what's in the database
            if search_queries['exact_matches']:
                with conn.cursor() as cursor:
                    # Show what we searched for
                    print_item("  Searched for:", ", ".join(search_queries['exact_matches'][:5]))
                    
                    # Check for similar matches (case-insensitive, partial)
                    first_match = search_queries['exact_matches'][0]
                    # Extract component name (last part after dots)
                    component_name = first_match.split('.')[-1] if '.' in first_match else first_match
                    
                    cursor.execute(f"""
                        SELECT DISTINCT production_class, reference_type
                        FROM {target_schema}.reverse_index 
                        WHERE LOWER(production_class) LIKE LOWER(%s) 
                           OR LOWER(production_class) LIKE LOWER(%s)
                        LIMIT 10
                    """, (f"%{component_name}%", f"%{first_match}%"))
                    sample_classes = cursor.fetchall()
                    if sample_classes:
                        print_item("  Similar entries in database", 
                                  ", ".join([f"{row[0]}" for row in sample_classes[:5]]))
                    else:
                        # Show sample of what's actually in the database
                        cursor.execute(f"""
                            SELECT DISTINCT production_class 
                            FROM {target_schema}.reverse_index 
                            ORDER BY production_class 
                            LIMIT 10
                        """)
                        sample_all = cursor.fetchall()
                        if sample_all:
                            print_item("  Sample production classes in database", 
                                      ", ".join([f"{row[0]}" for row in sample_all[:5]]))
                        else:
                            # Check if database has any data
                            cursor.execute(f"SELECT COUNT(*) FROM {target_schema}.reverse_index")
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
            
            # Use prefer_direct=True, require_direct=True, and filter by specific changed classes
            module_tests = query_tests_module_pattern(
                conn, module_pattern, 
                prefer_direct=True,
                specific_classes=specific_classes if specific_classes else None,
                require_direct=True,  # Only return tests with direct references
                schema=target_schema
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
    
    # Strategy 4: Semantic search - combine with AST results
    changed_functions_for_semantic = search_queries.get('changed_functions', []) or []
    semantic_test_ids = set()
    semantic_added = 0
    semantic_merged = 0
    
    if changed_functions_for_semantic or file_changes or diff_content:
        print_section("Querying database (Semantic search - meaning-based)...")
        try:
            # Extract semantic config parameters if provided
            similarity_threshold = None
            max_results = 10000
            use_adaptive_thresholds = True
            top_k = None
            top_p = None
            
            if semantic_config:
                similarity_threshold = semantic_config.get('similarity_threshold')
                if semantic_config.get('max_results') is not None:
                    max_results = semantic_config.get('max_results')
                use_adaptive_thresholds = semantic_config.get('use_adaptive_thresholds', True)
                top_k = semantic_config.get('top_k')
                top_p = semantic_config.get('top_p')
            
            # Check if we're in an async context - if so, skip semantic search here
            # (it should be done separately in the async caller)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # In async context - semantic search should be done separately
                    print_item("  Semantic search skipped", "(handled separately in async context)")
                    semantic_matches = []
                else:
                    # Loop exists but not running - safe to use asyncio.run()
                    semantic_matches = asyncio.run(
                        find_tests_semantic(
                            conn,
                            changed_functions_for_semantic,
                            file_changes,
                            similarity_threshold=similarity_threshold,
                            max_results=max_results,
                            use_adaptive_thresholds=use_adaptive_thresholds,
                            top_k=top_k,
                            top_p=top_p,
                            diff_content=diff_content,
                            semantic_config=semantic_config,
                            deleted_symbols=search_queries.get("deleted_symbols"),
                            added_symbols=search_queries.get("added_symbols"),
                            renamed_symbols=search_queries.get("renamed_symbols"),
                        )
                    )
            except RuntimeError:
                # No event loop - safe to create one
                semantic_matches = asyncio.run(
                    find_tests_semantic(
                        conn,
                        changed_functions_for_semantic,
                        file_changes,
                        similarity_threshold=similarity_threshold,
                        max_results=max_results,
                        use_adaptive_thresholds=use_adaptive_thresholds,
                        top_k=top_k,
                        top_p=top_p,
                        diff_content=diff_content,
                        semantic_config=semantic_config,
                        deleted_symbols=search_queries.get("deleted_symbols"),
                        added_symbols=search_queries.get("added_symbols"),
                        renamed_symbols=search_queries.get("renamed_symbols"),
                    )
                )

            # Combine AST and semantic results (not just add missing)
            for test in semantic_matches:
                test_id = test['test_id']
                similarity = test.get('similarity', 0)
                semantic_test_ids.add(test_id)
                
                if test_id not in all_tests:
                    # New test from semantic - add it with full test data
                    all_tests[test_id] = test
                    match_details[test_id] = [{
                        'type': 'semantic',
                        'similarity': similarity,
                        'confidence': 'medium'
                    }]
                    semantic_added += 1
                else:
                    # Test already found by AST - merge semantic match details AND update test object
                    existing_test = all_tests[test_id]
                    
                    # Update similarity on test object if not already set or if semantic has higher similarity
                    if similarity > 0:
                        existing_similarity = existing_test.get('similarity', 0)
                        if similarity > existing_similarity:
                            existing_test['similarity'] = similarity
                    
                    # Add semantic match to match_details
                    if test_id not in match_details:
                        match_details[test_id] = []
                    
                    # Check if semantic match already exists in match_details
                    has_semantic = any(m.get('type') == 'semantic' for m in match_details[test_id])
                    if not has_semantic:
                        # Add semantic match to existing match_details
                        match_details[test_id].append({
                            'type': 'semantic',
                            'similarity': similarity,
                            'confidence': 'medium'
                        })
                        semantic_merged += 1
                    else:
                        # Update similarity if higher
                        for m in match_details[test_id]:
                            if m.get('type') == 'semantic':
                                old_sim = m.get('similarity', 0)
                                new_sim = max(old_sim, similarity)
                                m['similarity'] = new_sim
                                # Also update test object similarity
                                if new_sim > existing_test.get('similarity', 0):
                                    existing_test['similarity'] = new_sim
                                break

            if semantic_added > 0:
                print_item(
                    f"  Found {semantic_added} additional test(s) via semantic search",
                    "(not found by AST matching)"
                )
            if semantic_merged > 0:
                print_item(
                    f"  Enhanced {semantic_merged} test(s) with semantic match details",
                    "(found by both AST and semantic)"
                )
            if semantic_added == 0 and semantic_merged == 0:
                print_item("  Semantic search: no new or enhanced tests", "")

        except Exception as e:
            # Semantic is optional — don't fail if Ollama is not running
            print_item("  Semantic search skipped", f"(Ollama unavailable: {e})")
        print()
    
    # Attach confidence score to every matched test
    # Use both AST and semantic match details for scoring
    # Note: LLM scores will be added later in process_diff_and_select_tests if available
    for test_id, test in all_tests.items():
        matches   = match_details.get(test_id, [])
        test_type = test.get('test_type')
        # Get LLM score if available (set by process_diff_and_select_tests)
        llm_score = test.get('llm_score')
        base_score = calculate_confidence_score(matches, test_type, llm_score=llm_score)
        
        test['confidence_score'] = min(100, base_score)

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


def find_tests_ast_only(conn, search_queries: Dict, file_changes: List[Dict] = None, schema: str = None) -> Dict[str, Any]:
    """
    Find tests using only AST-based strategies (0-3), excluding semantic search.
    
    Args:
        conn: Database connection
        search_queries: Dictionary with search queries
        file_changes: List of file change dictionaries
        schema: Database schema name (defaults to DB_SCHEMA if not provided)
    
    Returns:
        Dictionary with test results from AST-based matching only
    """
    # Use provided schema or fall back to DB_SCHEMA
    target_schema = schema or DB_SCHEMA
    
    all_tests = {}
    match_details = {}
    
    # Strategy 0: Function-level matching
    if search_queries.get('changed_functions'):
        function_tests = query_tests_for_functions(conn, search_queries['changed_functions'], schema=target_schema)
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
            search_queries['test_file_candidates'],
            schema=target_schema
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
                change_type = analyze_file_change_type(file_change)
                if change_type != 'import_only':
                    classes = extract_production_classes_from_file(file_path)
                    for module_name in classes[:1]:
                        integration_tests = find_integration_tests_for_module(conn, module_name, schema=target_schema)
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
            exact_tests = query_tests_for_classes(conn, [prod_class], schema=target_schema)
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
    # ── Guard: skip module_matches when constant symbols ALREADY matched tests ──
    # When reverse_index keys by symbol (e.g. PHONE_REGEX), exact match is enough.
    # When it keys by ApiConstants/file only, exact on MAX_* returns 0 — we must NOT
    # skip module_matches or AST yields 0 (semantic-only), as in ApiConstants diffs.
    #
    # RULE: If UPPER_CASE constants are in exact_matches BUT Strategy 0–2 found
    #       nothing, run module_matches anyway, then keep only tests whose names
    #       mention at least one changed constant (reduces EMAIL_REGEX noise when
    #       PHONE_REGEX changed, when we *do* have symbol-level hits).
    def _is_screaming_constant(name: str) -> bool:
        return bool(name) and name[0].isupper() and name.upper() == name

    constant_symbols = [
        c for c in search_queries.get('exact_matches', [])
        if _is_screaming_constant(c)
    ]
    has_constant_symbols = bool(constant_symbols)
    tests_before_module = len(all_tests)
    force_module_for_constants = has_constant_symbols and tests_before_module == 0

    if search_queries.get('module_matches') and (
        not has_constant_symbols or force_module_for_constants
    ):
        import logging as _log_ast

        _log_ast.getLogger(__name__).info(
            "[AST] Module pattern query%s",
            " (fallback: constant symbols had no reverse_index hit)"
            if force_module_for_constants
            else "",
        )
        for module_pattern in search_queries['module_matches']:
            module_tests = query_tests_module_pattern(
                conn, module_pattern, prefer_direct=True, schema=target_schema
            )
            for test in module_tests:
                # NOTE: The name-filter that previously checked whether the test
                # label contains the changed constant symbol has been REMOVED.
                #
                # Reason: it broke the "shared constants file cascade" pattern.
                # When actiotypes.js (action-type constants) renames a value,
                # ALL tests that import from that module are affected — not just
                # the one whose describe() block names the constant.
                # The filter was too narrow for this common JS/TS pattern and
                # caused ALL reducer tests to be missed (only the test whose
                # method name literally contained the constant was kept).
                #
                # Correctness: when force_module_for_constants=True we are
                # ALREADY in fallback mode (exact symbol query found 0 rows).
                # Including the full module is the correct conservative choice.
                test_id = test['test_id']
                if test_id not in all_tests:
                    all_tests[test_id] = test
                    match_details[test_id] = []
                match_details[test_id].append({
                    'type': 'module',
                    'pattern': module_pattern,
                    'reference_type': test.get('reference_type', 'direct_import'),
                    'confidence': 'medium',
                    'module_fallback_for_constants': force_module_for_constants,
                })
    # ──────────────────────────────────────────────────────────────────────────

    # Strategy 4a: Same test-file expansion (co-located tests)
    # When we find tests by Strategy 2 (exact match for a FUNCTION/method), also include
    # ALL tests that live in the SAME test file. This captures:
    #   - favouritesReducer tests (same file as toastReducer tests)
    #   - isUserLoggedIn/updateNewTokenDetails tests (same file as capitalizeFirstLetter tests)
    #
    # IMPORTANT: Only expand from camelCase FUNCTION matches (e.g. capitalizeFirstLetter,
    # toastReducer), NOT from UPPER_CASE constant matches (e.g. PHONE_REGEX, EMAIL_REGEX).
    # When a constant changes, only tests for THAT specific constant are relevant —
    # expanding to the whole file would include tests for unrelated constants.
    exact_and_func_test_ids = set()
    for test_id, matches in list(match_details.items()):
        has_direct_match = any(
            m.get('type') in ('exact', 'function_level') for m in matches
        )
        if not has_direct_match:
            continue

        # Check if this test was found ONLY via UPPER_CASE constant exact matches.
        # If so, skip same-file expansion (only PHONE_REGEX tests → don't expand to EMAIL_REGEX etc.)
        direct_matches = [m for m in matches if m.get('type') in ('exact', 'function_level')]
        is_constant_only = all(
            m.get('type') == 'exact' and
            m.get('class', '') and
            m['class'].upper() == m['class'] and
            not any(c.isdigit() for c in m['class'][:2])  # not just digits
            for m in direct_matches
        )

        # Check if this test was found ONLY via module-level exact matches
        # (e.g. 'helpers.utilities', 'ApiEndPoints', 'services.api.endpoints').
        # Module-level matches are file-level references — they find ALL tests that
        # import from a changed file, including tests for UNCHANGED functions.
        # Expanding the whole test file from a module-level match causes false positives:
        #   - isUserLoggedIn/updateNewTokenDetails dragged in from auth-storage (scenario 4)
        #   - ApiConstants tests dragged in from api-navigation (scenario 4)
        # We use the explicitly tracked module_exact_matches set (not a heuristic dot-check)
        # so that module names with no dots (e.g. 'ApiEndPoints') are also caught.
        _module_names = set(search_queries.get('module_exact_matches', []))
        is_module_name_only = (
            bool(_module_names) and
            all(
                m.get('type') == 'exact' and m.get('class', '') in _module_names
                for m in direct_matches
            )
        )

        if not is_constant_only and not is_module_name_only:
            exact_and_func_test_ids.add(test_id)

    if exact_and_func_test_ids:
        # Collect unique test file paths from directly matched tests
        colocated_file_paths = set()
        for tid in exact_and_func_test_ids:
            t = all_tests.get(tid, {})
            fp = t.get('test_file_path') or t.get('file_path', '')
            if fp:
                colocated_file_paths.add(fp)

        with conn.cursor() as _cursor:
            for file_path in colocated_file_paths:
                try:
                    _cursor.execute(f"""
                        SELECT DISTINCT test_id, class_name, method_name, file_path, test_type
                        FROM {target_schema}.test_registry
                        WHERE file_path = %s
                        ORDER BY test_id
                    """, (file_path,))
                    for row in _cursor.fetchall():
                        test_id = row[0]
                        if test_id not in all_tests:
                            all_tests[test_id] = {
                                'test_id': test_id,
                                'class_name': row[1],
                                'method_name': row[2],
                                'test_file_path': row[3],
                                'test_type': row[4],
                                'match_type': 'direct_test_file'
                            }
                            match_details[test_id] = []
                        # Only add co-located match if test not already matched by exact/function
                        if test_id not in exact_and_func_test_ids:
                            already_has_colocated = any(
                                m.get('match_strategy') == 'colocated_in_same_file'
                                for m in match_details.get(test_id, [])
                            )
                            if not already_has_colocated:
                                match_details[test_id].append({
                                    'type': 'direct_file',
                                    'test_file': file_path,
                                    'match_strategy': 'colocated_in_same_file',
                                    'confidence': 'medium'
                                })
                except Exception as _e:
                    logger.debug(f"Strategy 4a colocated lookup error: {_e}")

    # Strategy 4: Source file stem-based test file lookup
    # When the changed production file has a clear stem (e.g. "utilities", "toastReducer"),
    # search for test files whose path contains that stem.
    # This finds "sibling" tests: tests for other functions in the same source file.
    # e.g. "utilities.js" → "utilities.pure.test.js" → checkNull/checkArray/etc. tests
    if file_changes:
        from pathlib import Path as _Path
        # 'constants' is intentionally NOT in this set — when a constants file changes
        # (e.g. constants.ts), Strategy 4 must find the sibling test file
        # (e.g. regex.constants.test.js) so ALL tests for symbols in that file
        # are included as HIGH-priority siblings.
        # Only truly ambiguous one-word stems (index, main, app, etc.) are excluded,
        # plus directory-level generic names (reducer, actions, store …) that would
        # match every test file in that folder, not just the changed file.
        _GENERIC_STEMS = {
            # General
            'index', 'main', 'app', 'config', 'types',
            'utils', 'helpers', 'common', 'shared', 'base',
            # State-management directories
            'reducer', 'reducers', 'actions', 'action',
            'store', 'stores', 'state',
            'selectors', 'selector',
            'saga', 'sagas', 'epic', 'epics',
            # Service / infra directories
            'service', 'services',
            'middleware', 'middlewares',
            'context', 'contexts',
            'hooks', 'hook',
        }
        for file_change in file_changes:
            file_path = file_change.get('file', '')
            if not file_path:
                continue
            file_stem = _Path(file_path).stem.lower()  # e.g. "utilities", "toastreducer"
            if not file_stem or file_stem in _GENERIC_STEMS:
                continue  # Skip generic names to avoid over-broad matches

            with conn.cursor() as _cursor:
                # Search test_registry for test files whose path contains the stem
                # and looks like a test file (contains "test" or "spec")
                pattern_test = f'%{file_stem}%.test%'
                pattern_spec = f'%{file_stem}%.spec%'
                try:
                    _cursor.execute(f"""
                        SELECT DISTINCT test_id, class_name, method_name, file_path, test_type
                        FROM {target_schema}.test_registry
                        WHERE (file_path ILIKE %s OR file_path ILIKE %s)
                        ORDER BY test_id
                    """, (pattern_test, pattern_spec))
                    for row in _cursor.fetchall():
                        test_id = row[0]
                        if test_id not in all_tests:
                            all_tests[test_id] = {
                                'test_id': test_id,
                                'class_name': row[1],
                                'method_name': row[2],
                                'test_file_path': row[3],
                                'test_type': row[4],
                                'match_type': 'direct_test_file'
                            }
                            match_details[test_id] = []
                        match_details[test_id].append({
                            'type': 'direct_file',
                            'test_file': row[3],
                            'match_strategy': 'file_stem',
                            'confidence': 'medium'
                        })
                except Exception as _e:
                    logger.debug(f"Strategy 4 file_stem lookup error: {_e}")

    # Calculate scores
    for test_id, test in all_tests.items():
        matches = match_details.get(test_id, [])
        test_type = test.get('test_type')
        # Get LLM score if available
        llm_score = test.get('llm_score')
        test['confidence_score'] = calculate_confidence_score(matches, test_type, llm_score=llm_score)
    
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


async def find_tests_semantic_only_async(conn, search_queries: Dict, file_changes: List[Dict] = None, schema: str = None, test_repo_id: str = None, semantic_config: Dict = None, diff_content: str = None) -> Dict[str, Any]:
    """
    Async version: Find tests using only semantic search (vector embeddings).
    
    Args:
        conn: Database connection (not used for semantic search, but kept for compatibility)
        semantic_config: Optional semantic search configuration dict with:
            - similarity_threshold: Optional[float]
            - max_results: int
            - num_query_variations: int
            - top_k, top_p: optional
            After the run, semantic_config may contain _rag_diagnostics (unified RAG pipeline).
        search_queries: Dictionary with search queries
        file_changes: List of file change dictionaries
        schema: Database schema name (not used for semantic search, but kept for compatibility)
        test_repo_id: Test repository ID to filter embeddings in Pinecone
        diff_content: Optional git diff content for Advanced RAG
    
    Returns:
        Dictionary with test results from semantic search only
    """
    all_tests = {}
    match_details = {}
    
    changed_functions = search_queries.get('changed_functions', [])
    # NOTE: Do NOT exit early when changed_functions is empty.
    # Constants, config, and data files (e.g. constants.ts, ApiEndPoints.js)
    # have no function definitions, so changed_functions will always be [].
    # build_rich_change_description() has a file-name fallback for exactly
    # this case, but it is never reached if we bail out here.
    # Only skip semantic search when we truly have nothing to work with
    # (no functions AND no file_changes AND no diff_content).
    if not changed_functions and not file_changes and not diff_content:
        return {
            'tests': [],
            'match_details': {},
            'total_tests': 0,
            'method': 'Semantic'
        }
    
    try:
        # Extract config parameters if provided
        similarity_threshold = None
        max_results = 10000
        use_adaptive_thresholds = True
        top_k = None
        top_p = None
        
        if semantic_config:
            similarity_threshold = semantic_config.get('similarity_threshold')
            # Use max_results from config if provided, otherwise keep default
            if semantic_config.get('max_results') is not None:
                max_results = semantic_config.get('max_results')
            use_adaptive_thresholds = semantic_config.get('use_adaptive_thresholds', True)
            top_k = semantic_config.get('top_k')
            top_p = semantic_config.get('top_p')
        
        semantic_matches = await find_tests_semantic(
            conn,
            changed_functions,
            file_changes,
            similarity_threshold=similarity_threshold,
            max_results=max_results,
            use_adaptive_thresholds=use_adaptive_thresholds,
            test_repo_id=test_repo_id,
            top_k=top_k,
            top_p=top_p,
            diff_content=diff_content,
            semantic_config=semantic_config,
            deleted_symbols=search_queries.get("deleted_symbols"),
            added_symbols=search_queries.get("added_symbols"),
            renamed_symbols=search_queries.get("renamed_symbols"),
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

        out = {
            'tests': sorted_tests,
            'match_details': match_details,
            'total_tests': len(all_tests),
            'method': 'Semantic',
        }
        if semantic_config and isinstance(semantic_config, dict):
            rd = semantic_config.get('_rag_diagnostics')
            if rd is not None:
                out['rag_diagnostics'] = rd
        return out
    except Exception as e:
        return {
            'tests': [],
            'match_details': {},
            'total_tests': 0,
            'method': 'Semantic',
            'error': str(e)
        }


def find_tests_semantic_only(conn, search_queries: Dict) -> Dict[str, Any]:
    """
    Synchronous wrapper: Find tests using only semantic search (vector embeddings).
    
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
        # Try to get existing event loop, if none exists create one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use asyncio.run()
                # This means we're in an async context - should use async version instead
                raise RuntimeError(
                    "Cannot use synchronous find_tests_semantic_only from async context. "
                    "Use find_tests_semantic_only_async() instead."
                )
        except RuntimeError:
            # No event loop exists, safe to create one
            pass
        
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
def find_integration_tests_for_module(conn, production_class: str, schema: str = None) -> List[Dict]:
    """
    Find integration/e2e tests that reference a production module.
    
    Args:
        conn: Database connection
        production_class: Production class/module name (e.g., "agent.langgraph_agent")
        schema: Database schema name (defaults to DB_SCHEMA if not provided)
    
    Returns:
        List of test dictionaries (integration/e2e tests only)
    """
    target_schema = schema or DB_SCHEMA
    integration_tests = []
    
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"[{target_schema}] Searching for integration tests for: {production_class}")
    
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
            FROM {target_schema}.reverse_index ri
            JOIN {target_schema}.test_registry tr ON ri.test_id = tr.test_id
            WHERE ri.production_class = %s
              AND tr.test_type IN ('integration', 'e2e')
            ORDER BY tr.test_type, tr.test_id
        """, (production_class,))
        
        rows = cursor.fetchall()
        if not rows:
            # Debug: Check test types available
            cursor.execute(f"""
                SELECT DISTINCT test_type, COUNT(*) 
                FROM {target_schema}.test_registry 
                GROUP BY test_type
            """)
            test_types = cursor.fetchall()
            logger.debug(f"[{target_schema}] No integration tests found. Available test types: {test_types}")
        
        for row in rows:
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
def calculate_confidence_score(
    match_details: list,
    test_type: str,
    llm_score: Optional[float] = None,
    speed_factor: float = 1.0  # Fixed 10% component
) -> int:
    """
    Calculate 0-100 confidence score using weighted components.

    Weighted Scoring Formula:
      - AST Component (40%): Based on match_details (existing logic)
      - Vector Component (30%): Semantic similarity from match_details
      - LLM Component (20%): LLM relevance score (0.0-1.0) if available
      - Speed Component (10%): Fixed value (constant for all tests)

    Formula: total_score = (ast * 0.40) + (vector * 0.30) + (llm * 0.20) + (speed * 0.10)

    AST Component Calculation (0-100 scale):
      Base scores (before multipliers):
        function_level (exact)              → 95-100
        function_level (indirect)           → 85-94
        exact + direct_import                → 75-84
        exact + string_ref (patch/Mock)     → 65-74
        module pattern + direct_import       → 55-64
        module pattern (indirect)            → 45-54
        direct_file                          → 50-60
        integration                          → 40-50

      Match quality multipliers:
        direct_import: 1.0x
        string_ref (patch): 0.9x
        indirect_import: 0.8x
        module pattern only: 0.7x

      Bonuses:
        Multiple match types: +5
        Function-level match: +10 (on top of base)

      Penalties:
        Only module patterns: -10
        No function-level matches: -5

      Test type bonus (applied once):
        unit: +5
        integration: +3
        e2e / unknown / None: +0

    Vector Component (0-100 scale):
      Semantic similarity from match_details, capped at 60

    LLM Component (0-100 scale):
      llm_score * 100 if available, else 0

    Speed Component (0-100 scale):
      Fixed value: 10 (constant for all tests)

    Final score capped at 100, floored at 0.
    """
    if not match_details:
        return 0
    
    base_score = 0
    has_function_level = False
    has_exact_match = False
    has_direct_reference = False
    has_module_pattern_only = False
    match_types = set()
    
    # First pass: determine base score and match characteristics
    for match in match_details:
        mtype = match.get('type', '')
        ref_type = match.get('reference_type', '')
        match_types.add(mtype)
        
        # Determine base score based on match type
        if mtype == 'function_level':
            has_function_level = True
            # Check if it's direct (patch_ref) or indirect (function_call)
            source = match.get('source', '')
            if source == 'patch_ref':
                base_score = max(base_score, 95)  # Exact function-level match
            else:
                base_score = max(base_score, 85)  # Indirect function-level match
            has_exact_match = True
            if ref_type == 'direct_import' or source == 'patch_ref':
                has_direct_reference = True
                
        elif mtype == 'exact':
            has_exact_match = True
            if ref_type == 'direct_import':
                base_score = max(base_score, 75)
                has_direct_reference = True
            elif ref_type == 'string_ref':
                base_score = max(base_score, 65)
                has_direct_reference = True
            else:
                base_score = max(base_score, 60)
                
        elif mtype == 'direct_file':
            base_score = max(base_score, 50)
            has_direct_reference = True
            
        elif mtype == 'integration':
            base_score = max(base_score, 40)
            
        elif mtype == 'module':
            if base_score == 0:  # Only module pattern, no other matches
                has_module_pattern_only = True
            if ref_type == 'direct_import':
                base_score = max(base_score, 55)
                has_direct_reference = True
            else:
                base_score = max(base_score, 45)
                
        elif mtype == 'semantic':
            # Semantic matches should NOT contribute to AST score
            # They are handled separately in the Vector Component calculation
            # Skip semantic matches when calculating AST base_score
            pass
    
    # Apply multipliers based on reference quality
    multiplier = 1.0
    for match in match_details:
        ref_type = match.get('reference_type', '')
        if ref_type == 'direct_import':
            multiplier = max(multiplier, 1.0)
        elif ref_type == 'string_ref':
            multiplier = max(multiplier, 0.9)
        elif ref_type == 'indirect_import':
            multiplier = max(multiplier, 0.8)
        elif match.get('type') == 'module' and not has_direct_reference:
            multiplier = max(multiplier, 0.7)
    
    score = int(base_score * multiplier)
    
    # Apply bonuses
    if has_function_level:
        score += 10
    if len(match_types) > 1:
        score += 5
    
    # Apply penalties
    if has_module_pattern_only:
        score -= 10
    if not has_function_level and not has_exact_match:
        score -= 5
    
    # Test type bonus
    test_type_lower = (test_type or '').lower()
    if test_type_lower == 'unit':
        score += 5
    elif test_type_lower == 'integration':
        score += 3
    
    # Ensure AST score is within valid range
    ast_score = max(0, min(100, score))
    
    # Calculate Vector Component (30%)
    # No artificial cap: the similarity score already reflects true relevance.
    # Capping at 60 previously suppressed valid semantic signals when similarity was
    # high (e.g. 85%) and caused "Both" matches to be rated only "medium".
    vector_score = 0
    for match in match_details:
        if match.get('type') == 'semantic':
            similarity = match.get('similarity', 0)
            if similarity:
                vector_score = max(vector_score, int(similarity * 100))  # full range 0-100
    
    # Calculate LLM Component (20%)
    llm_component = 0
    if llm_score is not None and llm_score > 0:
        llm_component = int(llm_score * 100)  # Convert 0.0-1.0 to 0-100
    
    # Calculate Speed Component (10%) - Fixed value
    speed_component = 10  # Fixed 10% contribution
    
    # Weighted combination: 40% AST + 30% Vector + 20% LLM + 10% Speed
    total_score = (
        (ast_score * 0.40) +
        (vector_score * 0.30) +
        (llm_component * 0.20) +
        (speed_component * 0.10)
    )
    
    has_semantic_match = vector_score > 0

    # Dual-confirmation bonus: when BOTH AST (exact/function) and Semantic agree on a
    # test, it is far more likely to be relevant than if only one method found it.
    # Award +15 so the combined score clears the "high" threshold (≥70).
    if has_semantic_match and has_exact_match:
        total_score += 15

    # Semantic-primary boost: when there is NO AST match but semantic similarity is
    # high (≥70%), semantic is the only evidence and should drive the score.
    # The standard formula gives (0×0.4 + 95×0.3 + llm×0.2 + 10×0.1) ≈ 39 → "low",
    # which under-values a 95% cosine match. Switch to semantic-primary weighting.
    if not has_exact_match and ast_score == 0 and vector_score >= 70:
        semantic_primary = int(
            vector_score * 0.70 +
            llm_component * 0.20 +
            speed_component * 0.10
        )
        total_score = max(total_score, semantic_primary)

    # IMPORTANT: For AST-only tests (no semantic match), ensure minimum score
    if not has_semantic_match and ast_score > 0:
        if total_score < 50:
            total_score = max(50, int(ast_score * 0.60 + speed_component * 0.10))
    
    # Ensure final score is within valid range
    total_score = max(0, min(100, int(total_score)))
    
    return total_score
