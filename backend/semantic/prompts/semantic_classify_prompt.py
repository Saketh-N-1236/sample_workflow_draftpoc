"""
Prompt builder for semantic retrieval classification (Critical | High | NonRelevant).
"""

from typing import List, Dict


def build_semantic_classification_prompt(
    diff_summary: str,
    candidates: List[Dict],
) -> str:
    """
    Build a compact prompt asking the LLM to classify each test as:
    - Critical: Directly exercises or is a regression guard for the changed file/module
    - High: Likely relevant but less central than Critical
    - NonRelevant: Same domain words only or different module/file

    Returns a strict JSON schema with classifications for all candidates.
    """
    truncated_diff = diff_summary[:6000]
    if len(diff_summary) > 6000:
        truncated_diff += "\n... (truncated)"

    lines = []
    for i, t in enumerate(candidates, 1):
        cid = t.get("test_id", f"test_{i:04d}")
        cls = t.get("class_name", "") or ""
        mth = t.get("method_name", "") or ""
        fpt = t.get("test_file_path", "") or t.get("file_path", "") or t.get("relative_path", "") or ""
        reason_hints = t.get("match_reasons") or []
        lines.append(
            f"{i}. id={cid} | class={cls} | method={mth} | file={fpt} | hints={', '.join(reason_hints[:3])}"
        )

    test_ids_literal = ", ".join([f"\"{t.get('test_id', f'test_{i:04d}')}\"" for i, t in enumerate(candidates, 1)])

    prompt = f"""
You classify retrieved tests given a diff. Assign EACH test exactly one label.

---
## Labels and when to use them

**Critical** — The test directly exercises the changed symbol, OR it is a regression guard
in the same test class/describe block that contains the changed symbol.
Examples:
- Test for `CARD_REGEX` when `CARD_REGEX` definition changed → Critical
- Test for `paymentReducer` when `paymentReducer.js` changed → Critical

**High** — The test has a STRUCTURAL dependency on the changed source file even though
it does not directly test the changed symbol. Three sub-cases qualify:

  1. SIBLING SYMBOL — The test covers another export from the SAME source file.
     e.g. `EMAIL_REGEX` test when `CARD_REGEX` changed (both from `constants.ts`).
     The whole exports surface of the file could be affected by editing that file.

  2. CROSS-DEPENDENT — The test file imports the changed source file as a dependency.
     e.g. `validateEmailOrUsername` test in `auth-storage.cross.test.js` imports
     `constants.ts` → must run to confirm nothing broke through the import.

  3. AST/EXACT HINT — Match hints include `exact`, `direct_file`, `function_level`,
     or `colocated_from_semantic`. These signal a confirmed import/dependency link
     found by static analysis; treat as High unless the class name makes it obviously
     unrelated to the changed file's domain.

**NonRelevant** — The test has NO structural dependency on the changed source file.
Match hints are `semantic` only, and the test class/file points to a completely
different module with only vocabulary overlap.
Example: A `userProfileReducer` test when `constants.ts` changed, linked only because
both mention "user" — no import of constants.ts detected.

---
## Critical decision rule — "same source file" means the PRODUCTION file

When the diff changes `src/types/constants.ts`, every test that imports `constants.ts`
is in the blast radius — regardless of which test file it lives in.
Do NOT confuse "different test file" with "unrelated". A cross-dependent test file that
lists `constants.ts` in its sources is just as relevant as a standalone test file.

---
Diff (summary or truncated content):
```
{truncated_diff}
```

Tests (id | describe/class | method | file | hints):
{chr(10).join(lines)}

---
Classify EVERY test. Return strict JSON only — no prose, no markdown fences.

{{
  "classifications": [
    {{
      "test_id": "test_0001",
      "label": "Critical|High|NonRelevant",
      "reason": "one short sentence"
    }}
    // include EVERY test id: {test_ids_literal}
  ]
}}
"""
    return prompt.strip()
