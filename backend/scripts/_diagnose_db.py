"""Full DB audit for test_repo_261b672a."""
import sys
from pathlib import Path
_backend = str(Path(__file__).parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)
from deterministic.db_connection import get_connection_with_schema

schema = "test_repo_261b672a"
with get_connection_with_schema(schema) as conn:
    with conn.cursor() as cur:

        print("=== reverse_index - ALL entries ===")
        cur.execute(f"SELECT production_class, COUNT(*) cnt FROM {schema}.reverse_index GROUP BY production_class ORDER BY cnt DESC")
        rows = cur.fetchall()
        print(f"  Total unique production_class values: {len(rows)}")
        for r in rows: print(f"  {r[0]!r:40s} -> {r[1]} tests")

        print()
        print("=== test_function_mapping - sample (non-js/ts) ===")
        cur.execute(
            f"SELECT function_name, COUNT(*) cnt FROM {schema}.test_function_mapping "
            f"WHERE function_name NOT IN ('js','ts','jsx','tsx','css','test','it','describe') "
            f"GROUP BY function_name ORDER BY cnt DESC LIMIT 30"
        )
        rows = cur.fetchall()
        print(f"  Top production functions in mapping:")
        for r in rows: print(f"  {r[0]!r:40s} -> {r[1]} tests")

        print()
        print("=== test_registry - count by file ===")
        cur.execute(
            f"SELECT file_path, COUNT(*) cnt FROM {schema}.test_registry "
            f"GROUP BY file_path ORDER BY cnt DESC"
        )
        rows = cur.fetchall()
        for r in rows: print(f"  {r[1]:3d} tests in {r[0]}")

        print()
        print("=== js_mocks (sample) ===")
        cur.execute(f"SELECT test_id, mock_target FROM {schema}.js_mocks LIMIT 10")
        rows = cur.fetchall()
        for r in rows: print(f"  {r[0]} mocks {r[1]!r}")
