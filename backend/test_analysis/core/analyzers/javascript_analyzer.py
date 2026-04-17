"""
JavaScript/TypeScript test analyzer.

Analyzes JavaScript/TypeScript test repositories.

analyze() now returns BOTH:
  - AnalyzerResult  (backward-compatible, kept for callers that still use it)
  - a LanguageResult stored on self.language_result after each analyze() call

Set the env var DEBUG_WRITE_JSON=true to also write the legacy 8 JSON files.
"""

from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
import json
import os
import re
import logging
from datetime import datetime

from .base_analyzer import BaseAnalyzer, AnalyzerResult

# Import existing utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from test_analysis.utils.universal_parser import UniversalTestParser
from test_analysis.utils.dependency_plugins import get_registry
from test_analysis.engine.models import LanguageResult, TestRecord

logger = logging.getLogger(__name__)

# JS/TS test file patterns
JS_TEST_PATTERNS = [
    re.compile(r'.*\.test\.(js|ts|jsx|tsx)$'),
    re.compile(r'.*\.spec\.(js|ts|jsx|tsx)$'),
    re.compile(r'.*test.*\.(js|ts|jsx|tsx)$'),
]

EXCLUDE_DIRS = {'node_modules', '.git', '.idea', '.vscode', 'dist', 'build', '.next', '.nuxt'}


class JavaScriptAnalyzer(BaseAnalyzer):
    """JavaScript/TypeScript test analyzer implementation."""
    
    def __init__(self):
        super().__init__(
            language='javascript',
            supported_frameworks=['jest', 'mocha', 'jasmine', 'vitest']
        )
        self.parser = UniversalTestParser()
        self.dependency_plugin = get_registry().get_plugin('javascript')
        # Populated by analyze() — callers can read this directly
        self.language_result: Optional[LanguageResult] = None
    
    def analyze(
        self,
        repo_path: Path,
        output_dir: Path,
        test_files: List[Path] = None,
    ) -> AnalyzerResult:
        """
        Analyze JavaScript/TypeScript repository.

        Always populates self.language_result with a LanguageResult.
        Writes JSON files to disk only when DEBUG_WRITE_JSON=true.
        Returns AnalyzerResult for backward compatibility.

        Args:
            repo_path:  Root of the test repository.
            output_dir: Directory for optional JSON debug output.
            test_files: Pre-scanned list of test files.  When supplied the
                        internal file-scan step is skipped (avoids path-
                        encoding or permission issues on some platforms).
        """
        self._ensure_output_dir(output_dir)
        self._log_progress("Starting JavaScript/TypeScript analysis")
        
        errors = []
        repo_path = Path(repo_path).resolve()
        
        # Step 1: Scan test files (skip if caller already provided the list)
        self._log_progress("Scanning test files...")
        if test_files is None:
            test_files = self._scan_test_files(repo_path)
        if not test_files:
            errors.append("No JavaScript/TypeScript test files found")
            return AnalyzerResult(
                language='javascript',
                framework='unknown',
                output_dir=output_dir,
                errors=errors
            )
        
        # Step 2: Detect framework
        self._log_progress("Detecting framework...")
        framework, confidence = self._detect_framework(test_files)
        
        # Step 3: Extract tests
        self._log_progress("Extracting tests...")
        tests, test_id_counter = self._extract_tests(test_files, repo_path, framework)
        
        # Step 4: Extract dependencies
        self._log_progress("Extracting dependencies...")
        dependencies = self._extract_dependencies(test_files, tests, repo_path)
        
        # Step 5: Extract function calls
        self._log_progress("Extracting function calls...")
        function_calls = self._extract_function_calls(test_files, tests, repo_path)
        
        # Step 6: Extract metadata
        self._log_progress("Extracting metadata...")
        metadata = self._extract_metadata(tests, test_files, repo_path)
        
        # Step 7: Build reverse index
        self._log_progress("Building reverse index...")
        reverse_index = self._build_reverse_index(dependencies, function_calls)
        
        # Step 8: Map test structure
        self._log_progress("Mapping test structure...")
        structure = self._map_test_structure(test_files, tests, repo_path)
        
        # Step 9: Extract JavaScript-specific data
        self._log_progress("Extracting mocks...")
        mocks = self._extract_mocks(test_files, tests, repo_path)
        
        self._log_progress("Extracting async tests...")
        async_tests = self._extract_async_tests(tests, test_files, repo_path)
        
        # ── Build LanguageResult (in-memory, no disk I/O) ─────────────────
        test_records: List[TestRecord] = []
        for t in tests:
            desc_label = t.get('class_name') or ''
            it_label = t.get('method_name', '')
            full_name = it_label  # already "describe > it" from _extract_tests
            tr = TestRecord(
                id=t['test_id'],
                file=t['file_path'],
                describe=desc_label,
                name=it_label.split(' > ')[-1] if ' > ' in it_label else it_label,
                full_name=full_name,
                test_type=t.get('test_type', 'unit'),
                language='javascript',
                framework=framework,
                line_number=t.get('line_number'),
                repository_path=t.get('repository_path', str(repo_path)),
            )
            test_records.append(tr)

        # Attach test body content from metadata (same order as tests)
        for i, tr in enumerate(test_records):
            if i < len(metadata):
                tr.content = metadata[i].get('description', '') or ''

        self.language_result = LanguageResult(
            language='javascript',
            framework=framework,
            tests=test_records,
            reverse_index=reverse_index,
            function_mappings=function_calls,
            dependencies=dependencies,
            metadata=metadata,
            mocks=mocks or [],
            async_tests=async_tests or [],
            files_analyzed=len(test_files),
            errors=errors,
        )
        # ──────────────────────────────────────────────────────────────────

        # Write JSON files only when explicitly requested (debug mode)
        if os.environ.get('DEBUG_WRITE_JSON', '').lower() in ('1', 'true', 'yes'):
            self._write_outputs(
                output_dir, test_files, framework, confidence,
                tests, dependencies, function_calls, metadata,
                reverse_index, structure, repo_path,
                mocks, async_tests
            )
        
        # Generate summary
        summary = self._generate_summary(
            test_files, tests, dependencies, reverse_index,
            metadata, framework, confidence
        )
        
        self._log_progress(f"Analysis complete: {len(tests)} tests found")
        
        return AnalyzerResult(
            language='javascript',
            framework=framework,
            output_dir=output_dir,
            summary=summary,
            files_analyzed=len(test_files),
            tests_found=len(tests),
            errors=errors
        )
    
    def _scan_test_files(self, repo_path: Path) -> List[Path]:
        """Scan for JavaScript/TypeScript test files."""
        test_files = []
        for filepath in repo_path.rglob('*'):
            if not filepath.is_file():
                continue
            if any(excluded in filepath.parts for excluded in EXCLUDE_DIRS):
                continue
            if filepath.suffix.lower() in ['.js', '.ts', '.jsx', '.tsx']:
                if any(pattern.match(filepath.name) for pattern in JS_TEST_PATTERNS):
                    test_files.append(filepath)
        return sorted(test_files)
    
    def _detect_framework(self, test_files: List[Path]) -> tuple:
        """Detect test framework from imports."""
        votes = defaultdict(int)
        sample_size = min(50, len(test_files))
        
        for filepath in test_files[:sample_size]:
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                # Check for Jest
                if re.search(r"import.*from\s+['\"]jest['\"]|require\s*\(\s*['\"]jest['\"]|describe\(|it\(|expect\(", content):
                    votes['jest'] += 2
                
                # Check for Mocha
                if re.search(r"import.*from\s+['\"]mocha['\"]|require\s*\(\s*['\"]mocha['\"]|describe\(", content):
                    votes['mocha'] += 2
                
                # Check for Jasmine
                if re.search(r"import.*from\s+['\"]jasmine['\"]|require\s*\(\s*['\"]jasmine['\"]", content):
                    votes['jasmine'] += 1
                
                # Check for Vitest
                if re.search(r"import.*from\s+['\"]vitest['\"]|require\s*\(\s*['\"]vitest['\"]", content):
                    votes['vitest'] += 2
            except Exception as e:
                logger.debug(f"Error reading {filepath}: {e}")
        
        if votes:
            framework = max(votes, key=votes.get)
            confidence = 'high' if votes[framework] >= 10 else 'medium' if votes[framework] >= 5 else 'low'
            return framework, confidence
        return 'jest', 'low'
    
    def _extract_tests(self, test_files: List[Path], repo_path: Path, framework: str) -> tuple:
        """Extract test methods from files."""
        tests = []
        test_id_counter = 1
        
        for filepath in test_files:
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                test_type = self._get_test_type(filepath)
                
                # Extract individual test cases only (it/test).
                # 'describe' is a GROUP container, not a test — excluded intentionally.
                #
                # Pattern explanation:
                #   (?<!\w)          — word-boundary: prevents matching .test() inside class names
                #   (?:it|test)      — only real Jest test blocks (NOT describe)
                #   \s*\(            — opening paren (optional whitespace)
                #   (?:QUOTE_EXPR)   — the test-name argument as a proper quoted string literal
                #                      (single / double / backtick).
                #                      We use [^QUOTE\n\\]* instead of [^,]* so the pattern
                #                      CANNOT span newlines into a later it()/describe() line.
                #   \s*,\s*          — comma separating name from callback
                #   (?:async\s*)?    — optional async keyword
                #   (?:\([^)]*\)\s*)?=> — arrow function signature: () => or (args) =>
                test_pattern = re.compile(
                    r"""(?<!\w)(?:it|test)\s*\(\s*(?:'[^'\n\\]*'|"[^"\n\\]*"|`[^`\n\\]*`)\s*,\s*(?:async\s*)?(?:\([^)]*\)\s*)?=>""",
                    re.MULTILINE
                )

                # ── Pre-scan: build sorted list of (char_position, describe_name) ──
                # We use this to look up the closest enclosing describe() for each it().
                # Format: "describe_name > it_name"  makes every test uniquely identifiable
                # and is also the key that maps test_id → production symbol in AST matching.
                _desc_pattern = re.compile(
                    r"""(?<!\w)describe\s*\(\s*(?:'([^'\n\\]*)'|"([^"\n\\]*)"|`([^`\n\\]*)`)\s*,""",
                    re.MULTILINE
                )
                describe_positions = []   # [(start_pos, describe_name), ...]
                for dm in _desc_pattern.finditer(content):
                    desc_name = dm.group(1) or dm.group(2) or dm.group(3) or ''
                    describe_positions.append((dm.start(), desc_name))
                # Sort by position (should already be, but be safe)
                describe_positions.sort(key=lambda x: x[0])

                _name_re = re.compile(r"""(?:it|test)\s*\(\s*['"`]([^'"`\n]+)['"`]""")

                for match in test_pattern.finditer(content):
                    before = content[:match.start()]
                    line_num = before.count('\n') + 1

                    # ── Extract name ONLY from the current it()/test() call ──────────
                    matched_text = match.group(0)
                    name_match = _name_re.search(matched_text)
                    if name_match:
                        it_name = name_match.group(1)
                    else:
                        forward_text = content[match.start():min(len(content), match.start() + 300)]
                        fwd_match = _name_re.search(forward_text)
                        it_name = fwd_match.group(1) if fwd_match else f"test_{test_id_counter}"

                    # ── Attach enclosing describe() label ──────────────────────────
                    # Walk the sorted describe_positions in reverse; the LAST describe
                    # whose start position is before this it() start is the closest one.
                    enclosing_describe = ''
                    for dpos, dname in reversed(describe_positions):
                        if dpos < match.start():
                            enclosing_describe = dname
                            break

                    # Final test name: "describe_name > it_name" (or just it_name if no describe)
                    if enclosing_describe:
                        test_name = f"{enclosing_describe} > {it_name}"
                    else:
                        test_name = it_name
                    # ────────────────────────────────────────────────────────────────

                    test_id_str = f"test_{test_id_counter:04d}"
                    test_id_counter += 1

                    tests.append({
                        'test_id': test_id_str,
                        'file_path': str(filepath),
                        'class_name': enclosing_describe or None,   # describe block = class
                        'method_name': test_name,
                        'test_type': test_type,
                        'language': 'javascript',
                        'repository_path': str(repo_path),
                        'line_number': line_num,
                        'framework': framework,
                    })
            except Exception as e:
                logger.warning(f"Error extracting tests from {filepath}: {e}")
        
        return tests, test_id_counter
    
    def _get_test_type(self, filepath: Path) -> str:
        """Get test type from file path."""
        path_str = str(filepath).lower()
        if 'integration' in path_str:
            return 'integration'
        elif 'e2e' in path_str or 'end.to.end' in path_str:
            return 'e2e'
        return 'unit'
    
    # ── Import-chain traversal helpers ────────────────────────────────────
    _IMPORT_RE = re.compile(
        r"""(?:import|require)\s*(?:\([^)]*\))?\s*\(?['"`](\.{1,2}/[^'"`\s]+)['"`]""",
        re.MULTILINE,
    )

    # Matches JSDoc @source annotations that explicitly declare which production
    # file a test covers — used when the test inlines rather than imports source.
    # Examples handled:
    #   @source src/services/api/common/ApiEndPoints.js
    #   * @sources src/foo.js, src/bar.ts
    #   @source  ./components/MyComp.jsx
    _SOURCE_ANNOTATION_RE = re.compile(
        r"@sources?\s+([\w./,\s\-]+)",
        re.IGNORECASE,
    )
    _JS_EXTS = ('.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs')
    _EXCLUDE_CHAIN = frozenset(
        ['node_modules', '.git', 'dist', 'build', '.next', '.nuxt', '__pycache__']
    )

    def _resolve_import(self, source: Path, raw: str, repo_path: Path) -> Optional[str]:
        """
        Resolve a relative import string (starts with ./ or ../) to an absolute
        path string that exists on disk, staying within repo_path.
        Returns None if unresolvable.
        """
        try:
            base = (source.parent / raw).resolve()
            candidates = (
                [base]
                + [base.with_suffix(ext) for ext in self._JS_EXTS]
                + [base / f"index{ext}" for ext in self._JS_EXTS]
            )
            for c in candidates:
                if c.is_file():
                    c.relative_to(repo_path)   # raises ValueError if outside repo
                    return str(c)
        except Exception:
            pass
        return None

    def _build_production_import_graph(
        self, repo_path: Path
    ) -> Dict[str, Set[str]]:
        """
        Walk every JS/TS file in the repo (excluding test files and node_modules)
        and build a map:  resolved_path → {resolved_paths it imports}.

        Only relative imports are followed because those are the only ones
        resolvable without running the Node module resolver.
        """
        graph: Dict[str, Set[str]] = {}
        for fp in repo_path.rglob('*'):
            if not fp.is_file():
                continue
            if any(ex in fp.parts for ex in self._EXCLUDE_CHAIN):
                continue
            if fp.suffix.lower() not in self._JS_EXTS:
                continue
            try:
                content = fp.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            key = str(fp.resolve())
            graph.setdefault(key, set())
            for m in self._IMPORT_RE.finditer(content):
                resolved = self._resolve_import(fp, m.group(1), repo_path)
                if resolved:
                    graph[key].add(resolved)
        return graph

    def _transitive_imports(
        self,
        direct_abs: List[str],
        graph: Dict[str, Set[str]],
        max_depth: int = 3,
    ) -> Set[str]:
        """
        BFS from direct_abs through the production import graph.
        Returns every reachable file within max_depth hops (including direct_abs).
        """
        visited: Set[str] = set(direct_abs)
        frontier: Set[str] = set(direct_abs)
        for _ in range(max_depth):
            nxt: Set[str] = set()
            for node in frontier:
                for neighbor in graph.get(node, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        nxt.add(neighbor)
            frontier = nxt
            if not frontier:
                break
        return visited

    # ──────────────────────────────────────────────────────────────────────

    def _extract_dependencies(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """
        Extract direct AND transitive import dependencies for every test.

        Direct imports  → reference_type 'direct_import'
        Transitive hops → reference_type 'transitive_import'

        Both are stored in referenced_classes / reference_types and end up
        in the reverse_index so that AST selection can find tests even when
        the changed production file is 2–3 hops away from the test file.
        """
        # ── Build the whole-repo import graph (cached per analyze() call) ──
        if not hasattr(self, '_import_graph_cache'):
            self._import_graph_cache = None
            self._import_graph_repo = None

        if self._import_graph_repo != str(repo_path):
            logger.info("[JS] Building production import graph for %s", repo_path)
            self._import_graph_cache = self._build_production_import_graph(repo_path)
            self._import_graph_repo = str(repo_path)
            logger.info(
                "[JS] Import graph: %d files indexed", len(self._import_graph_cache)
            )

        import_graph = self._import_graph_cache

        dependencies = []
        # Build file → list-of-tests mapping (one file can have many tests)
        tests_by_file: Dict[str, List[Dict]] = {}
        for t in tests:
            tests_by_file.setdefault(t['file_path'], []).append(t)

        import_pattern = re.compile(
            r"(?:import|require)\s*(?:\([^)]*\))?\s*\(?['\"`]([@\w./\-]+)['\"`]",
            re.MULTILINE,
        )
        _FW_SKIP = frozenset(
            ['jest', 'mocha', 'jasmine', 'vitest', 'chai', 'sinon', 'enzyme',
             'testing-library', 'react-dom/test-utils']
        )

        for filepath in test_files:
            file_tests = tests_by_file.get(str(filepath))
            if not file_tests:
                continue

            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')

                # ── Direct imports ─────────────────────────────────────────
                raw_imports: List[str] = []
                for match in import_pattern.finditer(content):
                    imp = match.group(1)
                    if not any(fw in imp.lower() for fw in _FW_SKIP):
                        raw_imports.append(imp)
                direct_imports = sorted(set(raw_imports))

                # ── Resolve relative imports to absolute paths ─────────────
                direct_abs: List[str] = []
                for imp in direct_imports:
                    if imp.startswith(('.', '/')):
                        resolved = self._resolve_import(filepath, imp, repo_path)
                        if resolved:
                            direct_abs.append(resolved)

                # ── Transitive expansion (BFS, max 3 hops) ────────────────
                transitive_abs = self._transitive_imports(direct_abs, import_graph, max_depth=3)
                # Only the hops beyond direct
                indirect_abs = transitive_abs - set(direct_abs)

                # Convert absolute paths back to repo-relative stems for the
                # reverse_index key (same format as direct imports use).
                def _to_rel(abs_path: str) -> str:
                    try:
                        rel = Path(abs_path).relative_to(repo_path)
                        return str(rel).replace('\\', '/')
                    except ValueError:
                        return abs_path

                indirect_imports = sorted(_to_rel(p) for p in indirect_abs)

                # ── Merge into reference_types dict ───────────────────────
                reference_types: Dict[str, str] = {
                    imp: 'direct_import' for imp in direct_imports
                }
                for imp in indirect_imports:
                    if imp not in reference_types:
                        reference_types[imp] = 'transitive_import'

                all_imports = sorted(set(direct_imports) | set(indirect_imports))

                # ── @source JSDoc annotations ─────────────────────────────
                # Some test files INLINE production code instead of importing
                # it (e.g. api-navigation.feature.test.js copies ApiEndPoints).
                # The @source annotation explicitly declares the covered file:
                #   @source src/services/api/common/ApiEndPoints.js
                # We add these as 'source_annotation' references so the
                # reverse_index can find the test when that file changes.
                source_annotated: List[str] = []
                for m in self._SOURCE_ANNOTATION_RE.finditer(content):
                    raw_sources = m.group(1)
                    for raw_src in re.split(r'[,\s]+', raw_sources.strip()):
                        raw_src = raw_src.strip().rstrip(',')
                        if raw_src and not raw_src.startswith('//'):
                            source_annotated.append(raw_src)

                # Merge source annotations into reference_types dict
                for src in source_annotated:
                    if src not in reference_types:
                        reference_types[src] = 'source_annotation'
                        if src not in all_imports:
                            all_imports = sorted(set(all_imports) | {src})

                if source_annotated:
                    logger.debug(
                        "[JS] %s: %d @source annotation(s): %s",
                        filepath.name, len(source_annotated), source_annotated,
                    )

                if indirect_imports:
                    logger.debug(
                        "[JS] %s: %d direct + %d transitive import(s)",
                        filepath.name, len(direct_imports), len(indirect_imports),
                    )

                # Create one dependency entry per test in this file
                for test in file_tests:
                    dependencies.append({
                        'test_id': test['test_id'],
                        'file_path': str(filepath),
                        'class_name': test.get('class_name', ''),
                        'method_name': test['method_name'],
                        'referenced_classes': all_imports,
                        'reference_types': reference_types,
                        'import_count': len(direct_imports),
                        'transitive_count': len(indirect_imports),
                    })
            except Exception as e:
                logger.warning(f"Error extracting dependencies from {filepath}: {e}")

        return dependencies
    
    def _extract_function_calls(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract function calls per individual test.
        
        FIX: The old code used file→single-test dict so every method call in the
        file got attributed to only ONE test (the last one stored in the dict).
        
        New approach:
          1. Build a sorted list of (line_number, test) pairs per file.
          2. For each method-call match, determine which test body it belongs to
             by finding the nearest test that starts at or before that line.
          3. Emit one function_calls entry per (symbol, test) pair — deduplicated
             so the same symbol doesn't appear twice for the same test.
        """
        function_calls = []
        # Build file → sorted list of tests (by line_number ascending)
        tests_by_file: Dict[str, List[Dict]] = {}
        for t in tests:
            tests_by_file.setdefault(t['file_path'], []).append(t)
        # Sort each file's tests by line number
        for fp in tests_by_file:
            tests_by_file[fp].sort(key=lambda t: t.get('line_number') or 0)

        SKIP_OBJECTS = {'expect', 'describe', 'it', 'test', 'jest', 'mock',
                        'beforeeach', 'aftereach', 'beforeall', 'afterall',
                        'console', 'math', 'json', 'object', 'array', 'promise'}

        for filepath in test_files:
            file_tests = tests_by_file.get(str(filepath))
            if not file_tests:
                continue

            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                lines = content.split('\n')
                total_lines = len(lines)
                pattern = re.compile(r'(\w+)\.(\w+)\s*\(', re.MULTILINE)

                # seen set: avoid duplicate (test_id, module_name) rows
                seen: set = set()

                for match in pattern.finditer(content):
                    obj  = match.group(1)
                    func = match.group(2)
                    if obj.lower() in SKIP_OBJECTS:
                        continue

                    call_line = content[:match.start()].count('\n') + 1

                    # Find which test owns this line (last test whose line_number ≤ call_line)
                    owner_test = file_tests[0]  # fallback: first test
                    for t in file_tests:
                        t_line = t.get('line_number') or 0
                        if t_line <= call_line:
                            owner_test = t
                        else:
                            break  # list is sorted ascending; no need to continue

                    key = (owner_test['test_id'], obj)
                    if key in seen:
                        continue
                    seen.add(key)

                    function_calls.append({
                        'test_id':      owner_test['test_id'],
                        'file_path':    str(filepath),
                        'class_name':   owner_test.get('class_name', ''),
                        'method_name':  owner_test['method_name'],
                        'module_name':  obj,
                        'function_name': func,
                        'object_name':  obj,
                        'call_type':    'method',
                        'source':       'method_call',
                        'line_number':  call_line,
                    })
            except Exception as e:
                logger.warning(f"Error extracting function calls from {filepath}: {e}")

        return function_calls
    
    def _extract_test_content(self, filepath: Path, method_name: str, line_number: Optional[int]) -> str:
        """
        Extract test function body content from JavaScript/TypeScript source file.
        
        Returns full test function body including:
        - Setup code
        - Function calls
        - Assertions
        - Teardown code
        """
        if not filepath.exists():
            return ''
        
        try:
            content = filepath.read_text(encoding='utf-8', errors='replace')
            lines = content.split('\n')
            
            # If we have a line number, try line-based extraction first (more reliable)
            if line_number and line_number > 0 and line_number <= len(lines):
                # Get the line content at the specified line number
                line_content = lines[line_number - 1]
                # Check if this line contains test/it
                if 'test(' in line_content.lower() or 'it(' in line_content.lower():
                    # Extract test name from this line
                    test_name_match = re.search(r"(?:test|it)\s*\(\s*['\"`]([^'\"`]+)['\"`]", line_content)
                    if test_name_match:
                        extracted_name = test_name_match.group(1)
                        # If extracted name matches method_name (or is close), use line-based extraction
                        if extracted_name == method_name or method_name in extracted_name or extracted_name in method_name:
                            # Use line-based extraction
                            start_line_idx = line_number - 1
                            # Find the opening brace or arrow function starting from this line
                            start_pos = len('\n'.join(lines[:start_line_idx]))
                            if start_line_idx > 0:
                                start_pos += 1
                            
                            # Find the function body start
                            brace_count = 0
                            found_start = False
                            end_pos = start_pos
                            
                            for i in range(start_line_idx, min(start_line_idx + 30, len(lines))):
                                line_text = lines[i]
                                for char in line_text:
                                    if char == '{':
                                        if not found_start:
                                            found_start = True
                                        brace_count += 1
                                    elif char == '}':
                                        brace_count -= 1
                                        if found_start and brace_count == 0:
                                            end_pos = len('\n'.join(lines[:i+1]))
                                            if i > 0:
                                                end_pos += 1
                                            test_content = content[start_pos:end_pos]
                                            logger.debug(f"[javascript] Extracted {len(test_content)} chars using line-based extraction for '{method_name}'")
                                            return test_content
                            
                            # If we found start but not end, extract to end of file (shouldn't happen, but fallback)
                            if found_start:
                                test_content = content[start_pos:]
                                logger.debug(f"[javascript] Extracted {len(test_content)} chars (to EOF) using line-based extraction for '{method_name}'")
                                return test_content
            
            # Fallback to pattern-based search
            # If we have a line number, use it to narrow the search
            search_start = 0
            search_end = len(content)
            if line_number:
                # Search around the line number (±50 lines)
                start_line = max(0, line_number - 50)
                end_line = min(len(lines), line_number + 50)
                search_start = len('\n'.join(lines[:start_line]))
                if start_line > 0:
                    search_start += 1  # Account for newline
                search_end = len('\n'.join(lines[:end_line]))
                if end_line > 0:
                    search_end += 1  # Account for newline
                search_content = content[search_start:search_end]
            else:
                search_content = content
            
            # Escape method_name for regex, but handle special characters
            # The method_name might contain spaces, parentheses, etc.
            escaped_name = re.escape(method_name)
            
            # Pattern to match test functions: test('name', ...) or it('name', ...)
            # Handle both single and double quotes, and allow for spaces/special chars in name
            # Also handle template literals: test(`name`, ...)
            test_patterns = [
                # Exact match: test('method_name', ...) or it('method_name', ...)
                rf"(?:test|it)\s*\(\s*['\"]{escaped_name}['\"]",
                # Template literal: test(`method_name`, ...)
                rf"(?:test|it)\s*\(\s*`{escaped_name}`",
                # Partial match: test('...method_name...', ...) - in case name has extra context
                rf"(?:test|it)\s*\(\s*['\"][^'\"]*{escaped_name}[^'\"]*['\"]",
                # Template literal partial: test(`...method_name...`, ...)
                rf"(?:test|it)\s*\(\s*`[^`]*{escaped_name}[^`]*`",
            ]
            
            for pattern in test_patterns:
                match = re.search(pattern, search_content, re.MULTILINE | re.IGNORECASE | re.DOTALL)
                if match:
                    # Adjust match position if we're searching in a subset
                    actual_start = search_start + match.start()
                    actual_end = search_start + match.end()
                    
                    # Find the function body start (after the arrow or opening brace)
                    # Look for arrow function: => { or => (
                    arrow_match = re.search(r'=>\s*[{(]', content[actual_end:actual_end+200])
                    if arrow_match:
                        body_start = actual_end + arrow_match.end()
                        # Determine if it's a brace or parenthesis
                        if content[body_start - 1] == '{':
                            # Find matching closing brace
                            brace_count = 1
                            pos = body_start
                            while pos < len(content) and brace_count > 0:
                                if content[pos] == '{':
                                    brace_count += 1
                                elif content[pos] == '}':
                                    brace_count -= 1
                                pos += 1
                            
                            if brace_count == 0:
                                test_content = content[actual_start:pos]
                                logger.debug(f"Extracted {len(test_content)} chars of test content for '{method_name}'")
                                return test_content
                        else:
                            # Parenthesis - find matching closing parenthesis
                            paren_count = 1
                            pos = body_start
                            while pos < len(content) and paren_count > 0:
                                if content[pos] == '(':
                                    paren_count += 1
                                elif content[pos] == ')':
                                    paren_count -= 1
                                pos += 1
                            
                            if paren_count == 0:
                                test_content = content[actual_start:pos]
                                logger.debug(f"Extracted {len(test_content)} chars of test content for '{method_name}'")
                                return test_content
                    else:
                        # Regular function: function() { ... } or callback function
                        func_match = re.search(r'function\s*\([^)]*\)\s*{|\([^)]*\)\s*{', content[actual_end:actual_end+200])
                        if func_match:
                            body_start = actual_end + func_match.end()
                            brace_count = 1
                            pos = body_start
                            while pos < len(content) and brace_count > 0:
                                if content[pos] == '{':
                                    brace_count += 1
                                elif content[pos] == '}':
                                    brace_count -= 1
                                pos += 1
                            
                            if brace_count == 0:
                                test_content = content[actual_start:pos]
                                logger.debug(f"[javascript] Extracted {len(test_content)} chars of test content for '{method_name}'")
                                return test_content
            
            logger.warning(f"[javascript] Could not find test content for '{method_name}' in {filepath.name} (line {line_number})")
            
        except Exception as e:
            logger.warning(f"[javascript] Failed to extract test content from {filepath}:{line_number}: {e}", exc_info=True)
        
        return ''
    
    def _extract_metadata(
        self, tests: List[Dict], test_files: List[Path], repo_path: Path
    ) -> List[Dict]:
        """Extract test metadata."""
        metadata = []
        content_extracted = 0
        content_failed = 0
        
        # DEBUG: Log first few tests to verify method_name format
        self._log_progress(f"Extracting metadata for {len(tests)} tests")
        if tests:
            sample_test = tests[0]
            logger.info(f"[javascript] Sample test: method_name='{sample_test.get('method_name')}', line_number={sample_test.get('line_number')}, file={Path(sample_test.get('file_path', '')).name}")
        
        for test in tests:
            # Extract test content (function body)
            test_content = ''
            try:
                filepath = Path(test['file_path'])
                
                # Try to resolve file path if it doesn't exist
                if not filepath.exists():
                    # Try relative to repo_path
                    if repo_path:
                        filepath = repo_path / filepath
                        if not filepath.exists():
                            # Try as absolute path
                            filepath = Path(test['file_path']).resolve()
                
                if filepath.exists():
                    test_content = self._extract_test_content(
                        filepath,
                        test['method_name'],
                        test.get('line_number')
                    )
                    if test_content:
                        content_extracted += 1
                    else:
                        content_failed += 1
                        # Log first few failures for debugging
                        if content_failed <= 3:
                            logger.debug(f"[javascript] Failed to extract content for test '{test.get('method_name')}' in {filepath.name} (line {test.get('line_number')})")
                else:
                    logger.warning(f"[javascript] Test file does not exist: {test['file_path']} (resolved: {filepath})")
                    content_failed += 1
            except Exception as e:
                logger.warning(f"[javascript] Error extracting content for {test.get('test_id')}: {e}", exc_info=True)
                content_failed += 1
            
            # Use test content as description
            full_description = test_content if test_content else ''
            
            metadata.append({
                'test_id': test['test_id'],
                'file_path': test['file_path'],
                'class_name': test.get('class_name', ''),
                'method_name': test['method_name'],
                'name': test['method_name'],
                'description': full_description,  # Now contains test content
                'markers': [],
                'annotations': [],
                'is_async': False,
                'is_parameterized': False,
                'is_disabled': False,
                'pattern': 'annotation_based',
                'line_number': test.get('line_number'),
            })
        
        self._log_progress(f"Test content extraction: {content_extracted} succeeded, {content_failed} failed out of {len(tests)} tests")
        return metadata
    
    def _extract_mocks(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> List[Dict]:
        """Extract mock usage from test files."""
        mocks = []
        tests_by_file = defaultdict(list)
        for test in tests:
            file_path = test.get('file_path', '')
            if file_path:
                tests_by_file[file_path].append(test)
        
        # Mock patterns: jest.mock(), jest.fn(), sinon.mock(), etc.
        mock_patterns = [
            (r'jest\.mock\s*\(([^)]+)\)', 'jest.mock', 'module'),
            (r'jest\.fn\s*\(', 'jest.fn', None),
            (r'jest\.spyOn\s*\(([^)]+)\)', 'jest.spyOn', 'object'),
            (r'sinon\.mock\s*\(([^)]+)\)', 'sinon.mock', 'object'),
            (r'sinon\.stub\s*\(([^)]+)\)', 'sinon.stub', 'object'),
            (r'mock\(([^)]+)\)', 'mock', 'module'),
            (r'vi\.mock\s*\(([^)]+)\)', 'vi.mock', 'module'),  # Vitest
            (r'vi\.fn\s*\(', 'vi.fn', None),  # Vitest
        ]
        
        for filepath in test_files:
            file_path_str = str(filepath)
            file_tests = tests_by_file.get(file_path_str, [])
            if not file_tests:
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                
                for pattern, mock_type, target_type in mock_patterns:
                    regex = re.compile(pattern, re.MULTILINE)
                    for match in regex.finditer(content):
                        line_num = content[:match.start()].count('\n') + 1
                        target_value = match.group(1) if match.lastindex and match.lastindex >= 1 else None
                        
                        # Try to extract mock implementation if present
                        mock_impl = None
                        if target_value:
                            # Look for arrow function or function after the mock call
                            after_match = content[match.end():match.end()+200]
                            if '=>' in after_match or 'function' in after_match:
                                mock_impl = after_match[:100].strip()
                        
                        for test in file_tests:
                            mock_data = {
                                'test_id': test['test_id'],
                                'mock_type': mock_type,
                                'line_number': line_num,
                            }
                            
                            if target_type == 'module' and target_value:
                                mock_data['mock_target'] = target_value.strip().strip('"\'')
                            elif target_type == 'object' and target_value:
                                mock_data['mock_target'] = target_value.strip().strip('"\'')
                            
                            if mock_impl:
                                mock_data['mock_implementation'] = mock_impl
                            
                            mocks.append(mock_data)
            except Exception as e:
                logger.warning(f"Error extracting mocks from {filepath}: {e}")
        
        return mocks
    
    def _extract_async_tests(
        self, tests: List[Dict], test_files: List[Path], repo_path: Path
    ) -> List[Dict]:
        """Extract async test information."""
        async_tests = []
        
        for test in tests:
            file_path = test.get('file_path', '')
            if not file_path:
                continue
            
            try:
                filepath = Path(file_path)
                if not filepath.exists():
                    continue
                
                content = filepath.read_text(encoding='utf-8', errors='replace')
                method_name = test.get('method_name', '')
                
                if method_name:
                    # Check if test is async (async function, async arrow, etc.)
                    async_patterns = [
                        rf'async\s+function\s+{re.escape(method_name)}',
                        rf'async\s+\([^)]*\)\s*=>',
                        rf'async\s+{re.escape(method_name)}\s*\(',
                    ]
                    
                    is_async = any(re.search(pattern, content, re.MULTILINE) for pattern in async_patterns)
                    
                    if is_async:
                        # Determine async pattern
                        async_pattern_type = 'async/await'
                        if 'done()' in content or 'done =>' in content:
                            async_pattern_type = 'callback'
                        elif 'Promise' in content:
                            async_pattern_type = 'promise'
                        
                        async_tests.append({
                            'test_id': test['test_id'],
                            'is_async': True,
                            'async_pattern': async_pattern_type,
                        })
            except Exception as e:
                logger.warning(f"Error extracting async test info from {file_path}: {e}")
        
        return async_tests
    
    # ── Regex used to split compound describe labels ──────────────────────────
    # "capitalizeFirstLetter with checkWhiteSpace" → "capitalizeFirstLetter"
    # "toastReducer > TOAST action"               → "toastReducer"
    # "validateEmailOrUsername uses EMAIL_REGEX"  → "validateEmailOrUsername"
    _DESCRIBE_SPLIT_RE = re.compile(
        r'\s+(?:with|uses|from|for|in|that|>|→|:)\s+', re.IGNORECASE
    )

    @staticmethod
    def _normalize_import_to_stem(ref_class: str):
        """
        Normalize a raw JS/TS import string to its file stem so the reverse
        index can be queried by the stem that build_search_queries generates.

        '../helpers/utilities' → 'utilities'
        '../signInFormHook'    → 'signInFormHook'
        './MyComponent'        → 'MyComponent'
        'react'                → None  (external, already a bare name)
        '@reduxjs/toolkit'     → None  (scoped package)

        Only local/relative paths (starting with '.', or containing '/' but NOT
        starting with '@') are normalized.  External packages are left as-is
        because their bare names are already the DB key that searches use.
        """
        from pathlib import Path as _Path
        if not ref_class:
            return None
        # Skip @-scoped packages (e.g. '@reduxjs/toolkit')
        if ref_class.startswith('@'):
            return None
        # Only normalize when the string looks like a file path (contains '/' or starts with '.')
        if not (ref_class.startswith('.') or '/' in ref_class):
            return None
        stem = _Path(ref_class).stem
        # If stem == ref_class the Path didn't change anything — nothing to normalize
        if not stem or stem == ref_class:
            return None
        return stem

    def _build_reverse_index(
        self, dependencies: List[Dict], function_calls: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Build reverse index.

        Five sources are merged:
        1.  File-level direct imports   — raw path  e.g. '../helpers/utilities'
        1b. Normalized stem of Source 1 — file stem e.g. 'utilities'
        1c. Transitive imports          — raw repo-relative path (2-3 hops away)
        1d. Normalized stem of Source 1c
        2.  Method calls (function_calls.module_name)
        3.  describe-label extraction from class_name

        Sources 1c/1d are NEW — they index tests that transitively import a
        changed production file, enabling AST selection to find tests even when
        the import chain is 2-3 hops deep (the main JS/TS false-negative gap).
        """
        reverse_index = defaultdict(list)

        for dep in dependencies:
            for ref_class in dep.get('referenced_classes', []):
                ref_type = dep['reference_types'].get(ref_class, 'direct_import')
                entry = {
                    'test_id': dep['test_id'],
                    'file_path': dep['file_path'],
                    'class_name': dep.get('class_name', ''),
                    'method_name': dep['method_name'],
                    'reference_type': ref_type,
                }
                # Source 1 / 1c: raw import path
                reverse_index[ref_class].append(entry)
                # Source 1b / 1d: normalized file stem
                normalized = self._normalize_import_to_stem(ref_class)
                if normalized:
                    norm_type = (
                        'transitive_normalized'
                        if ref_type == 'transitive_import'
                        else 'source_annotation_normalized'
                        if ref_type == 'source_annotation'
                        else 'normalized_import'
                    )
                    reverse_index[normalized].append({**entry, 'reference_type': norm_type})
        
        for call in function_calls:
            if call.get('module_name'):
                reverse_index[call['module_name']].append({
                    'test_id': call['test_id'],
                    'file_path': call['file_path'],
                    'class_name': call.get('class_name', ''),
                    'method_name': call['method_name'],
                    'reference_type': call.get('source', 'method_call'),
                })
        
        # ── Source 3: describe-label → production symbol ──────────────────────
        # Deduplicate (symbol, test_id) pairs so we don't insert duplicates.
        seen_label: set = set()
        for dep in dependencies:
            class_name = (dep.get('class_name') or '').strip()
            if not class_name:
                continue
            # Extract primary symbol: split on connector words, take first part.
            primary = self._DESCRIBE_SPLIT_RE.split(class_name, maxsplit=1)[0].strip()
            # Also strip any trailing " > something" (nested describe)
            primary = primary.split(' > ')[0].strip()
            if not primary:
                continue
            key = (primary, dep['test_id'])
            if key in seen_label:
                continue
            seen_label.add(key)
            reverse_index[primary].append({
                'test_id': dep['test_id'],
                'file_path': dep['file_path'],
                'class_name': class_name,
                'method_name': dep.get('method_name', ''),
                'reference_type': 'describe_label',
            })
            # If the primary symbol differs from class_name, also add the full class_name
            if primary != class_name:
                full_key = (class_name, dep['test_id'])
                if full_key not in seen_label:
                    seen_label.add(full_key)
                    reverse_index[class_name].append({
                        'test_id': dep['test_id'],
                        'file_path': dep['file_path'],
                        'class_name': class_name,
                        'method_name': dep.get('method_name', ''),
                        'reference_type': 'describe_label',
                    })
        # ──────────────────────────────────────────────────────────────────────
        
        return dict(reverse_index)
    
    def _map_test_structure(
        self, test_files: List[Path], tests: List[Dict], repo_path: Path
    ) -> Dict:
        """Map test structure."""
        by_category = defaultdict(list)
        for test in tests:
            by_category[test.get('test_type', 'unit')].append(test)
        
        return {
            'directory_structure': {
                'root_path': str(repo_path),
                'directories': {
                    cat: {
                        'file_count': len(set(t['file_path'] for t in tests)),
                        'test_count': len(tests),
                        'total_lines': 0,
                    }
                    for cat, tests in by_category.items()
                },
            },
            'summary': {
                'total_directories': len(by_category),
                'total_files': len(test_files),
                'categories': list(by_category.keys()),
            },
        }
    
    def _write_outputs(
        self, output_dir: Path, test_files: List[Path], framework: str, confidence: str,
        tests: List[Dict], dependencies: List[Dict], function_calls: List[Dict],
        metadata: List[Dict], reverse_index: Dict, structure: Dict, repo_path: Path,
        mocks: List[Dict] = None, async_tests: List[Dict] = None
    ):
        """Write all JSON output files (8 core + 2 JavaScript-specific)."""
        now = datetime.now().isoformat()
        
        # Write all 8 files with same structure as other analyzers
        self._write_json(output_dir / '01_test_files.json', {
            'generated_at': now,
            'data': {
                'scan_directory': str(repo_path),
                'total_files': len(test_files),
                'total_lines': sum(self._count_lines(f) for f in test_files),
                'total_size_bytes': sum(f.stat().st_size for f in test_files if f.exists()),
                'categories': self._categorize_files(test_files),
                'files': [
                    {
                        'path': str(f),
                        'file_path': str(f),
                        'name': f.name,
                        'directory': self._get_category(f),
                        'line_count': self._count_lines(f),
                        'size_bytes': f.stat().st_size if f.exists() else 0,
                        'language': 'javascript',
                    }
                    for f in test_files
                ],
            },
        })
        
        self._write_json(output_dir / '02_framework_detection.json', {
            'generated_at': now,
            'data': {
                'primary_framework': framework,
                'framework': framework,
                'confidence': confidence,
                'evidence': [f'{framework} detected'],
            },
        })
        
        by_type = defaultdict(int)
        by_file = defaultdict(int)
        for test in tests:
            by_type[test.get('test_type', 'unit')] += 1
            by_file[test['file_path']] += 1
        
        self._write_json(output_dir / '03_test_registry.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(tests),
                'total_classes': 0,
                'total_files': len(test_files),
                'tests_by_type': dict(by_type),
                'tests_by_file': dict(by_file),
                'tests': tests,
            },
        })
        
        total_refs = sum(d.get('import_count', 0) for d in dependencies)
        self._write_json(output_dir / '04_static_dependencies.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(dependencies),
                'tests_with_dependencies': sum(1 for d in dependencies if d.get('import_count', 0) > 0),
                'total_references': total_refs,
                'average_references_per_test': round(total_refs / len(dependencies), 2) if dependencies else 0,
                'test_dependencies': dependencies,
            },
        })
        
        self._write_json(output_dir / '04b_function_calls.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(tests),
                'tests_with_function_calls': len(set(c['test_id'] for c in function_calls)),
                'total_mappings': len(function_calls),
                'average_mappings_per_test': round(len(function_calls) / len(tests), 2) if tests else 0,
                'test_function_mappings': function_calls,
            },
        })
        
        self._write_json(output_dir / '05_test_metadata.json', {
            'generated_at': now,
            'data': {
                'total_tests': len(metadata),
                'tests_with_descriptions': sum(1 for m in metadata if m.get('description')),
                'tests_with_markers': sum(1 for m in metadata if m.get('markers')),
                'async_tests': 0,
                'parameterized_tests': 0,
                'disabled_tests': 0,
                'test_metadata': metadata,
            },
        })
        
        total_mappings = sum(len(v) for v in reverse_index.values())
        self._write_json(output_dir / '06_reverse_index.json', {
            'generated_at': now,
            'data': {
                'total_production_classes': len(reverse_index),
                'total_mappings': total_mappings,
                'average_tests_per_class': round(total_mappings / len(reverse_index), 2) if reverse_index else 0,
                'reverse_index': {k: v for k, v in reverse_index.items()},
            },
        })
        
        self._write_json(output_dir / '07_test_structure.json', {
            'generated_at': now,
            'data': structure,
        })
        
        summary = self._generate_summary(
            test_files, tests, dependencies, reverse_index,
            metadata, framework, confidence
        )
        self._write_json(output_dir / '08_summary_report.json', {
            'generated_at': now,
            'data': summary,
        })
        
        # 09_js_mocks.json (JavaScript-specific)
        if mocks:
            self._write_json(output_dir / '09_js_mocks.json', {
                'generated_at': now,
                'data': {
                    'total_mocks': len(mocks),
                    'tests_with_mocks': len(set(m['test_id'] for m in mocks)),
                    'mocks': mocks,
                },
            })
        
        # 10_js_async_tests.json (JavaScript-specific)
        if async_tests:
            self._write_json(output_dir / '10_js_async_tests.json', {
                'generated_at': now,
                'data': {
                    'total_async_tests': len(async_tests),
                    'async_tests': async_tests,
                },
            })
    
    def _write_json(self, path: Path, data: Dict):
        """Write JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _count_lines(self, filepath: Path) -> int:
        """Count lines in file."""
        try:
            return len(filepath.read_text(encoding='utf-8', errors='replace').splitlines())
        except:
            return 0
    
    def _get_category(self, filepath: Path) -> str:
        """Get test category."""
        return self._get_test_type(filepath)
    
    def _categorize_files(self, test_files: List[Path]) -> Dict[str, int]:
        """Categorize files."""
        cats = defaultdict(int)
        for f in test_files:
            cats[self._get_category(f)] += 1
        return dict(cats)
    
    def _generate_summary(
        self, test_files: List[Path], tests: List[Dict],
        dependencies: List[Dict], reverse_index: Dict,
        metadata: List[Dict], framework: str, confidence: str
    ) -> Dict:
        """Generate summary."""
        total_prod_classes = len(reverse_index)
        total_deps = sum(d.get('import_count', 0) for d in dependencies)
        
        # Calculate tests_by_type
        by_type = defaultdict(int)
        for test in tests:
            by_type[test.get('test_type', 'unit')] += 1
        
        return {
            'test_repository_overview': {
                'total_test_files': len(test_files),
                'total_lines_of_code': sum(self._count_lines(f) for f in test_files),
                'test_framework': framework,
                'framework_confidence': confidence,
                'language': 'javascript',
            },
            'test_inventory': {
                'total_tests': len(tests),
                'total_test_classes': 0,
                'tests_by_type': dict(by_type),
            },
            'dependencies': {
                'total_production_classes_referenced': total_prod_classes,
                'total_dependency_mappings': total_deps,
                'average_tests_per_class': round(len(tests) / total_prod_classes, 2) if total_prod_classes else 0,
                'tests_with_dependencies': sum(1 for d in dependencies if d.get('import_count', 0) > 0),
            },
            'metadata': {
                'tests_with_descriptions': 0,
                'tests_with_markers': 0,
                'async_tests': 0,
                'parameterized_tests': 0,
                'disabled_tests': 0,
            },
            'summary_for_db': {
                'files_analyzed': len(test_files),
                'functions_extracted': 0,
                'modules_identified': 0,
                'test_files': len(test_files),
                'total_tests': len(tests),
                'total_test_classes': 0,
                'total_test_methods': len(tests),
                'total_dependencies': total_deps,
                'total_production_classes': total_prod_classes,
                'tests_with_descriptions': 0,
                'framework': framework,
            },
        }
