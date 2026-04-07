"""
Summarize git diff for use as the original query in semantic search.

Flow:
1. Embed the **entire** diff (embedding model) — aligns with validation / vector pipeline.
2. Pass the **entire** diff to the chat LLM for a search-oriented summary.

Optional: DIFF_SUMMARY_MAX_CHARS caps text for both steps if set (positive int).
Optional: DIFF_SUMMARY_MAX_TOKENS for chat completion (default 4096).
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import logging

project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from llm.factory import LLMFactory
from llm.models import LLMRequest, EmbeddingRequest
from config.settings import get_settings

logger = logging.getLogger(__name__)

_LARGE_DIFF_WARN_CHARS = 200_000


def _full_diff_for_pipeline(diff_content: str) -> Tuple[str, bool]:
    """Return full diff unless DIFF_SUMMARY_MAX_CHARS is a positive int."""
    cap_s = os.environ.get("DIFF_SUMMARY_MAX_CHARS", "").strip()
    if cap_s:
        try:
            cap = int(cap_s)
            if cap > 0 and len(diff_content) > cap:
                return diff_content[:cap] + "\n... (truncated)", True
        except ValueError:
            pass
    return diff_content, False


async def summarize_git_diff(diff_content: Optional[str]) -> Optional[str]:
    """
    1) Embed entire diff (best-effort; failure does not block summarization).
    2) Send entire diff to chat LLM; return summary text.
    """
    if not diff_content or not diff_content.strip():
        return None

    diff_text, truncated = _full_diff_for_pipeline(diff_content)
    n = len(diff_text)

    if n > _LARGE_DIFF_WARN_CHARS:
        logger.warning(
            f"[DIFF_SUMMARY] Diff is large ({n} chars); ensure embedding + chat models support context."
        )
    if truncated:
        logger.info(f"[DIFF_SUMMARY] Using capped diff: {n} chars (DIFF_SUMMARY_MAX_CHARS)")
    else:
        logger.info(f"[DIFF_SUMMARY] Using full diff: {n} chars")

    settings = get_settings()

    # Step 1: Embed entire diff first
    try:
        embed_provider = LLMFactory.create_embedding_provider(settings)
        emb_resp = await embed_provider.get_embeddings(EmbeddingRequest(texts=[diff_text]))
        vec = emb_resp.embeddings[0] if emb_resp.embeddings else []
        logger.info(
            f"[DIFF_SUMMARY] Diff embedded first | dim={len(vec)} | provider={getattr(emb_resp, 'provider', '')}"
        )
    except Exception as e:
        logger.warning(
            f"[DIFF_SUMMARY] Diff embedding failed (continuing to LLM): {e}"
        )

    # Step 2: Chat LLM with full diff text
    try:
        chat_provider = LLMFactory.create_provider(settings)
    except Exception as e:
        logger.warning(f"Diff summarizer: LLM provider not available: {e}")
        return None

    prompt = f"""You will write ONE continuous paragraph (or a few short paragraphs) that will be turned into a **vector embedding** to retrieve **automated tests** from a database.

## Critical rules (precision)
1. **Lead with concrete anchors** — In the first 2–3 sentences, repeat **every changed file path** exactly as it appears in the diff (e.g. `src/features/auth/hooks/signUpFormHook.ts`). Then list **function names, hooks, classes, constants, and exported symbols** that are added, removed, or edited. Do not replace them with vague labels like "the auth layer" or "validation logic" without also naming the real identifiers.
2. **Scope follows the diff** — If the diff touches one file, stay focused on that file and its symbols. If it touches many files, summarize each touched area briefly; do not invent unrelated subsystems.
3. **Avoid generic bait** — Do not lean only on broad domains ("authentication", "payments", "regex", "forms") unless you **tie them to the specific paths/symbols** above. Generic wording increases false positives in semantic search.
4. **Regex / pattern literals in the diff** — If the diff contains a raw regex literal (e.g. `/\s/g`, `/[A-Z]/`), describe it in functional terms tied to the symbol (e.g. "whitespace-detection logic inside `checkWhiteSpace`"). **Do not use the word "regex"** unless the changed symbol is itself a regex constant. Using "regex" as a standalone word pulls in unrelated regex-constant tests.
5. **Dependencies mentioned in the diff** — If the diff references imports (e.g. `UNIQUE_USERNAME_REGEX`, another module), name them; retrieval can match tests that import the same symbols **only when that connection appears in the diff**.
6. **What we want to retrieve** — Tests that **directly exercise, import, or assert behavior of** these exact files/symbols. You are NOT trying to find "any test in the same product area."

## Retrieval errors to avoid (false positives vs false negatives)
- **False positive (retrieval)**: The summary stresses generic product themes or mood ("validation", "auth flows") without **verbatim** paths and symbol names → the embedding matches **unrelated** tests that share vocabulary but not the changed code.
- **False negative (retrieval)**: The summary omits, abbreviates, or paraphrases away **changed file paths or symbols** → tests that truly cover this diff **never** surface strongly in vector search.
- **Balance**: Keep every anchor **complete and literal** first; only then add short behavioral phrasing that is explicitly tied to those identifiers.

## Style
- Prefer factual, searchable phrases over marketing language.
- 120–600 words is fine if needed for multi-file diffs; single-file changes can be shorter.
- Output **only** the summary text — no headings, no JSON, no bullet labels like "Summary:".

Git diff:
```
{diff_text}
```
"""

    try:
        max_tokens = int(os.environ.get("DIFF_SUMMARY_MAX_TOKENS", "4096"))
        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write embedding-friendly summaries of git diffs for test retrieval. "
                        "Optimize for PRECISION: concrete file paths and symbol names first; "
                        "avoid vague domain-only descriptions (that causes false-positive matches). "
                        "Dropping anchors causes false negatives—relevant tests never rank. "
                        "Output only the summary body, no preamble."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=max(256, max_tokens),
        )
        response = await chat_provider.chat_completion(request)
        summary = (response.content or "").strip()
        if summary:
            logger.info(f"[DIFF_SUMMARY] LLM summary length: {len(summary)} chars")
            return summary
    except Exception as e:
        logger.warning(f"Diff summarization failed: {e}")
    return None
