"""
Prompt builder for dependency classification (Independent | CrossDependent).

Called after all test selection is done. Given the diff and the selected tests,
the LLM decides whether each test DIRECTLY exercises the changed code
(Independent) or is INDIRECTLY affected through an import chain or semantic
similarity (CrossDependent).
"""

from typing import List, Dict


def build_dependency_classification_prompt(
    diff_content: str,
    tests: List[Dict],
) -> str:
    """
    Build a batched prompt for classifying selected tests into:
      - Independent     : test directly imports / exercises the changed code
      - CrossDependent  : test is indirectly affected (chain, similarity, co-location)

    Each test dict must have: test_id, class_name, method_name, match_type,
    and optionally rule_hint (pre-computed rule-based label for context).

    Returns a prompt string the caller sends to the LLM as the user message.
    """
    # Truncate diff to keep total tokens manageable (~4 k chars ≈ ~1 k tokens)
    diff_snippet = diff_content[:4000]
    if len(diff_content) > 4000:
        diff_snippet += "\n... (truncated)"

    # Build the test list section
    test_lines: List[str] = []
    for i, t in enumerate(tests, 1):
        tid   = t.get("test_id", f"test_{i:04d}")
        cls   = (t.get("class_name") or "").strip()
        mth   = (t.get("method_name") or "").strip()
        fpath = (t.get("test_file_path") or t.get("file_path") or "").strip()
        mtype = (t.get("match_type") or "").strip()
        # rule_hint is the fast rule-based result — passed as a hint so the LLM
        # can agree quickly for obvious cases and focus effort on ambiguous ones.
        hint  = (t.get("rule_hint") or "unknown").strip()

        test_lines.append(
            f"{i}. id={tid} | class={cls!r} | method={mth!r} | "
            f"file={fpath} | match={mtype} | rule_hint={hint}"
        )

    all_ids_literal = ", ".join(
        f'"{t.get("test_id", f"test_{i:04d}")}"'
        for i, t in enumerate(tests, 1)
    )

    prompt = f"""You classify selected tests against a code diff.
Assign EACH test exactly one label: Independent OR CrossDependent.

═══════════════════════════════════════════════════════════
DEFINITIONS
═══════════════════════════════════════════════════════════

Independent
  The test DIRECTLY exercises the code that was changed.
  Use this label when ANY of these are true:
  • The test's describe() / class name IS the changed function or symbol
    (e.g. class="unifiedSearchAPI" and diff adds unifiedSearchAPI)
  • The test imports the changed file with a path that matches the diff
    (e.g. @source annotation or import statement for the changed file)
  • The test calls the changed function by name and asserts its behaviour
  • If the changed code were deleted, THIS test would fail immediately

CrossDependent
  The test is INDIRECTLY affected. Use this when:
  • The test was found only by vector/semantic similarity (no import chain)
  • The test covers a different function from the same file
    (sibling symbol — still worth running but not a direct test)
  • The test imports a file that imports the changed file (2+ hops away)
  • The test is in the same file as a directly-matched test (co-located)
  • The test's class/method name belongs to an unrelated module

IMPORTANT RULES
  1. If rule_hint says "independent" AND the class name matches the diff symbols,
     trust it — label Independent without further analysis.
  2. If rule_hint says "cross_dependent" but the class/method name EXACTLY matches
     a changed symbol in the diff, override to Independent.
  3. When unsure, use confidence="low" and label CrossDependent (conservative).
  4. Never use any label other than "Independent" or "CrossDependent".

═══════════════════════════════════════════════════════════
DIFF (what changed):
═══════════════════════════════════════════════════════════
{diff_snippet}

═══════════════════════════════════════════════════════════
SELECTED TESTS (id | class | method | file | match_type | rule_hint):
═══════════════════════════════════════════════════════════
{chr(10).join(test_lines)}

═══════════════════════════════════════════════════════════
OUTPUT FORMAT — return ONLY the JSON below, no extra text:
═══════════════════════════════════════════════════════════
{{
  "classifications": [
    {{
      "test_id": "test_0001",
      "label": "Independent",
      "confidence": "high",
      "reason": "one short sentence ≤ 20 words"
    }}
    // Repeat for EVERY test id: {all_ids_literal}
  ]
}}
"""
    return prompt.strip()
