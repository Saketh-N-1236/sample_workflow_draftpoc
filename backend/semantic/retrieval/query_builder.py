"""
Query builder for semantic retrieval.

Builds rich, contextual descriptions of code changes for semantic search.
"""

import re
from typing import List, Dict, Optional, Any
from pathlib import Path


def build_rich_change_description(
    changed_functions: list,
    file_changes: Optional[List[Dict]] = None,
    diff_content: Optional[str] = None
) -> str:
    """
    Build a rich, contextual description of code changes for semantic search.
    
    Includes:
    - File paths and class context
    - Related functions in the same file
    - Module-level context
    - Change type (new file, modified, etc.)
    - Changed constant/variable names (extracted from diff when no functions)
    
    Args:
        changed_functions: List of {'module': str, 'function': str}
        file_changes: Optional list of file change dictionaries from parse_git_diff
        diff_content: Optional raw git diff text for richer symbol extraction
    
    Returns:
        Rich description string for embedding
    """
    if not changed_functions:
        # Fallback: build a file-level query when no functions were detected.
        # This handles constants/config/data files (e.g. ApiEndPoints.js, config.json)
        # that contain no function definitions, so the diff parser extracts 0 functions.
        # Without this fallback, Pinecone would receive an empty query and return 0 results.
        if file_changes or diff_content:
            parts = []

            # ── Per-file context ───────────────────────────────────────────────
            for fc in (file_changes or [])[:3]:
                file_path = fc.get('file', '')
                if not file_path:
                    continue
                fp = Path(file_path)
                file_stem = fp.stem              # e.g. "constants"
                parent_name = fp.parent.name       # e.g. "types"
                parts.append(f"Changed file: {file_stem}")
                if parent_name and parent_name not in ('.', ''):
                    parts.append(f"In: {parent_name}")
                # include any changed classes/methods if parser did find some
                changed_classes = fc.get('changed_classes', [])
                if changed_classes:
                    parts.append(f"Classes: {', '.join(changed_classes)}")
                changed_methods = fc.get('changed_methods', [])
                if changed_methods:
                    parts.append(f"Methods: {', '.join(changed_methods)}")

            # ── Extract symbol names from diff +lines ──────────────────────────
            # For constants/config files, the changed lines contain declarations
            # like:  +export const PHONE_REGEX = /^(\+?[1-9]\d{9,13})$/;
            # We extract the identifier names (ALL_CAPS, camelCase, PascalCase)
            # to build a query rich enough for semantic matching.
            if diff_content:
                symbol_pattern = re.compile(
                    r'^\+(?!#|//).*?\b'          # added line, not a comment
                    r'(?:const|let|var|export\s+const|export\s+default)\s+'
                    r'([A-Za-z_][A-Za-z0-9_]*)',  # identifier
                    re.MULTILINE
                )
                # Also catch TypeScript enums / interface / type aliases
                ts_pattern = re.compile(
                    r'^\+.*?\b(?:enum|interface|type)\s+([A-Za-z_][A-Za-z0-9_]*)',
                    re.MULTILINE
                )
                symbols = []
                for m in symbol_pattern.finditer(diff_content):
                    name = m.group(1)
                    if name not in symbols:
                        symbols.append(name)
                for m in ts_pattern.finditer(diff_content):
                    name = m.group(1)
                    if name not in symbols:
                        symbols.append(name)
                if symbols:
                    parts.append(f"Changed symbols: {', '.join(symbols[:10])}")

            return ". ".join(parts) + "." if parts else ""
        return ""

    # Group functions by module
    by_module = {}
    for cf in changed_functions:
        module = cf.get('module', '')
        func = cf.get('function', '')
        if module not in by_module:
            by_module[module] = []
        by_module[module].append(func)
    
    # Build rich description
    parts = []
    
    # Add module-level context
    if len(by_module) == 1:
        module = list(by_module.keys())[0]
        functions = by_module[module]
        parts.append(f"Changed in module: {module}")
        parts.append(f"Changed functions: {', '.join(f'{f}()' for f in functions)}")
        
        # Try to extract file path and class from module
        if file_changes:
            for file_change in file_changes:
                file_path = file_change.get('file', '')
                if file_path.endswith('.py'):
                    # Try to match module to file
                    module_path = module.replace('.', '/') + '.py'
                    if module_path in file_path or file_path.endswith(module_path):
                        parts.append(f"File: {file_path}")
                        
                        # Extract class names from changed classes
                        changed_classes = file_change.get('changed_classes', [])
                        if changed_classes:
                            parts.append(f"Classes: {', '.join(changed_classes)}")
                        
                        # Add change status
                        status = file_change.get('status', 'modified')
                        if status == 'added':
                            parts.append("Status: New file")
                        break
    else:
        # Multiple modules
        parts.append("Changed across multiple modules:")
        for module, functions in by_module.items():
            parts.append(f"  - {module}: {', '.join(f'{f}()' for f in functions)}")
    
    # Add related context
    if len(changed_functions) > 1:
        parts.append(f"Total functions changed: {len(changed_functions)}")
    
    return ". ".join(parts) + "."


def build_diff_anchor_text(
    diff_content: str,
    file_hints: Optional[str] = None,
    max_chars: int = 12000,
) -> str:
    """
    When LLM summary fails validation, use truncated raw diff as canonical query text
    (before single symbol enrichment). Optionally append a short line from rich description.
    """
    d = (diff_content or "").strip()
    if not d:
        return ""
    if len(d) > max_chars:
        head = max_chars // 2
        tail = max_chars - head
        d = d[:head] + "\n\n... [diff truncated] ...\n\n" + d[-tail:]
    parts = ["Code change (git diff):\n", d]
    hint = (file_hints or "").strip()
    if hint:
        parts.append("\n\nContext: " + hint[:2000])
    return "".join(parts)


def enrich_semantic_query_with_diff_symbols(
    base_query: str,
    deleted_symbols: Optional[List[str]] = None,
    added_symbols: Optional[List[str]] = None,
    renamed_symbols: Optional[List[Dict[str, Any]]] = None,
    max_items: int = 35,
) -> str:
    """
    Append explicit deleted/added/renamed symbol lists to the semantic search query.

    LLM diff summaries often omit removed identifiers; AST already uses deleted_symbols.
    This keeps vector search aligned so tests referencing removed names are easier to retrieve.
    """
    if not base_query or not base_query.strip():
        base_query = ""
    parts = []
    d = [s for s in (deleted_symbols or []) if s][:max_items]
    if d:
        parts.append(
            "Removed or deleted symbols (tests may still reference these): "
            + ", ".join(d)
        )
    a = [s for s in (added_symbols or []) if s][:max_items]
    if a:
        parts.append("Newly added symbols: " + ", ".join(a))
    rbits = []
    for r in (renamed_symbols or [])[:max_items]:
        if not isinstance(r, dict):
            continue
        o, n = r.get("old"), r.get("new")
        if o and n:
            rbits.append(f"{o} -> {n}")
    if rbits:
        parts.append("Renamed symbols: " + ", ".join(rbits))
    if not parts:
        return base_query
    suffix = " ".join(parts)
    return f"{base_query.rstrip()}\n\n[Diff symbols] {suffix}"
