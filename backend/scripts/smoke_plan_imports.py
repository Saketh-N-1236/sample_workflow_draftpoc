"""Run from backend/: python scripts/smoke_plan_imports.py — verifies key imports."""

import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

if __name__ == "__main__":
    from services.repository_vcs import normalize_diff_payload
    from services.http_client import get_shared_async_client
    from parsers.registry import get_registry
    from git_diff_processor.process_diff_programmatic import process_diff_and_select_tests

    get_registry()
    normalize_diff_payload({"diff": "", "changed_files": []})
    assert get_shared_async_client() is not None
    assert process_diff_and_select_tests is not None
    print("smoke_plan_imports: ok")
