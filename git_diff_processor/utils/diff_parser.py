"""
Git Diff Parser

This module parses git diff output (unified diff format) to extract:
- Changed files
- Changed classes (from class definitions)
- Changed methods (from method signatures)
- File status (added, deleted, modified)
- Line numbers

It handles standard git diff format and extracts production code references
that can be used to query the database.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path


def parse_git_diff(diff_content: str) -> Dict[str, Any]:
    """
    Parse git diff content to extract changed information.
    
    Args:
        diff_content: Raw git diff output as string
    
    Returns:
        Dictionary with parsed diff information:
        - changed_files: List of changed file paths
        - changed_classes: List of changed class names
        - changed_methods: List of changed method names
        - file_changes: List of detailed file change information
    
    Example:
        >>> diff = "diff --git a/file.py b/file.py\\n..."
        >>> result = parse_git_diff(diff)
        >>> result['changed_files']
        ['file.py']
    """
    if not diff_content.strip():
        return {
            'changed_files': [],
            'changed_classes': [],
            'changed_methods': [],
            'file_changes': []
        }
    
    lines = diff_content.split('\n')
    file_changes = []
    changed_files = []
    changed_classes = set()
    changed_methods = set()
    
    current_file = None
    current_file_info = None
    in_hunk = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Match file header: "diff --git a/path b/path"
        file_match = re.match(r'diff --git a/(.+?) b/(.+?)$', line)
        if file_match:
            # Save previous file if exists
            if current_file_info:
                file_changes.append(current_file_info)
            
            # Start new file
            old_path = file_match.group(1)
            new_path = file_match.group(2)
            current_file = new_path if new_path != '/dev/null' else old_path
            changed_files.append(current_file)
            
            # Determine file status
            status = 'modified'
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if 'new file' in next_line or 'deleted file' in next_line:
                    if 'new file' in next_line:
                        status = 'added'
                    elif 'deleted file' in next_line:
                        status = 'deleted'
            
            current_file_info = {
                'file': current_file,
                'status': status,
                'additions': 0,
                'deletions': 0,
                'changed_lines': [],
                'changed_classes': [],
                'changed_methods': []
            }
            in_hunk = False
            i += 1
            continue
        
        # Match hunk header: "@@ -start,count +start,count @@"
        hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if hunk_match and current_file_info:
            in_hunk = True
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
            
            # Track line numbers in this hunk
            old_line = old_start
            new_line = new_start
            i += 1
            continue
        
        # Process hunk content
        if in_hunk and current_file_info:
            if line.startswith('+') and not line.startswith('+++'):
                # Added line
                current_file_info['additions'] += 1
                new_line += 1
                
                # Check for class definition
                class_match = re.search(r'class\s+(\w+)', line)
                if class_match:
                    class_name = class_match.group(1)
                    changed_classes.add(class_name)
                    if class_name not in current_file_info['changed_classes']:
                        current_file_info['changed_classes'].append(class_name)
                
                # Check for method/function definition
                method_match = re.search(r'def\s+(\w+)', line)
                if method_match:
                    method_name = method_match.group(1)
                    changed_methods.add(method_name)
                    if method_name not in current_file_info['changed_methods']:
                        current_file_info['changed_methods'].append(method_name)
                
                current_file_info['changed_lines'].append(new_line)
            
            elif line.startswith('-') and not line.startswith('---'):
                # Deleted line
                current_file_info['deletions'] += 1
                old_line += 1
                current_file_info['changed_lines'].append(old_line)
            
            elif line.startswith(' '):
                # Context line (unchanged)
                old_line += 1
                new_line += 1
            
            i += 1
            continue
        
        i += 1
    
    # Save last file
    if current_file_info:
        file_changes.append(current_file_info)
    
    return {
        'changed_files': list(set(changed_files)),
        'changed_classes': sorted(list(changed_classes)),
        'changed_methods': sorted(list(changed_methods)),
        'file_changes': file_changes
    }


def is_production_python_file(file_path: str) -> bool:
    """
    Check if a file is a Python production code file.
    
    Filters out:
    - Non-Python files (.css, .tsx, .txt, .db, .bin, .json, etc.)
    - Test files
    - Artifact/data files
    - Frontend files (TypeScript/React)
    - Configuration files
    
    Args:
        file_path: File path to check
    
    Returns:
        True if it's a Python production file, False otherwise
    """
    if not file_path or file_path == '/dev/null':
        return False
    
    # Must be a Python file
    if not file_path.endswith('.py'):
        return False
    
    # Skip test files
    file_lower = file_path.lower()
    if 'test' in file_lower or file_path.endswith('_test.py'):
        return False
    
    # Skip artifact/data directories
    skip_dirs = [
        'mlartifacts',
        'artifacts',
        'data/',
        'chromadb_data',
        'node_modules',
        '__pycache__',
        '.git',
        'venv',
        'env',
        'frontend',  # Frontend code (TypeScript/React)
        'static',
        'templates'
    ]
    
    for skip_dir in skip_dirs:
        if skip_dir in file_lower:
            return False
    
    return True


def extract_production_classes_from_file(file_path: str) -> List[str]:
    """
    Extract production class/module names from a file path.
    
    This converts file paths to import-style module names that match
    what's stored in the database.
    
    Only processes Python production files (filters out test files,
    artifacts, data files, frontend files, etc.)
    
    Args:
        file_path: File path from git diff (e.g., "agent/agent_pool.py")
    
    Returns:
        List of possible production class/module names to search
    
    Example:
        >>> extract_production_classes_from_file("agent/agent_pool.py")
        ['agent.agent_pool', 'agent']
        >>> extract_production_classes_from_file("frontend/src/ChatPage.tsx")
        []
    """
    if not file_path or file_path == '/dev/null':
        return []
    
    # Only process Python production files
    if not is_production_python_file(file_path):
        return []
    
    # Remove .py extension
    file_path = file_path[:-3]
    
    # Convert path to module name
    module_name = file_path.replace('/', '.').replace('\\', '.')
    
    # Database stores module paths WITHOUT "backend." prefix
    # So "backend/agent/agent_pool.py" becomes "agent.agent_pool"
    if module_name.startswith('backend.'):
        module_name = module_name[8:]  # Remove "backend." prefix
    
    # Generate search candidates
    candidates = []
    
    # Add full module path (e.g., "agent.agent_pool")
    candidates.append(module_name)
    
    # Add parent module (e.g., "agent" from "agent.agent_pool")
    parts = module_name.split('.')
    if len(parts) > 1:
        parent_module = parts[0]
        candidates.append(parent_module)
    
    return list(set(candidates))  # Remove duplicates


def extract_test_file_candidates(file_path: str) -> List[str]:
    """
    Extract potential test file names from a production file path.
    
    Enhanced with multiple strategies to find test files in any repository structure.
    
    Args:
        file_path: Production file path (e.g., "backend/agent/agent_pool.py")
    
    Returns:
        List of potential test file names to search for
    
    Example:
        >>> extract_test_file_candidates("backend/agent/agent_pool.py")
        ['test_agent_pool.py', 'test_agent_agent_pool.py', 'test_agent_pool_*.py']
        >>> extract_test_file_candidates("backend/api/routes.py")
        ['test_routes.py', 'test_api_routes.py', 'test_routes_*.py']
    """
    if not file_path or file_path == '/dev/null':
        return []
    
    # Only for Python files
    if not file_path.endswith('.py'):
        return []
    
    path_obj = Path(file_path)
    candidates = set()
    
    # Get file name without extension
    file_stem = path_obj.stem  # e.g., 'agent_pool'
    
    # Strategy 1: Direct test file name: test_<filename>.py
    candidates.add(f"test_{file_stem}.py")
    
    # Strategy 2: If file is in a subdirectory, check parent module pattern
    # e.g., backend/agent/agent_pool.py -> test_agent_agent_pool.py
    if len(path_obj.parts) > 1:
        parent_dir = path_obj.parts[-2]  # e.g., 'agent'
        candidates.add(f"test_{parent_dir}_{file_stem}.py")
    
    # Strategy 3: Check for test_<parent>_<file>.py pattern
    # e.g., backend/api/routes.py -> test_api_routes.py
    if len(path_obj.parts) >= 2:
        parent = path_obj.parts[-2]
        candidates.add(f"test_{parent}_{file_stem}.py")
    
    # Strategy 4: For nested modules, try full module path
    # e.g., backend/agent/agent_pool.py -> test_agent_agent_pool.py (already covered)
    # But also try: test_agent_pool_*.py for parameterized tests
    candidates.add(f"test_{file_stem}_*.py")
    
    # Strategy 5: Try without underscores (for camelCase files)
    if '_' in file_stem:
        camel_case = file_stem.replace('_', '')
        candidates.add(f"test_{camel_case}.py")
    
    # Strategy 6: Try with module prefix if in subdirectory
    if len(path_obj.parts) >= 2:
        # Build module path: agent.agent_pool
        module_parts = path_obj.parts[-2:]  # ['agent', 'agent_pool.py']
        module_name = '.'.join([p.replace('.py', '') for p in module_parts])
        # Convert to test pattern: test_agent_agent_pool.py
        test_module_name = module_name.replace('.', '_')
        candidates.add(f"test_{test_module_name}.py")
    
    return sorted(list(candidates))  # Return sorted list for consistency


def analyze_file_change_type(file_change: Dict) -> str:
    """
    Determine the type of change in a file.
    
    Returns:
        - 'code': Actual code changes (classes, methods, logic)
        - 'import_only': Only import statements changed
        - 'comment_only': Only comments changed
        - 'deleted': File was deleted
        - 'added': New file added
    """
    if file_change['status'] == 'deleted':
        return 'deleted'
    
    if file_change['status'] == 'added':
        return 'added'
    
    # Check if there are actual code changes (classes, methods)
    has_code_changes = (
        file_change.get('changed_classes') or 
        file_change.get('changed_methods') or
        file_change.get('additions', 0) > 0
    )
    
    if not has_code_changes:
        return 'comment_only'
    
    # Check if changes are primarily in import section (typically first 50 lines)
    changed_lines = file_change.get('changed_lines', [])
    if changed_lines:
        import_section_changes = [line for line in changed_lines if line <= 50]
        # If all changes are in import section and no classes/methods changed
        if (len(import_section_changes) == len(changed_lines) and 
            not file_change.get('changed_classes') and 
            not file_change.get('changed_methods')):
            return 'import_only'
    
    return 'code'


def build_search_queries(file_changes: List[Dict]) -> Dict[str, List[str]]:
    """
    Build database search queries from file changes.
    
    Only processes Python production files, filtering out:
    - Non-Python files (CSS, TSX, TXT, DB, etc.)
    - Test files
    - Artifact/data files
    - Frontend files
    
    Args:
        file_changes: List of file change dictionaries from parse_git_diff
    
    Returns:
        Dictionary with search strategies:
        - exact_matches: Exact production class names
        - module_matches: Module-level patterns (agent.*)
        - file_patterns: File name patterns
        - test_file_candidates: Direct test file names to search
    """
    exact_matches = []
    module_matches = []
    file_patterns = []
    test_file_candidates = []
    
    for file_change in file_changes:
        file_path = file_change['file']
        
        # Skip import-only changes (they don't affect production code behavior)
        change_type = analyze_file_change_type(file_change)
        if change_type == 'import_only':
            continue  # Don't match tests for import-only changes
        
        # Extract production classes (this function already filters)
        classes = extract_production_classes_from_file(file_path)
        
        # If no classes extracted, skip this file (not a production Python file)
        if not classes:
            continue
        
        for class_name in classes:
            # Exact match
            exact_matches.append(class_name)
            
            # Module-level match (if has dots)
            if '.' in class_name:
                module_part = class_name.split('.')[0]
                module_pattern = f"{module_part}.*"
                if module_pattern not in module_matches:
                    module_matches.append(module_pattern)
        
        # File pattern (for fallback searches) - only for Python files
        if file_path.endswith('.py'):
            file_name = Path(file_path).stem
            if file_name:
                file_patterns.append(file_name)
        
        # Extract direct test file candidates
        test_candidates = extract_test_file_candidates(file_path)
        test_file_candidates.extend(test_candidates)
    
    return {
        'exact_matches': list(set(exact_matches)),
        'module_matches': list(set(module_matches)),
        'file_patterns': list(set(file_patterns)),
        'test_file_candidates': list(set(test_file_candidates))
    }


def read_diff_file(file_path: Path) -> str:
    """
    Read git diff content from a file.
    
    Args:
        file_path: Path to the diff file
    
    Returns:
        Diff content as string
    
    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file can't be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Diff file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()
