"""Enrich reverse_index for existing test repo without full re-analysis."""
import sys
from pathlib import Path
_backend = str(Path(__file__).parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)
import re as _re
from deterministic.db_connection import get_connection_with_schema
from psycopg2.extras import execute_values

_DESCRIBE_SPLIT_RE = _re.compile(r'\s+(?:with|uses|from|for|in|that|>|:)\s+', _re.IGNORECASE)

schema = "test_repo_261b672a"
print(f"Enriching reverse_index for schema: {schema}")

with get_connection_with_schema(schema) as conn:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT test_id, class_name, file_path "
            f"FROM {schema}.test_registry "
            f"WHERE class_name IS NOT NULL AND class_name <> '' "
            f"ORDER BY test_id"
        )
        rows = cur.fetchall()

    entries = []
    seen = set()
    for test_id, class_name, file_path in rows:
        class_name = (class_name or "").strip()
        if not class_name:
            continue
        primary = _DESCRIBE_SPLIT_RE.split(class_name, maxsplit=1)[0].strip()
        primary = primary.split(" > ")[0].strip()
        for symbol in {primary, class_name}:
            if not symbol:
                continue
            key = (symbol, test_id)
            if key in seen:
                continue
            seen.add(key)
            entries.append((symbol, test_id, file_path, "describe_label"))

    print(f"Entries to insert: {len(entries)}")
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO {schema}.reverse_index "
            f"(production_class, test_id, test_file_path, reference_type) "
            f"VALUES %s ON CONFLICT DO NOTHING",
            entries
        )
    conn.commit()
    print("Done!")

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT production_class, COUNT(*) cnt "
            f"FROM {schema}.reverse_index "
            f"GROUP BY production_class ORDER BY cnt DESC LIMIT 25"
        )
        print("\nTop entries after enrichment:")
        for r in cur.fetchall():
            print(f"  {r[0]!r:55s} -> {r[1]} tests")
