"""
Git diff parsing and AST-query planning (single source of truth).

Parses unified diff output and builds DB search structures (exact matches,
module patterns, function-level keys, symbol deltas). There is no second
copy of this logic under git_diff_processor/ — that package imports here.

Call trace (typical):
  - API/CLI selection: ``process_diff_programmatic.process_diff_and_select_tests``
    → ``parse_git_diff`` / ``build_search_queries`` (this module)
  - CLI: ``git_diff_processor.git_diff_processor`` (main) → same functions
  - AST selection: ``git_diff_processor.selection_engine`` → helpers such as
    ``extract_production_classes_from_file``, ``analyze_file_change_type``
  - Semantic RAG: ``semantic.retrieval.rag_pipeline._resolve_symbols`` may call
    ``extract_deleted_added_renamed_symbols`` when symbol lists are empty
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
        logger.info(f"[PARSE] Headerless diff - using provided file list ({len(filtered_file_list)} file(s))")
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
                'changed_methods': [],
                'changed_line_ranges': [],  # [{method, start_line, end_line}]
            }
            
            # Process this file's chunk
            in_hunk = False
            # ── Headerless pre-change context tracking ─────────────────────────
            # Problem: git puts the *enclosing* function (e.g. getScreenNumber)
            # in the @@ header, not the actual function being changed.
            # The actual changed function (e.g. checkWhiteSpace) appears as a
            # context line (starts with space) BEFORE the first +/- line in the
            # hunk.  The headerless path ignores context lines entirely, so we
            # must track them manually.
            #
            # Rule: scan context lines before the first +/- line; the LAST
            # function declaration seen just before the change is the real
            # changed function — override the hunk-header method with it.
            _hl_pending_method = None        # method from @@ header (might be wrong)
            _hl_pre_change_method = None     # last fn decl seen before first +/-
            _hl_hunk_has_changes = False     # True once we see a +/- line
            _HL_SKIP_KW = {'if','for','while','switch','catch','try','else','return'}
            _hl_new_start = 0                # new-file start line from @@ header
            _hl_new_line = 0                 # current new-file line counter
            _hl_min_changed = 0             # first changed line in this hunk
            _hl_max_changed = 0             # last  changed line in this hunk
            # ────────────────────────────────────────────────────────────────────
            for i in range(start_idx, end_idx):
                line = lines[i]
                
                # Match hunk header
                hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)', line)
                if hunk_match:
                    # ── Flush pending method from previous hunk ────────────────
                    # When a new hunk starts, commit the resolved method for the
                    # previous hunk (pre-change override beats header if found).
                    if _hl_pending_method is not None:
                        resolved = _hl_pre_change_method or _hl_pending_method
                        changed_methods.add(resolved)
                        if resolved not in file_info['changed_methods']:
                            file_info['changed_methods'].append(resolved)
                        # Record line range for the flushed method
                        if _hl_min_changed > 0:
                            file_info.setdefault('changed_line_ranges', []).append({
                                'method': resolved,
                                'start_line': _hl_min_changed,
                                'end_line': _hl_max_changed or _hl_min_changed,
                            })
                    # Reset for new hunk
                    _hl_hunk_has_changes = False
                    _hl_pre_change_method = None
                    _hl_new_start = int(hunk_match.group(3)) if hunk_match.group(3) else 0
                    _hl_new_line = _hl_new_start - 1   # will be incremented on first + line
                    _hl_min_changed = 0
                    _hl_max_changed = 0
                    # ──────────────────────────────────────────────────────────
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
                        
                        # Save hunk-header method as pending (may be overridden by context scan)
                        _hh_m = re.search(r'(?:async\s+)?function\s+(\w+)', hunk_context)
                        if not _hh_m:
                            _hh_m = re.search(r'\bdef\s+(\w+)', hunk_context)
                        if not _hh_m:
                            _hh_m = re.search(
                                r'\b(?:public|private|protected|static)\s+\S+\s+(\w+)\s*\(', hunk_context)
                        _hl_pending_method = _hh_m.group(1) if _hh_m else None
                    else:
                        _hl_pending_method = None
                    continue
                
                # ── Pre-change context scan (headerless path) ──────────────────
                # If we are inside a hunk but have not yet seen a +/- line,
                # scan context lines (starting with space) for function declarations.
                # The last one found just before the first change is the actual
                # function being modified, overriding the @@ header.
                if in_hunk and not _hl_hunk_has_changes and line.startswith(' '):
                    _ctx_clean = line.lstrip(' ')
                    _ctx_fn = None
                    _m_ctx = re.search(r'(?:async\s+)?function\s+(\w+)', _ctx_clean)
                    if _m_ctx:
                        _ctx_fn = _m_ctx.group(1)
                    elif not _ctx_fn:
                        _m_ctx = re.search(
                            r'(?:export\s+)?(?:const|let|var)\s+([a-z][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(',
                            _ctx_clean,
                        )
                        if _m_ctx and '=>' in _ctx_clean:
                            _ctx_fn = _m_ctx.group(1)
                    if _ctx_fn and _ctx_fn not in _HL_SKIP_KW:
                        _hl_pre_change_method = _ctx_fn  # override pending header method
                    # Also extract post-change context functions (after +/- lines)
                # ────────────────────────────────────────────────────────────────

                # Process hunk content
                if in_hunk:
                    if line.startswith('+') and not line.startswith('+++'):
                        _hl_hunk_has_changes = True
                        _hl_new_line += 1
                        # Track changed line range for the pending method
                        if _hl_pending_method is not None or _hl_pre_change_method is not None:
                            if _hl_min_changed == 0:
                                _hl_min_changed = _hl_new_line
                            _hl_max_changed = _hl_new_line
                        file_info['additions'] += 1
                        clean_line = line.lstrip('+- ')
                        # Extract class
                        class_match = re.search(r'class\s+(\w+)', clean_line)
                        if class_match:
                            class_name = class_match.group(1)
                            changed_classes.add(class_name)
                            if class_name not in file_info['changed_classes']:
                                file_info['changed_classes'].append(class_name)
                        # Extract TypeScript/JavaScript exported constants/enums/types.
                        # e.g. "export const PHONE_REGEX = ..." → adds PHONE_REGEX to
                        # changed_classes so the reverse_index is queried by symbol name
                        # instead of the generic file/module name.
                        # Only on CHANGED (+) lines — NOT context lines — to prevent
                        # neighbouring constants in the same hunk from being included.
                        ts_export_match = re.search(
                            r'\b(?:export\s+)?(?:const|let|var|enum|type|interface)\s+([A-Z_][A-Za-z0-9_]*)\b',
                            clean_line
                        )
                        if ts_export_match:
                            symbol_name = ts_export_match.group(1)
                            if symbol_name[0].isupper():  # UPPER_CASE or PascalCase only
                                changed_classes.add(symbol_name)
                                if symbol_name not in file_info['changed_classes']:
                                    file_info['changed_classes'].append(symbol_name)
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
                        _hl_hunk_has_changes = True
                        file_info['deletions'] += 1
                        # Also extract symbols from deleted lines so we recognise
                        # both sides of a rename/rewrite (e.g. old PHONE_REGEX value).
                        clean_del = line.lstrip('+- ')
                        ts_del_match = re.search(
                            r'\b(?:export\s+)?(?:const|let|var|enum|type|interface)\s+([A-Z_][A-Za-z0-9_]*)\b',
                            clean_del
                        )
                        if ts_del_match:
                            symbol_name = ts_del_match.group(1)
                            if symbol_name[0].isupper():
                                changed_classes.add(symbol_name)
                                if symbol_name not in file_info['changed_classes']:
                                    file_info['changed_classes'].append(symbol_name)
            
            # Flush final hunk's pending method for this file
            if _hl_pending_method is not None:
                resolved = _hl_pre_change_method or _hl_pending_method
                changed_methods.add(resolved)
                if resolved not in file_info['changed_methods']:
                    file_info['changed_methods'].append(resolved)
                # Record line range for the final hunk
                if _hl_min_changed > 0:
                    file_info.setdefault('changed_line_ranges', []).append({
                        'method': resolved,
                        'start_line': _hl_min_changed,
                        'end_line': _hl_max_changed or _hl_min_changed,
                    })

            file_changes.append(file_info)
        
        logger.info(f"[PARSE] Headerless diff parsed: {len(changed_files)} file(s), {len(changed_classes)} class(es), {len(changed_methods)} method(s)")
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

    # ── Deferred hunk-context tracking ────────────────────────────────────────
    # Git puts the enclosing function in the @@ header (e.g. handleLogout).
    # But when the actual +lines ADD a brand-new top-level function after the
    # enclosing function closes, the context function was NOT itself changed.
    # We defer the decision: save the context method and only commit it to
    # changed_methods after we've seen the hunk body.
    #
    # Rule: if the hunk has ZERO deletions AND the +lines define at least one
    #       new top-level function (different from the context method), the
    #       context method was only "nearby" — skip it.
    # Otherwise (hunk has deletions, or no new function defined), the context
    # method WAS modified — add it as before.
    _pending_context_method = None      # context method saved from @@ header
    _pending_context_file_info = None   # the file_info the pending method belongs to
    _hunk_deletions = 0                 # - lines seen in current hunk
    _hunk_new_toplevel_fns: set = set() # new top-level fn names from + lines
    # ── Line-range tracking ─────────────────────────────────────────────────
    # Records {method, start_line, end_line} for every confirmed method change.
    # start/end are NEW-FILE line numbers from the +lines in the hunk.
    # Reset each time _finalize_pending_context commits or discards a method.
    _hunk_min_changed_line: int = 0     # first +/- line number in current hunk
    _hunk_max_changed_line: int = 0     # last  +/- line number in current hunk
    # ────────────────────────────────────────────────────────────────────────

    _TOP_LEVEL_FN_RE = re.compile(
        r'^\+(?:export\s+)?(?:async\s+)?(?:function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
        r'|(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s*)?\()',
    )

    def _finalize_pending_context():
        """Commit or discard the deferred hunk-context method."""
        nonlocal _pending_context_method, _pending_context_file_info
        nonlocal _hunk_deletions, _hunk_new_toplevel_fns
        nonlocal _hunk_min_changed_line, _hunk_max_changed_line
        if _pending_context_method is None:
            return
        # Decide: add only when the hunk actually modified existing code
        # (has deletions) OR when no competing new function was added.
        skip = (_hunk_deletions == 0 and bool(_hunk_new_toplevel_fns)
                and _pending_context_method not in _hunk_new_toplevel_fns)
        if not skip:
            changed_methods.add(_pending_context_method)
            fi = _pending_context_file_info
            if fi and _pending_context_method not in fi.get('changed_methods', []):
                fi['changed_methods'].append(_pending_context_method)
            # ── Record the changed line range for this method ──────────────
            # start_line/end_line use NEW-file line numbers from +lines.
            # If only deletions happened (no +lines), fall back to old_line.
            if fi is not None and _hunk_min_changed_line > 0:
                fi.setdefault('changed_line_ranges', []).append({
                    'method': _pending_context_method,
                    'start_line': _hunk_min_changed_line,
                    'end_line': _hunk_max_changed_line or _hunk_min_changed_line,
                })
            # ───────────────────────────────────────────────────────────────
        _pending_context_method = None
        _pending_context_file_info = None
        _hunk_deletions = 0
        _hunk_new_toplevel_fns = set()
        _hunk_min_changed_line = 0
        _hunk_max_changed_line = 0
    # ──────────────────────────────────────────────────────────────────────────
    
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
                    resolved_file = new_path if new_path != '/dev/null' else old_path
                    
                    # --- Deduplication guard ---
                    # Standard git diffs emit BOTH a "diff --git a/x b/x" header AND
                    # a "--- a/x" / "+++ b/x" pair for the same file.  The `diff --git`
                    # handler (below) already created current_file_info for this file.
                    # If we blindly create a second entry here we end up with two dicts
                    # for the same file: the first (empty) from `diff --git` and the
                    # second (populated) from this `---`/`+++` block.
                    # When build_search_queries iterates over both, the first entry adds
                    # generic module names (e.g. "constants") to exact_matches as if no
                    # specific symbols were found, defeating the symbol-precision logic.
                    #
                    # Fix: if current_file_info already tracks this exact file, just
                    # reset the hunk state and keep using the SAME dict – no duplicate.
                    if current_file_info and current_file_info.get('file') == resolved_file:
                        # Same file already open – skip creating a duplicate entry.
                        in_hunk = False
                        i += 2  # Skip both --- and +++ lines
                        continue
                    
                    current_file = resolved_file
                    changed_files.append(current_file)
                    
                    # Finalize any deferred hunk-context for the previous file
                    _finalize_pending_context()
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
                        'changed_methods': [],
                        'changed_line_ranges': [],  # [{method, start_line, end_line}]
                    }
                    in_hunk = False
                    i += 2  # Skip both --- and +++ lines
                    continue
        
        if file_match:
            # Finalize any deferred hunk-context method for the previous file
            _finalize_pending_context()
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
                'changed_methods': [],
                'changed_line_ranges': [],  # [{method, start_line, end_line}]
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
            # Reset per-hunk line range (finalize carries previous values through
            # _finalize_pending_context; this reset covers hunks with no pending method)
            _hunk_min_changed_line = 0
            _hunk_max_changed_line = 0
            
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
                
                # Extract function name from hunk context line (supports Python, JS/TS, Java).
                # Git puts the enclosing function name after the last @@ in the hunk header.
                # e.g. "@@ -176,23 +176,17 @@ export function capitalizeFirstLetter(string) {"
                _hunk_method = None
                # Python: def funcName
                _m = re.search(r'\bdef\s+(\w+)', hunk_context)
                if _m:
                    _hunk_method = _m.group(1)
                # JS/TS regular function: function funcName / async function funcName
                if not _hunk_method:
                    _m = re.search(r'(?:async\s+)?function\s+(\w+)', hunk_context)
                    if _m:
                        _hunk_method = _m.group(1)
                # JS/TS arrow: export const funcName = (...) => / const funcName = async (...) =>
                if not _hunk_method:
                    _m = re.search(
                        r'(?:export\s+)?(?:const|let|var)\s+([a-z][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(',
                        hunk_context
                    )
                    if _m and '=>' in hunk_context:
                        _hunk_method = _m.group(1)
                # Java: public/private/protected ... methodName(
                if not _hunk_method:
                    _m = re.search(
                        r'\b(?:public|private|protected|static)\s+\S+\s+(\w+)\s*\(',
                        hunk_context
                    )
                    if _m:
                        _hunk_method = _m.group(1)
                _SKIP_CONTEXT_KW = {
                    'if', 'for', 'while', 'switch', 'catch', 'try', 'else', 'return'
                }
                if _hunk_method and _hunk_method not in _SKIP_CONTEXT_KW:
                    # ── Deferred: don't add immediately ──────────────────────
                    # First finalize the PREVIOUS hunk's pending context method,
                    # then register the new one as pending.
                    _finalize_pending_context()
                    _pending_context_method = _hunk_method
                    _pending_context_file_info = current_file_info
                    _hunk_deletions = 0
                    _hunk_new_toplevel_fns = set()
                    # ─────────────────────────────────────────────────────────
                else:
                    # No context method — finalize any previous pending one
                    _finalize_pending_context()
            
            # Track line numbers in this hunk
            old_line = old_start
            new_line = new_start
            i += 1
            continue
        
        # Process hunk content
        if in_hunk and current_file_info:
            # Helper function to extract class/method from any line
            def extract_definitions(line_content: str, is_changed_line: bool = False):
                """Extract class and method definitions from a line (multi-language).
                
                Args:
                    line_content: The raw diff line (including +/- prefix)
                    is_changed_line: True if this is an added (+) or deleted (-) line.
                                     False for context lines (space prefix).
                                     TypeScript/JS constant symbols are ONLY extracted from
                                     changed lines to prevent context constants (unchanged
                                     lines in the same hunk) from polluting the query set.
                """
                # Remove diff prefix if present
                clean_line = line_content.lstrip('+- ')
                
                # Check for class definition (Python: class X, Java: class X, etc.)
                class_match = re.search(r'class\s+(\w+)', clean_line)
                if class_match:
                    class_name = class_match.group(1)
                    changed_classes.add(class_name)
                    if class_name not in current_file_info['changed_classes']:
                        current_file_info['changed_classes'].append(class_name)
                
                # Check for TypeScript/JavaScript: export const/let/var/enum/type/interface SYMBOL = ...
                # These are top-level named exports (regex constants, enums, type aliases, etc.)
                # e.g. "export const PHONE_REGEX = /.../" or "export enum Status {"
                # We treat them as "changed classes" so the reverse_index is queried for them.
                #
                # IMPORTANT: Only do this for actually changed (+/-) lines, NOT context lines.
                # A constants.ts hunk typically shows many surrounding constants as context.
                # If we extract symbols from context lines, all those unrelated constants
                # end up in changed_classes and pollute the reverse_index query.
                if is_changed_line:
                    ts_export_match = re.search(
                        r'\b(?:export\s+)?(?:const|let|var|enum|type|interface)\s+([A-Z_][A-Za-z0-9_]*)\b',
                        clean_line
                    )
                    if ts_export_match:
                        symbol_name = ts_export_match.group(1)
                        # Only include UPPER_CASE or PascalCase symbols (constants/types/enums)
                        # Skip lowercase variable declarations like "let result = ..." inside functions
                        if symbol_name[0].isupper():
                            changed_classes.add(symbol_name)
                            if symbol_name not in current_file_info['changed_classes']:
                                current_file_info['changed_classes'].append(symbol_name)

                # Check for method/function definition
                # Python: def method_name(
                # Java: public/private/protected [static] [return_type] method_name(
                # JavaScript/TypeScript: function method_name( OR const funcName = (...) =>
                method_match = None
                extracted_method_name = None
                
                # Python style: def method_name
                if re.search(r'\bdef\s+(\w+)', clean_line):
                    method_match = re.search(r'\bdef\s+(\w+)', clean_line)
                # Java style: [modifiers] return_type method_name( or method_name(
                elif re.search(r'\b(public|private|protected|static)\s+.*?\s+(\w+)\s*\(', clean_line):
                    method_match = re.search(r'\b(public|private|protected|static)\s+.*?\s+(\w+)\s*\(', clean_line)
                    if method_match:
                        extracted_method_name = method_match.group(2)
                    else:
                        method_match = re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line)
                # JS/TS: function functionName or async function functionName
                elif re.search(r'(?:async\s+)?function\s+(\w+)', clean_line):
                    method_match = re.search(r'(?:async\s+)?function\s+(\w+)', clean_line)
                # Generic: method_name( pattern (works for Java, JS, etc.)
                elif re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line):
                    method_match = re.search(r'\b(\w+)\s*\([^)]*\)\s*\{', clean_line)
                
                if method_match and not extracted_method_name:
                    extracted_method_name = (
                        method_match.group(1) if len(method_match.groups()) == 1
                        else method_match.group(2)
                    )
                _skip_kw = {'if', 'for', 'while', 'switch', 'catch', 'try', 'else', 'return'}
                if extracted_method_name and extracted_method_name not in _skip_kw:
                    changed_methods.add(extracted_method_name)
                    if extracted_method_name not in current_file_info['changed_methods']:
                        current_file_info['changed_methods'].append(extracted_method_name)
                
                # JS/TS arrow function: export const funcName = (...) => { OR
                #                       const funcName = async (...) =>
                # Also detect from context lines so we catch the enclosing function when
                # only the body changes (signature appears as context before first +/-)
                js_arrow = re.search(
                    r'(?:export\s+)?(?:const|let|var)\s+([a-z][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(',
                    clean_line
                )
                if js_arrow and '=>' in clean_line:
                    arrow_name = js_arrow.group(1)
                    _skip_arrow = {
                        'if', 'for', 'while', 'switch', 'catch', 'try', 'else',
                        'let', 'const', 'var', 'return', 'result', 'value',
                        'data', 'item', 'index', 'key', 'error', 'res', 'req'
                    }
                    if arrow_name not in _skip_arrow:
                        changed_methods.add(arrow_name)
                        if arrow_name not in current_file_info['changed_methods']:
                            current_file_info['changed_methods'].append(arrow_name)
            
            if line.startswith('+') and not line.startswith('+++'):
                # Added line — is_changed_line=True so TS/JS constant symbols are extracted
                current_file_info['additions'] += 1
                new_line += 1
                extract_definitions(line, is_changed_line=True)
                current_file_info['changed_lines'].append(new_line)
                # ── Line range tracking ──────────────────────────────────────
                if _pending_context_method:
                    if _hunk_min_changed_line == 0:
                        _hunk_min_changed_line = new_line
                    _hunk_max_changed_line = new_line
                # ─────────────────────────────────────────────────────────────
                # Track new top-level function definitions for deferred context decision
                if _pending_context_method:
                    _m_top = _TOP_LEVEL_FN_RE.match(line)
                    if _m_top:
                        fn_name = _m_top.group(1) or _m_top.group(2)
                        if fn_name and fn_name != _pending_context_method:
                            _hunk_new_toplevel_fns.add(fn_name)
            
            elif line.startswith('-') and not line.startswith('---'):
                # Deleted line — is_changed_line=True so TS/JS constant symbols are extracted
                current_file_info['deletions'] += 1
                old_line += 1
                extract_definitions(line, is_changed_line=True)  # Also check deleted lines for context
                current_file_info['changed_lines'].append(old_line)
                # ── Line range tracking (deletions use old_line) ─────────────
                if _pending_context_method:
                    if _hunk_min_changed_line == 0:
                        _hunk_min_changed_line = old_line
                    _hunk_max_changed_line = max(_hunk_max_changed_line, old_line)
                # ─────────────────────────────────────────────────────────────
                # A deletion means the context function body was modified in-place
                if _pending_context_method:
                    _hunk_deletions += 1
            
            elif line.startswith(' '):
                # Context line (unchanged) - extract class/method definitions but NOT TS constants.
                # is_changed_line defaults to False, so ts_export_match is skipped.
                # This prevents unrelated neighbouring constants from polluting changed_classes.
                _has_changes = (
                    current_file_info.get('additions', 0) > 0
                    or current_file_info.get('deletions', 0) > 0
                )
                if _has_changes:
                    extract_definitions(line, is_changed_line=False)
                else:
                    # ── Pre-change context scan ─────────────────────────────────────────
                    # We are still BEFORE the first +/- line.  Git puts the *enclosing*
                    # function in the @@ header — but that is the function that CONTAINS
                    # (or precedes) the hunk, not necessarily the function being changed.
                    #
                    # Example:
                    #   @@ -171,8 +171,9 @@ export function getScreenNumber(width) {
                    #    }                               ← context, pre-change
                    #                                    ← context, pre-change
                    #    export function checkWhiteSpace(string) {   ← context, pre-change
                    #   +  if (string === null …) return false;       ← first + line
                    #
                    # Here "checkWhiteSpace" is the ACTUAL changed function, but the @@
                    # header only knows about "getScreenNumber".  By scanning context
                    # lines before the first +/- line and updating _pending_context_method
                    # whenever we find a function declaration, the last function seen
                    # right before the changed lines wins — which is the correct function.
                    _pre_clean = line.lstrip(' ')
                    _pre_fn: str | None = None
                    _m_pre = re.search(r'(?:async\s+)?function\s+(\w+)', _pre_clean)
                    if _m_pre:
                        _pre_fn = _m_pre.group(1)
                    elif not _pre_fn:
                        _m_pre = re.search(
                            r'(?:export\s+)?(?:const|let|var)\s+([a-z][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(',
                            _pre_clean,
                        )
                        if _m_pre and '=>' in _pre_clean:
                            _pre_fn = _m_pre.group(1)
                    _SKIP_PRE_KW = {
                        'if', 'for', 'while', 'switch', 'catch', 'try', 'else', 'return',
                    }
                    if _pre_fn and _pre_fn not in _SKIP_PRE_KW:
                        # Override pending context: the function declaration closest to
                        # the changed lines is the actual changed function.
                        _pending_context_method = _pre_fn
                        _pending_context_file_info = current_file_info
                    # ────────────────────────────────────────────────────────────────────
                old_line += 1
                new_line += 1
            
            i += 1
            continue
        
        i += 1
    
    # Finalize any pending hunk-context method for the last file in the diff
    _finalize_pending_context()
    
    # Save last file
    if current_file_info:
        file_changes.append(current_file_info)
    
    logger.info(f"[PARSE] Diff parsed: {len(changed_files)} file(s), {len(changed_classes)} class(es), {len(changed_methods)} method(s)")
    if not changed_files:
        logger.warning("[PARSE] No files detected in diff")
        if file_list:
            logger.warning(f"[PARSE] file_list provided but not consumed (has_headers={has_headers}, starts_with_hunk={starts_with_hunk})")
    
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
            # No dedicated parser for this file type (e.g. tree-sitter-typescript not installed).
            # FALL THROUGH to the extension-based check below instead of hard-returning False.
            # Returning False here would silently exclude ALL TypeScript / unknown-language files
            # even when they are plainly production files (.ts, .tsx, etc.).
            production_extensions = ['.py', '.java', '.js', '.ts', '.jsx', '.tsx', '.kt', '.go', '.rb', '.cs']
            if not any(file_path.endswith(ext) for ext in production_extensions):
                return False
            # It's a known production extension — continue to the generic checks below
        else:
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


def extract_deleted_added_renamed_symbols(diff_content: str) -> Dict[str, Any]:
    """
    Extract symbol names that appear only in removed lines (deleted), only in
    added lines (added), or as renames (old -> new) from unified diff content.
    Used so AST can find tests referencing deleted symbols (e.g. advertisement)
    and so diff-impact can report coverage gaps and breakage warnings.

    Args:
        diff_content: Raw git diff output as string.

    Returns:
        Dictionary with:
        - deleted_symbols: List of symbol names only in - lines
        - added_symbols: List of symbol names only in + lines
        - renamed_symbols: List of {"old": str, "new": str}
    """
    if not (diff_content and diff_content.strip()):
        return {
            'deleted_symbols': [],
            'added_symbols': [],
            'renamed_symbols': []
        }

    # Patterns for symbols in diff lines (JS/TS, Python, Java-style)
    # export const X, export function X, export { X }, export default X
    # class X, def x(, function x(, x: (property/key)
    EXPORT_CONST = re.compile(r'[+-]\s*export\s+const\s+([A-Za-z_][A-Za-z0-9_]*)')
    EXPORT_FUNC = re.compile(r'[+-]\s*export\s+function\s+([A-Za-z_][A-Za-z0-9_]*)')
    EXPORT_VAR = re.compile(r'[+-]\s*export\s+(?:let|var)\s+([A-Za-z_][A-Za-z0-9_]*)')
    EXPORT_BRACE = re.compile(r'[+-]\s*export\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)')
    CLASS_DEF = re.compile(r'[+-]\s*class\s+([A-Za-z_][A-Za-z0-9_]*)')
    DEF_FUNC = re.compile(r'[+-]\s*def\s+([A-Za-z_][A-Za-z0-9_]*)')
    FUNC_DECL = re.compile(r'[+-]\s*function\s+([A-Za-z_][A-Za-z0-9_]*)')
    # Property/key: after +/- and spaces, identifier then : or (
    PROPERTY = re.compile(r'^[+-]\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:\(]')

    def collect_symbols(line_list: List[str], sign: str) -> set:
        out = set()
        for line in line_list:
            if not line.startswith(sign) or line.startswith(sign * 3):
                continue
            for pat in (EXPORT_CONST, EXPORT_FUNC, EXPORT_VAR, EXPORT_BRACE, CLASS_DEF, DEF_FUNC, FUNC_DECL):
                m = pat.search(line)
                if m:
                    out.add(m.group(1))
                    break
            m = PROPERTY.search(line)
            if m:
                out.add(m.group(1))
        return out

    lines = diff_content.split('\n')
    minus_lines = [ln for ln in lines if ln.startswith('-') and not ln.startswith('---')]
    plus_lines = [ln for ln in lines if ln.startswith('+') and not ln.startswith('+++')]

    symbols_minus = collect_symbols(minus_lines, '-')
    symbols_plus = collect_symbols(plus_lines, '+')

    # Renames: same structural line, one symbol swapped (e.g. -export const OLD / +export const NEW)
    renamed_symbols: List[Dict[str, str]] = []
    # Per-hunk pairing: look for -export const X and +export const Y in nearby lines
    for i, ln in enumerate(lines):
        if not ln.startswith('-') or ln.startswith('---'):
            continue
        m_old = EXPORT_CONST.search(ln)
        if not m_old:
            continue
        old_name = m_old.group(1)
        # Look in next few lines for +export const NEW
        for j in range(i + 1, min(i + 5, len(lines))):
            other = lines[j]
            if other.startswith('+') and not other.startswith('+++'):
                m_new = EXPORT_CONST.search(other)
                if m_new:
                    new_name = m_new.group(1)
                    if old_name != new_name:
                        renamed_symbols.append({'old': old_name, 'new': new_name})
                    break
            if other.startswith('@') or (other.startswith('-') and not other.startswith('---')):
                continue
            if other.strip() and not other.startswith('+'):
                break

    deleted_only = symbols_minus - symbols_plus - {r['old'] for r in renamed_symbols}
    added_only = symbols_plus - symbols_minus - {r['new'] for r in renamed_symbols}

    return {
        'deleted_symbols': list(deleted_only),
        'added_symbols': list(added_only),
        'renamed_symbols': renamed_symbols
    }


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
        - exact_matches: Exact production class/module names (includes deleted_symbols for AST)
        - module_matches: Module-level patterns (agent.*)
        - file_patterns: File name patterns
        - test_file_candidates: Direct test file names to search
        - changed_functions: Function-level changes
        - deleted_symbols: Symbols only in removed diff lines (for diff-impact)
        - added_symbols: Symbols only in added diff lines (for coverage gaps)
        - renamed_symbols: List of {"old": str, "new": str} (for breakage labels)
    """
    exact_matches = []
    module_matches = []
    file_patterns = []
    test_file_candidates = []
    # Separately track module names that were put into exact_matches.
    # This is passed to find_tests_ast_only so that Strategy 4a can
    # distinguish "matched via module name" from "matched via specific symbol".
    # Module-name matches must NOT trigger same-file expansion — they're
    # too broad and would pull in unrelated co-located tests.
    module_exact_matches: list = []
    
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
        
        # Check if this file only changed TypeScript/JS constants/symbols
        # (uppercase symbols in changed_classes, no method changes).
        # In this case, the generic module names (e.g. "constants", "types.constants")
        # are too broad — they map to EVERY test that imports that file, not just the
        # tests relevant to the specific changed symbol (e.g. PHONE_REGEX).
        # So we SKIP the generic module names from exact_matches and put them in
        # module_matches (lower priority fallback) instead.
        specific_symbols = [
            c for c in file_change.get('changed_classes', [])
            if c and c[0].isupper() and c.upper() == c  # UPPER_CASE constants only
        ]
        has_method_changes = bool(file_change.get('changed_methods'))
        use_symbol_only = bool(specific_symbols) and not has_method_changes

        # Single-word directory names that appear as the "parent part" of a
        # dotted module (e.g. 'reducer' from 'reducer.paymentReducer').
        # Searching by these alone matches EVERY test that imports from ANY
        # file in that directory — e.g. 'reducer' matches toastReducer,
        # favouritesReducer, paymentReducer all at once via LIKE 'reducer.%',
        # causing wide false positives when only ONE reducer file changed.
        #
        # These names are COMPLETELY EXCLUDED from all match lists.
        # The specific dotted form (e.g. 'reducer.paymentReducer') and the file
        # stem ('paymentReducer') are still added normally as exact_matches, so
        # the reverse_index IS queried — just with the precise module name.
        # Semantic search provides the safety net for barrel-import tests.
        _GENERIC_DIRS = {
            'reducer', 'reducers', 'actions', 'action',
            'store', 'stores', 'state',
            'service', 'services',
            'hooks', 'hook',
            'context', 'contexts',
            'middleware', 'middlewares',
            'saga', 'sagas', 'epic', 'epics',
            'selectors', 'selector',
            'components', 'containers',
            'controllers', 'models',
            'routes', 'views', 'pages',
        }

        for module_name in modules:
            # Completely skip bare generic directory names — too broad for any query.
            if module_name in _GENERIC_DIRS:
                continue

            if use_symbol_only:
                # Demote file/module names to module_matches (broad fallback).
                # The specific symbols added below will be the primary exact_matches.
                if module_name not in module_matches:
                    module_matches.append(module_name)
            else:
                # Normal case: add module name as an exact match AND track it
                # separately so Strategy 4a can identify it as a module-level match.
                exact_matches.append(module_name)
                if module_name not in module_exact_matches:
                    module_exact_matches.append(module_name)

            # Module-level wildcard pattern (if dotted) — only when the root part
            # is NOT a generic directory name.
            if '.' in module_name:
                module_part = module_name.split('.')[0]
                if module_part not in _GENERIC_DIRS:
                    module_pattern = f"{module_part}.*"
                    if module_pattern not in module_matches:
                        module_matches.append(module_pattern)
        
        # Add any changed classes/symbols as exact matches.
        # This covers TypeScript/JS `export const PHONE_REGEX = ...` which is
        # parsed as a "changed class" by extract_definitions() in parse_git_diff().
        # Adding them here lets the reverse_index be queried by specific symbol name
        # (e.g. PHONE_REGEX → test_0061/62/63) instead of only by the generic
        # file module name (e.g. constants → all tests importing that file).
        for class_name in file_change.get('changed_classes', []):
            if class_name and class_name not in exact_matches:
                exact_matches.append(class_name)

        # Also add changed function/method names to exact_matches.
        # This enables the reverse_index to be queried by function name, which is
        # used for describe_label entries. For example, if `capitalizeFirstLetter`
        # is in changed_methods (from hunk header or +/- line), and the reverse_index
        # has entries like (capitalizeFirstLetter, test_0012, describe_label), then
        # the "Exact matches" strategy will find those tests.
        # Without this, function-level matching only checks test_function_mapping
        # (which has 0 entries for JS), missing the reverse_index describe_labels.
        for method_name in file_change.get('changed_methods', []):
            if method_name and method_name not in exact_matches:
                exact_matches.append(method_name)

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
    
    # Deleted/added/renamed symbols from diff lines (for AST and diff-impact)
    deleted_symbols: List[str] = []
    added_symbols: List[str] = []
    renamed_symbols: List[Dict[str, str]] = []
    if diff_content:
        delta = extract_deleted_added_renamed_symbols(diff_content)
        deleted_symbols = delta.get('deleted_symbols', [])
        added_symbols = delta.get('added_symbols', [])
        renamed_symbols = delta.get('renamed_symbols', [])
        for sym in deleted_symbols:
            if sym and sym not in exact_matches:
                exact_matches.append(sym)
    
    return {
        'exact_matches': list(set(exact_matches)),
        'module_matches': list(set(module_matches)),
        'module_exact_matches': list(set(module_exact_matches)),  # module-only names in exact_matches
        'file_patterns': list(set(file_patterns)),
        'test_file_candidates': list(set(test_file_candidates)),
        'changed_functions': changed_functions,  # Function-level changes
        'deleted_symbols': deleted_symbols,
        'added_symbols': added_symbols,
        'renamed_symbols': renamed_symbols,
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
