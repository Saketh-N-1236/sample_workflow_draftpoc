# Universal parsing (Tree-sitter + plugins)

## Order of operations

1. **Tree-sitter** — Full AST for Java, Python, JavaScript, TypeScript, TSX, C, C++ (when grammars are installed). Imports always captured when TS runs.
2. **Plugins** — Regex runs when TS finds **no** tests, **or** for **C/C++ always** (merge): GTest `TEST`/`TEST_F`/… plus `void test_*` from TS. Result may be `treesitter`, `treesitter+regex`, or `regex`.

## Grammars

| Language   | Package / module        |
|-----------|-------------------------|
| Python    | `tree_sitter_python`    |
| Java      | `tree_sitter_java`      |
| JS / TS   | `tree_sitter_javascript`, `tree_sitter_typescript` (typescript + tsx) |
| C         | `tree_sitter_c`         |
| C++       | `tree_sitter_cpp`       |

Install C/C++: `pip install tree-sitter-c tree-sitter-cpp`

**Repo analysis:** `CPlugin` / `CppPlugin` (`plugins/native/`) run when the engine detects `.c`/`.h` or `.cpp`/… files — same parser, feeds core `test_registry` / dependencies.

## Adding a plugin

1. Implement `run_plugin(name, content, language, filepath, partial_result) -> dict | None`.
2. Register in `plugins/__init__.py` → `default_plugin_chain()`.
