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


def parse_git_diff(diff_content: str, file_list: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Parse git diff content to extract changed information.
    
    Args:
        diff_content: Raw git diff output as string
        file_list: Optional list of file paths (for GitLab API diffs that don't include headers)
    
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
    import logging
    logger = logging.getLogger(__name__)
    
    if not diff_content.strip():
        logger.debug("Empty diff content provided")
        return {
            'changed_files': [],
            'changed_classes': [],
            'changed_methods': [],
            'file_changes': []
        }
    
    # If file_list is provided and diff doesn't have headers, use file_list
    # This handles GitLab API diffs that only contain hunk content
    has_headers = diff_content.strip().startswith(('diff --git', '--- '))
    starts_with_hunk = '@@' in diff_content[:100]  # Check first 100 chars for hunk marker
    
    # Filter out empty strings from file_list before checking
    filtered_file_list = None
    if file_list:
        filtered_file_list = [f for f in file_list if f and f.strip()]
        if not filtered_file_list:
            filtered_file_list = None
    
    if filtered_file_list and not has_headers and starts_with_hunk:
        logger.info(f"Using provided file_list ({len(filtered_file_list)} files) for headerless diff. Files: {filtered_file_list[:3]}")
        # GitLab returns one diff per file, concatenated with newlines
        # Split by detecting file boundaries: look for sequences of @@ that might indicate new files
        # Better approach: split diff into chunks and assign to files
        lines = diff_content.split('\n')
        file_changes = []
        changed_files = list(filtered_file_list)
        changed_classes = set()
        changed_methods = set()
        
        # Split diff into file chunks
        # GitLab returns one diff per file, concatenated with newlines
        # Strategy: If single file, use entire diff. If multiple files, split by detecting boundaries
        # Simple approach: split evenly by hunk count, or process all for single file
        if len(filtered_file_list) == 1:
            # Single file - use entire diff
            file_boundaries = [0, len(lines)]
        else:
            # Multiple files - try to detect boundaries
            # Find all hunk starts
            hunk_starts = []
            for i, line in enumerate(lines):
                if re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line):
                    hunk_starts.append(i)
            
            # If we have hunks, try to split evenly
            if hunk_starts and len(hunk_starts) >= len(filtered_file_list):
                chunks_per_file = len(hunk_starts) // len(filtered_file_list)
                file_boundaries = [0]
                for i in range(1, len(filtered_file_list)):
                    if i * chunks_per_file < len(hunk_starts):
                        file_boundaries.append(hunk_starts[i * chunks_per_file])
                file_boundaries.append(len(lines))
            else:
                # Fallback: assign entire diff to first file, empty for others
                # This handles edge cases where splitting is unclear
                file_boundaries = [0, len(lines)] + [len(lines)] * (len(filtered_file_list) - 1)
        
        # Process each file's diff chunk
        for file_idx, file_path in enumerate(filtered_file_list):
            start_idx = file_boundaries[file_idx] if file_idx < len(file_boundaries) else 0
            end_idx = file_boundaries[file_idx + 1] if file_idx + 1 < len(file_boundaries) else len(lines)
            
            file_info = {
                'file': file_path,
                'status': 'modified',
                'additions': 0,
                'deletions': 0,
                'changed_lines': [],
                'changed_classes': [],
                'changed_methods': []
            }
            
            # Process this file's chunk
            in_hunk = False
            for i in range(start_idx, end_idx):
                line = lines[i]
                
                # Match hunk header
                hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)', line)
                if hunk_match:
                    in_hunk = True
                    hunk_context = hunk_match.group(5).strip() if hunk_match.group(5) else ""
                    if hunk_context:
                        # Extract class
                        class_match = re.search(r'class\s+(\w+)', hunk_context)
                        if class_match:
                            class_name = class_match.group(1)
                            changed_classes.add(class_name)
                            if class_name not in file_info['changed_classes']:
                                file_info['changed_classes'].append(class_name)
                        
                        # Extract method
                        method_match = re.search(r'(?:def|function|public|private|protected)\s+(\w+)\s*\(', hunk_context)
                        if method_match:
                            method_name = method_match.group(1)
                            changed_methods.add(method_name)
                            if method_name not in file_info['changed_methods']:
                                file_info['changed_methods'].append(method_name)
                    continue
                
                # Process hunk content
                if in_hunk:
                    if line.startswith('+') and not line.startswith('+++'):
                        file_info['additions'] += 1
                        clean_line = line.lstrip('+- ')
                        # Extract class
                        class_match = re.search(r'class\s+(\w+)', clean_line)
                        if class_match:
                            class_name = class_match.group(1)
                            changed_classes.add(class_name)
                            if class_name not in file_info['changed_classes']:
                                file_info['changed_classes'].append(class_name)
                        # Extract method
                        method_match = None
                        if re.search(r'\bdef\s+(\w+)', clean_line):
                            method_match = re.search(r'\bdef\s+(\w+)', clean_line)
                        elif re.search(r'\b(public|private|protected|static)\s+.*?\s+(\w+)\s*\(', clean_line):
                            method_match = re.search(r'\b(public|private|protected|static)\s+.*?\s+(\w+)\s*\(', clean_line)
                            if method_match:
                                method_name = method_match.group(2)
                            else:
                                method_match = re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line)
                        elif re.search(r'\bfunction\s+(\w+)', clean_line):
                            method_match = re.search(r'\bfunction\s+(\w+)', clean_line)
                        elif re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line):
                            method_match = re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line)
                        
                        if method_match:
                            method_name = method_match.group(1) if len(method_match.groups()) == 1 else method_match.group(2)
                            if method_name not in ['if', 'for', 'while', 'switch', 'catch', 'try', 'else']:
                                changed_methods.add(method_name)
                                if method_name not in file_info['changed_methods']:
                                    file_info['changed_methods'].append(method_name)
                    elif line.startswith('-') and not line.startswith('---'):
                        file_info['deletions'] += 1
            
            file_changes.append(file_info)
        
        logger.info(f"Parsed headerless diff: {len(changed_files)} files, {len(changed_classes)} classes, {len(changed_methods)} methods")
        if changed_files:
            logger.info(f"Detected files: {changed_files[:5]}")
        return {
            'changed_files': list(set(changed_files)),
            'changed_classes': sorted(list(changed_classes)),
            'changed_methods': sorted(list(changed_methods)),
            'file_changes': file_changes
        }
    
    # Debug: Log diff format
    logger.debug(f"Diff content length: {len(diff_content)} chars")
    first_500 = diff_content[:500].replace('\n', '\\n')
    logger.debug(f"Diff preview (first 500 chars): {first_500}")
    
    lines = diff_content.split('\n')
    file_changes = []
    changed_files = []
    changed_classes = set()
    changed_methods = set()
    
    current_file = None
    current_file_info = None
    in_hunk = False
    
    # Track different diff formats we encounter
    diff_format_patterns = {
        'git': r'diff --git a/(.+?) b/(.+?)$',
        'index': r'index [a-f0-9]+\.\.[a-f0-9]+',
        'new_file': r'new file mode',
        'deleted_file': r'deleted file mode',
        '---': r'^--- (.+)$',
        '+++': r'^\+\+\+ (.+)$'
    }
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Match file header: "diff --git a/path b/path" (standard git format)
        file_match = re.match(r'diff --git a/(.+?) b/(.+?)$', line)
        
        # Also try alternative formats (GitLab might use different format)
        if not file_match:
            # Try "--- a/path" and "+++ b/path" format (unified diff)
            if line.startswith('--- '):
                old_path = line[4:].strip()
                # Look for corresponding +++ line
                if i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
                    new_path = lines[i + 1][4:].strip()
                    # Remove a/ or b/ prefix if present
                    old_path = old_path.lstrip('a/')
                    new_path = new_path.lstrip('b/')
                    current_file = new_path if new_path != '/dev/null' else old_path
                    changed_files.append(current_file)
                    
                    # Save previous file if exists
                    if current_file_info:
                        file_changes.append(current_file_info)
                    
                    current_file_info = {
                        'file': current_file,
                        'status': 'modified',
                        'additions': 0,
                        'deletions': 0,
                        'changed_lines': [],
                        'changed_classes': [],
                        'changed_methods': []
                    }
                    in_hunk = False
                    i += 2  # Skip both --- and +++ lines
                    continue
        
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
        
        # Match hunk header: "@@ -start,count +start,count @@ optional_context"
        hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)', line)
        if hunk_match and current_file_info:
            in_hunk = True
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
            
            # Extract class/method from hunk header context (the part after @@)
            hunk_context = hunk_match.group(5).strip() if hunk_match.group(5) else ""
            if hunk_context:
                # Check for class definition in context
                class_match = re.search(r'class\s+(\w+)', hunk_context)
                if class_match:
                    class_name = class_match.group(1)
                    changed_classes.add(class_name)
                    if class_name not in current_file_info['changed_classes']:
                        current_file_info['changed_classes'].append(class_name)
                
                # Check for method/function definition in context
                method_match = re.search(r'def\s+(\w+)', hunk_context)
                if method_match:
                    method_name = method_match.group(1)
                    changed_methods.add(method_name)
                    if method_name not in current_file_info['changed_methods']:
                        current_file_info['changed_methods'].append(method_name)
            
            # Track line numbers in this hunk
            old_line = old_start
            new_line = new_start
            i += 1
            continue
        
        # Process hunk content
        if in_hunk and current_file_info:
            # Helper function to extract class/method from any line
            def extract_definitions(line_content: str):
                """Extract class and method definitions from a line (multi-language)."""
                # Remove diff prefix if present
                clean_line = line_content.lstrip('+- ')
                
                # Check for class definition (Python: class X, Java: class X, etc.)
                class_match = re.search(r'class\s+(\w+)', clean_line)
                if class_match:
                    class_name = class_match.group(1)
                    changed_classes.add(class_name)
                    if class_name not in current_file_info['changed_classes']:
                        current_file_info['changed_classes'].append(class_name)
                
                # Check for method/function definition
                # Python: def method_name(
                # Java: public/private/protected [static] [return_type] method_name(
                # JavaScript/TypeScript: method_name( or function method_name(
                method_match = None
                
                # Python style: def method_name
                if re.search(r'\bdef\s+(\w+)', clean_line):
                    method_match = re.search(r'\bdef\s+(\w+)', clean_line)
                # Java style: [modifiers] return_type method_name( or method_name(
                elif re.search(r'\b(public|private|protected|static)\s+.*?\s+(\w+)\s*\(', clean_line):
                    method_match = re.search(r'\b(public|private|protected|static)\s+.*?\s+(\w+)\s*\(', clean_line)
                    if method_match:
                        method_name = method_match.group(2)  # Get the method name (second group)
                    else:
                        # Try simpler: method_name( pattern
                        method_match = re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line)
                # JavaScript/TypeScript: function method_name or method_name(
                elif re.search(r'\bfunction\s+(\w+)', clean_line):
                    method_match = re.search(r'\bfunction\s+(\w+)', clean_line)
                # Generic: method_name( pattern (works for Java, JS, etc.)
                elif re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line):
                    method_match = re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line)
                
                if method_match:
                    method_name = method_match.group(1) if len(method_match.groups()) == 1 else method_match.group(2)
                    # Filter out common non-method patterns
                    if method_name not in ['if', 'for', 'while', 'switch', 'catch', 'try', 'else']:
                        changed_methods.add(method_name)
                        if method_name not in current_file_info['changed_methods']:
                            current_file_info['changed_methods'].append(method_name)
            
            if line.startswith('+') and not line.startswith('+++'):
                # Added line
                current_file_info['additions'] += 1
                new_line += 1
                extract_definitions(line)
                current_file_info['changed_lines'].append(new_line)
            
            elif line.startswith('-') and not line.startswith('---'):
                # Deleted line
                current_file_info['deletions'] += 1
                old_line += 1
                extract_definitions(line)  # Also check deleted lines for context
                current_file_info['changed_lines'].append(old_line)
            
            elif line.startswith(' '):
                # Context line (unchanged) - but may contain class/method definitions
                # that are relevant to the changes nearby
                # Only extract if we're in a hunk with actual changes (additions/deletions)
                if current_file_info.get('additions', 0) > 0 or current_file_info.get('deletions', 0) > 0:
                    extract_definitions(line)
                old_line += 1
                new_line += 1
            
            i += 1
            continue
        
        i += 1
    
    # Save last file
    if current_file_info:
        file_changes.append(current_file_info)
    
    # Debug logging
    logger.info(f"Parsed diff: {len(changed_files)} files, {len(changed_classes)} classes, {len(changed_methods)} methods")
    if changed_files:
        logger.info(f"Changed files: {changed_files[:5]}")
    else:
        logger.warning("No files detected in diff! First 20 lines:")
        logger.warning('\n'.join(lines[:20]))
        if file_list:
            logger.warning(f"file_list was provided but not used: {file_list[:3]}")
            logger.warning(f"has_headers={has_headers}, starts_with_hunk={starts_with_hunk}")
    
    return {
        'changed_files': list(set(changed_files)),
        'changed_classes': sorted(list(changed_classes)),
        'changed_methods': sorted(list(changed_methods)),
        'file_changes': file_changes
    }


def is_production_file(
    file_path: str,
    parser_registry=None,
    config: Dict = None
) -> bool:
    """
    Check if a file is a production code file (language-agnostic).
    
    Filters out:
    - Files without a parser (unsupported languages)
    - Test files (using language-specific patterns)
    - Artifact/data files
    - Configuration files
    
    Args:
        file_path: File path to check
        parser_registry: Optional parser registry instance
        config: Optional language configuration dictionary
    
    Returns:
        True if it's a production file, False otherwise
    """
    if not file_path or file_path == '/dev/null':
        return False
    
    filepath = Path(file_path)
    
    # If parser registry provided, use it to detect language
    if parser_registry:
        parser = parser_registry.get_parser(filepath)
        if not parser:
            return False  # No parser available for this file type
        
        # Check if it's a test file using language config
        if config:
            try:
                from config.config_loader import get_test_patterns, get_language_config
                language = parser.language_name
                lang_config = get_language_config(config, language)
                if lang_config:
                    test_patterns = get_test_patterns(config, language)
                    filename = filepath.name
                    import fnmatch
                    for pattern in test_patterns:
                        if fnmatch.fnmatch(filename, pattern):
                            return False  # It's a test file
            except Exception:
                pass
    else:
        # Fallback: check for common production file extensions (language-agnostic)
        production_extensions = ['.py', '.java', '.js', '.ts', '.jsx', '.tsx', '.kt', '.go', '.rb', '.cs']
        if not any(file_path.endswith(ext) for ext in production_extensions):
            return False
    
    # Skip test files (generic check)
    file_lower = file_path.lower()
    if 'test' in file_lower:
        # More specific check: only skip if it's clearly a test file
        if file_lower.endswith('_test.py') or file_lower.endswith('test.py'):
            return False
        # Check for test directory patterns
        if '/test/' in file_lower or '\\test\\' in file_lower:
            if '/test/' in file_lower or '\\test\\' in file_lower:
                # Could be a test file, but be lenient - let parser decide
                pass
    
    # Skip artifact/data directories (language-agnostic)
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
        'static',
        'templates',
        'build',
        'dist',
        'target',
        'bin',
        'obj'
    ]
    
    for skip_dir in skip_dirs:
        if skip_dir in file_lower:
            return False
    
    return True


def is_production_python_file(file_path: str) -> bool:
    """
    Legacy function for backward compatibility.
    
    Deprecated: Use is_production_file() instead.
    """
    return is_production_file(file_path, parser_registry=None, config=None)


def extract_production_modules_from_file(
    file_path: str,
    parser_registry=None,
    project_root: Path = None,
    config: Dict = None
) -> List[str]:
    """
    Extract production module/package names from a file path (language-agnostic).
    
    This converts file paths to import-style module names that match
    what's stored in the database. Uses parser's resolve_module_name() method.
    
    Args:
        file_path: File path from git diff (e.g., "agent/agent_pool.py")
        parser_registry: Optional parser registry instance
        project_root: Optional project root directory for module resolution
        config: Optional language configuration dictionary
    
    Returns:
        List of possible production module/package names to search
    
    Example:
        >>> extract_production_modules_from_file("agent/agent_pool.py", parser_registry, project_root)
        ['agent.agent_pool', 'agent']
    """
    if not file_path or file_path == '/dev/null':
        return []
    
    filepath = Path(file_path)
    
    # Check if it's a production file
    if not is_production_file(file_path, parser_registry, config):
        return []
    
    # If parser registry provided, use parser's resolve_module_name
    if parser_registry and project_root:
        parser = parser_registry.get_parser(filepath)
        if parser:
            try:
                module_name = parser.resolve_module_name(filepath, project_root)
                
                # Generate search candidates
                candidates = [module_name]
                
                # Add parent module/package
                parts = module_name.split('.')
                if len(parts) > 1:
                    candidates.append(parts[0])
                
                return list(set(candidates))
            except Exception:
                pass
    
    # Fallback: Language-agnostic logic for common file types
    # Handle Python, JavaScript, Java, TypeScript files
    supported_extensions = ['.py', '.js', '.jsx', '.java', '.ts', '.tsx']
    file_ext = filepath.suffix.lower()
    
    if file_ext not in supported_extensions:
        return []
    
    # Remove extension
    file_path_no_ext = str(filepath.with_suffix(''))
    
    # Convert path to module name (replace path separators with dots)
    module_name = file_path_no_ext.replace('/', '.').replace('\\', '.')
    
    # Apply language-specific prefix removal rules from config
    if config:
        lang_config = None
        for lang_name, lang_cfg in config.get('languages', {}).items():
            if file_ext in lang_cfg.get('extensions', []):
                lang_config = lang_cfg
                break
        
        if lang_config:
            module_resolution = lang_config.get('module_resolution', {})
            remove_prefixes = module_resolution.get('remove_prefixes', [])
            for prefix in remove_prefixes:
                if module_name.startswith(prefix):
                    module_name = module_name[len(prefix):].lstrip('.')
                    break
    
    # Database stores module paths WITHOUT "backend." prefix (Python-specific)
    # So "backend/agent/agent_pool.py" becomes "agent.agent_pool"
    if module_name.startswith('backend.'):
        module_name = module_name[8:]  # Remove "backend." prefix
    
    # Also remove common frontend prefixes
    if module_name.startswith('client.'):
        module_name = module_name[7:]  # Remove "client." prefix
    if module_name.startswith('src.'):
        module_name = module_name[4:]  # Remove "src." prefix
    
    # Generate search candidates
    candidates = [module_name]
    
    # Add parent module
    parts = module_name.split('.')
    if len(parts) > 1:
        candidates.append(parts[0])
        # Also add component name (last part) for JavaScript components
        if file_ext in ['.js', '.jsx', '.ts', '.tsx']:
            candidates.append(parts[-1])  # e.g., "ChatPage" from "components.ChatPage"
    
    return list(set(candidates))


def extract_production_classes_from_file(file_path: str) -> List[str]:
    """
    Legacy function for backward compatibility.
    
    Deprecated: Use extract_production_modules_from_file() instead.
    """
    return extract_production_modules_from_file(file_path, parser_registry=None, project_root=None, config=None)


def extract_test_file_candidates(
    file_path: str,
    parser_registry=None,
    config: Dict = None
) -> List[str]:
    """
    Extract potential test file names from a production file path (language-agnostic).
    
    Enhanced with multiple strategies to find test files in any repository structure.
    Uses language-specific test patterns from config.
    
    Args:
        file_path: Production file path (e.g., "backend/agent/agent_pool.py")
        parser_registry: Optional parser registry instance
        config: Optional language configuration dictionary
    
    Returns:
        List of potential test file names to search for
    
    Example:
        >>> extract_test_file_candidates("backend/agent/agent_pool.py", parser_registry, config)
        ['test_agent_pool.py', 'test_agent_agent_pool.py']
    """
    if not file_path or file_path == '/dev/null':
        return []
    
    filepath = Path(file_path)
    candidates = set()
    
    # Get language-specific test patterns if available
    test_patterns = None
    extension = filepath.suffix
    
    if parser_registry and config:
        parser = parser_registry.get_parser(filepath)
        if parser:
            try:
                from config.config_loader import get_test_patterns, get_language_config
                language = parser.language_name
                lang_config = get_language_config(config, language)
                if lang_config:
                    test_patterns = get_test_patterns(config, language)
            except Exception:
                pass
    
    # Fallback to Python patterns if not found
    if not test_patterns:
        if not file_path.endswith('.py'):
            return []
        test_patterns = ['test_*.py', '*_test.py']
    
    # Get file name without extension
    file_stem = filepath.stem  # e.g., 'agent_pool'
    
    # Generate candidates based on language-specific test patterns
    import fnmatch
    for pattern in test_patterns:
        # Replace * with file_stem to generate candidate
        candidate = pattern.replace('*', file_stem)
        candidates.add(candidate)
    
    # Also add common patterns based on file structure
    if len(filepath.parts) > 1:
        parent_dir = filepath.parts[-2]  # e.g., 'agent'
        # Try parent_dir_file_stem pattern
        for pattern in test_patterns:
            candidate = pattern.replace('*', f"{parent_dir}_{file_stem}")
            candidates.add(candidate)
    
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


def build_search_queries(
    file_changes: List[Dict],
    parser_registry=None,
    project_root: Path = None,
    config: Dict = None,
    diff_content: str = None
) -> Dict[str, List[str]]:
    """
    Build database search queries from file changes (language-agnostic).
    
    Processes production files from any language with a registered parser.
    
    Args:
        file_changes: List of file change dictionaries from parse_git_diff
        parser_registry: Optional parser registry instance
        project_root: Optional project root directory for module resolution
        config: Optional language configuration dictionary
        diff_content: Optional full diff content for parsing new files
    
    Returns:
        Dictionary with search strategies:
        - exact_matches: Exact production class/module names
        - module_matches: Module-level patterns (agent.*)
        - file_patterns: File name patterns
        - test_file_candidates: Direct test file names to search
        - changed_functions: Function-level changes
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
        
        # Extract production modules (language-agnostic, already filters)
        modules = extract_production_modules_from_file(file_path, parser_registry, project_root, config)
        
        # If no modules extracted, skip this file (not a production file)
        if not modules:
            continue
        
        for module_name in modules:
            # Exact match
            exact_matches.append(module_name)
            
            # Module-level match (if has dots)
            if '.' in module_name:
                module_part = module_name.split('.')[0]
                module_pattern = f"{module_part}.*"
                if module_pattern not in module_matches:
                    module_matches.append(module_pattern)
        
        # File pattern (for fallback searches) - language-agnostic
        filepath = Path(file_path)
        if filepath.stem:
            file_patterns.append(filepath.stem)
        
        # Extract direct test file candidates (language-agnostic)
        test_candidates = extract_test_file_candidates(file_path, parser_registry, config)
        test_file_candidates.extend(test_candidates)
    
    # Extract changed functions with modules (for function-level matching)
    changed_functions = extract_changed_functions_with_modules(
        file_changes, diff_content, parser_registry, project_root, config
    )
    
    return {
        'exact_matches': list(set(exact_matches)),
        'module_matches': list(set(module_matches)),
        'file_patterns': list(set(file_patterns)),
        'test_file_candidates': list(set(test_file_candidates)),
        'changed_functions': changed_functions  # Function-level changes
    }


def extract_definitions_from_diff(
    diff_content: str,
    file_path: str,
    parser_registry=None,
    config: Dict = None
) -> Dict[str, List[str]]:
    """
    Extract class and function definitions from diff content for new files (language-agnostic).
    
    Parses class and function definitions from git diff using language-specific patterns.
    
    Args:
        diff_content: Full git diff content as string
        file_path: Path of the file being analyzed
        parser_registry: Optional parser registry instance
        config: Optional language configuration dictionary
    
    Returns:
        Dictionary with:
        - 'classes': List of class names found
        - 'functions': List of function names found
    """
    classes = []
    functions = []
    
    filepath = Path(file_path)
    language = None
    syntax_patterns = None
    
    # Get language-specific patterns if parser registry and config available
    if parser_registry and config:
        parser = parser_registry.get_parser(filepath)
        if parser:
            language = parser.language_name
            try:
                from config.config_loader import get_language_config
                lang_config = get_language_config(config, language)
                if lang_config:
                    syntax_patterns = lang_config.get('syntax_patterns', {})
            except Exception:
                pass
    
    # Default to Python patterns if not found
    if not syntax_patterns:
        syntax_patterns = {
            'class': r'^\+.*class\s+(\w+)',
            'function': r'^\+.*def\s+(\w+)'
        }
    
    class_pattern = syntax_patterns.get('class', r'^\+.*class\s+(\w+)')
    func_pattern = syntax_patterns.get('function', r'^\+.*def\s+(\w+)')
    
    # Find the section for this file in the diff
    file_section = False
    in_hunk = False
    
    for line in diff_content.split('\n'):
        # Check if we're in the section for this file
        if line.startswith('diff --git'):
            file_section = False
            in_hunk = False
            # Check if this is our file
            if file_path in line:
                file_section = True
        elif file_section and line.startswith('@@'):
            in_hunk = True
        elif file_section and in_hunk:
            # Look for added lines with class or function definitions
            if line.startswith('+') and not line.startswith('+++'):
                # Extract class definition using language-specific pattern
                class_match = re.search(class_pattern, line)
                if class_match:
                    classes.append(class_match.group(1))
                
                # Extract function definition using language-specific pattern
                func_match = re.search(func_pattern, line)
                if func_match:
                    functions.append(func_match.group(1))
    
    return {
        'classes': list(set(classes)),
        'functions': list(set(functions))
    }


def extract_changed_functions_with_modules(
    file_changes: List[Dict],
    diff_content: str = None,
    parser_registry=None,
    project_root: Path = None,
    config: Dict = None
) -> List[Dict[str, str]]:
    """
    Extract changed functions with their module names from file changes (language-agnostic).
    
    Converts file paths and changed methods to module.function format
    that can be used to query the test_function_mapping table.
    
    For new files (status='added'), extracts definitions from diff content.
    
    Args:
        file_changes: List of file change dictionaries from parse_git_diff
        diff_content: Optional full diff content for parsing new files
        parser_registry: Optional parser registry instance
        project_root: Optional project root directory for module resolution
        config: Optional language configuration dictionary
    
    Returns:
        List of dictionaries with:
        - module: Module name (e.g., 'agent.langgraph_agent')
        - function: Function name (e.g., 'initialize')
    """
    changed_functions = []
    
    for file_change in file_changes:
        file_path = file_change['file']
        status = file_change.get('status', 'modified')
        
        # Skip import-only changes (unless it's a new file)
        if status != 'added':
            change_type = analyze_file_change_type(file_change)
            if change_type == 'import_only':
                continue
        
        # Only process production files (language-agnostic)
        if not is_production_file(file_path, parser_registry, config):
            continue
        
        # For new files, extract definitions from diff
        if status == 'added' and diff_content:
            definitions = extract_definitions_from_diff(diff_content, file_path, parser_registry, config)
            # Use extracted functions if available, otherwise use changed_methods
            functions_to_process = definitions.get('functions', [])
            if not functions_to_process:
                functions_to_process = file_change.get('changed_methods', [])
        else:
            # For modified files, use changed_methods from diff parser
            functions_to_process = file_change.get('changed_methods', [])
        
        if not functions_to_process:
            continue
        
        # Convert file path to module name (language-agnostic)
        # e.g., 'agent/langgraph_agent.py' -> 'agent.langgraph_agent'
        module_names = extract_production_modules_from_file(file_path, parser_registry, project_root, config)
        if not module_names:
            continue
        
        # Use the first (most specific) module name
        primary_module = module_names[0]
        
        # Create module.function entries for each function
        for method_name in functions_to_process:
            changed_functions.append({
                'module': primary_module,
                'function': method_name
            })
    
    # Remove duplicates (same module.function combination)
    seen = set()
    unique_functions = []
    for func in changed_functions:
        key = (func['module'], func['function'])
        if key not in seen:
            seen.add(key)
            unique_functions.append(func)
    
    return unique_functions


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
