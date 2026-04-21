"""
LLM Reasoning Service

Two responsibilities:
1. classify_semantic_candidates — Critical | High | NonRelevant
   Called before AST/semantic merge to prune irrelevant vector hits.

2. classify_dependency_type — Independent | CrossDependent
   Called after final test selection to explain WHY each test was selected:
   does it directly exercise the changed code, or is it indirectly affected?
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging
import json

# Add backend/ to path: backend/services/llm_reasoning_service.py -> parent.parent = backend/
_backend_path = Path(__file__).parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

from llm.factory import LLMFactory
from llm.models import LLMRequest
from config.settings import get_settings
from semantic.prompts.semantic_classify_prompt import build_semantic_classification_prompt
from semantic.prompts.dependency_classify_prompt import build_dependency_classification_prompt
from semantic.config import (
    LLM_RETRIEVAL_BATCH_SIZE,
    LLM_RETRIEVAL_CLASSIFY_TOP_K,
    LLM_RETRIEVAL_MAX_ITEMS,
)

logger = logging.getLogger(__name__)


class LLMReasoningService:
    """Classifies semantic-retrieved test candidates via LLM (Critical/High/NonRelevant)."""

    def __init__(self):
        self.settings = get_settings()
        try:
            self.llm_provider = LLMFactory.create_provider(self.settings)
            logger.info(
                f"LLM Reasoning Service initialized | "
                f"Provider: {self.llm_provider.provider_name.upper()} | "
                f"Model: {self.llm_provider.model_name}"
            )
        except Exception as e:
            logger.error(f"LLM Reasoning Service initialization failed: {e}")
            self.llm_provider = None

    async def classify_semantic_candidates(
        self,
        diff_summary_or_content: str,
        candidates: List[Dict],
        batch_size: Optional[int] = None,
        max_items: Optional[int] = None,
        top_k: Optional[str] = None,
    ) -> List[Dict]:
        """
        Classify semantic-retrieved candidates as Critical | High | NonRelevant.
        Returns list of dicts: { test_id, label, reason }.
        Fails open (returns empty list) if provider is unavailable.
        """
        if not self.llm_provider:
            logger.warning("LLM provider not available, skipping semantic classification")
            return []

        if not candidates:
            return []

        # Resolve limits from config/env
        _batch = batch_size or LLM_RETRIEVAL_BATCH_SIZE
        _max = max_items if isinstance(max_items, int) else LLM_RETRIEVAL_MAX_ITEMS
        _topk = (top_k if isinstance(top_k, str) else LLM_RETRIEVAL_CLASSIFY_TOP_K) or "200"

        # Determine slice for classification
        to_classify = list(candidates)
        if _topk != "all":
            try:
                k = int(_topk)
                to_classify = to_classify[:max(0, k)]
            except ValueError:
                # Ignore invalid top_k; default to config behavior
                to_classify = to_classify[:200]

        if len(to_classify) > _max:
            to_classify = to_classify[:_max]

        # Build all batches upfront, then fire them ALL in parallel.
        batches = [
            to_classify[i : i + _batch]
            for i in range(0, len(to_classify), _batch)
        ]

        async def _sem_batch(batch: List[Dict], slot: int) -> List[Dict]:
            try:
                prompt = build_semantic_classification_prompt(
                    diff_summary_or_content or "", batch
                )
                request = LLMRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You strictly classify retrieved tests for relevance to the given diff. "
                                "Return only JSON with classifications for EVERY provided test id. "
                                "Valid labels: Critical, High, NonRelevant."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=min(4000, 200 + len(batch) * 60),
                )
                response = await self.llm_provider.chat_completion(request)
                parsed = self._parse_simple_classification_json(
                    response.content or "", expected=len(batch)
                )
                logger.info(
                    "[SEM_CLASSIFY] Batch %d/%d: %d result(s) parsed",
                    slot + 1, len(batches), len(parsed),
                )
                return parsed
            except Exception as e:
                logger.warning(
                    "[SEM_CLASSIFY] Batch %d/%d failed: %s", slot + 1, len(batches), e
                )
                return []

        try:
            per_batch: List[List[Dict]] = await asyncio.gather(
                *[_sem_batch(b, i) for i, b in enumerate(batches)]
            )
        except Exception as e:
            logger.warning("Semantic classification failed: %s", e, exc_info=True)
            return []

        results: List[Dict] = [item for br in per_batch for item in br]
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Dependency-type classification  (Independent | CrossDependent)
    # ──────────────────────────────────────────────────────────────────────────

    async def classify_dependency_type(
        self,
        diff_content: str,
        tests: List[Dict],
        batch_size: int = 10,
    ) -> List[Dict]:
        """
        Classify each selected test as Independent or CrossDependent using LLM.

        Flow:
          1. Each test already has a fast rule_hint computed by rule-based logic.
          2. Tests are batched (default 10 per LLM call) and sent with the diff.
          3. LLM returns { classifications: [{test_id, label, confidence, reason}] }.
          4. Results are merged back; missing tests fall back to rule_hint.

        Returns list of dicts:
          { test_id, label, confidence, reason, source }
          label   : "Independent" | "CrossDependent"
          confidence: "high" | "medium" | "low"
          reason  : one short sentence
          source  : "llm" | "rule_fallback"

        Fails open — if LLM is unavailable returns empty list so the caller
        can fall back to rule-based values already on each test dict.
        """
        if not self.llm_provider:
            logger.warning("[DEP_CLASSIFY] LLM provider unavailable — skipping dependency classification")
            return []

        if not tests:
            return []

        total = len(tests)
        batches = [
            tests[i : i + batch_size] for i in range(0, total, batch_size)
        ]
        num_batches = len(batches)
        logger.info(
            "[DEP_CLASSIFY] Classifying %d test(s) in %d parallel batch(es) of %d",
            total, num_batches, batch_size,
        )

        async def _dep_batch(batch: List[Dict], slot: int) -> List[Dict]:
            start_idx = slot * batch_size + 1
            end_idx   = min(start_idx + batch_size - 1, total)
            try:
                prompt = build_dependency_classification_prompt(diff_content or "", batch)
                request = LLMRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You classify selected tests as Independent or CrossDependent "
                                "relative to a code diff. "
                                "Return ONLY the JSON object with a 'classifications' array. "
                                "Valid labels: Independent, CrossDependent. "
                                "Valid confidence: high, medium, low."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=min(4000, 300 + len(batch) * 80),
                )
                response = await self.llm_provider.chat_completion(request)
                parsed = self._parse_dependency_classification_json(
                    response.content or "", batch
                )
                logger.info(
                    "[DEP_CLASSIFY] Batch %d-%d: %d result(s) parsed",
                    start_idx, end_idx, len(parsed),
                )
                return parsed
            except Exception as e:
                logger.warning(
                    "[DEP_CLASSIFY] Batch %d-%d failed: %s", start_idx, end_idx, e
                )
                return []

        try:
            per_batch: List[List[Dict]] = await asyncio.gather(
                *[_dep_batch(b, i) for i, b in enumerate(batches)]
            )
        except Exception as e:
            logger.warning("[DEP_CLASSIFY] Parallel gather failed: %s", e, exc_info=True)
            return []

        results: List[Dict] = [item for br in per_batch for item in br]
        logger.info(
            "[DEP_CLASSIFY] Done — %d/%d tests classified by LLM",
            len(results), total,
        )
        return results

    def _parse_dependency_classification_json(
        self, content: str, batch: List[Dict]
    ) -> List[Dict]:
        """
        Parse { classifications: [{test_id, label, confidence, reason}] }.

        Falls back gracefully:
        - Unknown/missing label → rule_hint value (or 'cross_dependent')
        - Unparseable JSON     → empty list (caller uses rule fallback)
        """
        _VALID_LABELS = {"Independent", "CrossDependent"}
        _VALID_CONF   = {"high", "medium", "low"}

        # Build expected test_id set for this batch
        batch_ids = {str(t.get("test_id", "")) for t in batch}

        try:
            json_str = content.strip()
            start = json_str.find("{")
            end   = json_str.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = json_str[start : end + 1]
            data  = json.loads(json_str)
            items = data.get("classifications", [])
        except Exception as e:
            logger.warning("[DEP_CLASSIFY] JSON parse error: %s — raw: %.200s", e, content)
            return []

        out: List[Dict] = []
        seen: set = set()
        for item in items:
            tid    = str(item.get("test_id") or "").strip()
            label  = str(item.get("label") or "").strip()
            conf   = str(item.get("confidence") or "low").strip().lower()
            reason = str(item.get("reason") or "").strip()

            if not tid or tid in seen:
                continue
            if tid not in batch_ids:
                continue  # LLM hallucinated an id not in this batch
            seen.add(tid)

            # Normalise label
            if label not in _VALID_LABELS:
                # try case-insensitive match
                label_map = {l.lower(): l for l in _VALID_LABELS}
                label = label_map.get(label.lower(), "")
            if label not in _VALID_LABELS:
                logger.debug("[DEP_CLASSIFY] Unknown label %r for %s — using rule_hint", label, tid)
                continue  # caller fills gap with rule_hint

            if conf not in _VALID_CONF:
                conf = "low"

            out.append({
                "test_id":    tid,
                "label":      label,         # "Independent" | "CrossDependent"
                "confidence": conf,
                "reason":     reason,
                "source":     "llm",
            })

        return out

    # ──────────────────────────────────────────────────────────────────────────

    def _parse_simple_classification_json(self, content: str, expected: int) -> List[Dict]:
        """Parse {classifications:[{test_id,label,reason}]} with loose extraction."""
        try:
            # Try to locate JSON block heuristically
            json_str = content.strip()
            fence_start = json_str.find("{")
            fence_end = json_str.rfind("}")
            if fence_start != -1 and fence_end != -1 and fence_end > fence_start:
                json_str = json_str[fence_start : fence_end + 1]
            data = json.loads(json_str)
            items = data.get("classifications", [])
            out = []
            for it in items:
                tid = it.get("test_id")
                label = str(it.get("label", "")).strip()
                reason = it.get("reason") or ""
                if tid and label in ("Critical", "High", "NonRelevant"):
                    out.append({"test_id": tid, "label": label, "reason": reason})
            # If nothing parsed but we expected something, return empty list (fail open upstream)
            return out
        except Exception as e:
            logger.warning("Failed to parse classification JSON: %s", e)
            return []
