"""
LLM Reasoning Service for Test Relevance Assessment

This service uses LLM to assess the relevance of test candidates based on git diff.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging
import json
import re

# Add backend/ to path: backend/services/llm_reasoning_service.py -> parent.parent = backend/
_backend_path = Path(__file__).parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

from llm.factory import LLMFactory
from llm.models import LLMRequest, LLMResponse
from config.settings import get_settings

logger = logging.getLogger(__name__)


class LLMReasoningService:
    """Service for LLM-based test relevance assessment."""
    
    def __init__(self):
        """Initialize LLM reasoning service."""
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
    
    async def assess_test_relevance(
        self,
        diff_content: str,
        test_candidates: List[Dict],
        top_n: int = 20
    ) -> List[Dict]:
        """
        Assess test relevance using LLM reasoning.
        
        Args:
            diff_content: Git diff content
            test_candidates: List of test candidate dictionaries with:
                - test_id: str
                - class_name: Optional[str]
                - method_name: str
                - test_file_path: str
                - match_reasons: Optional[List[str]] - reasons why test was matched
            top_n: Number of top candidates to assess (default: 20)
        
        Returns:
            List of dictionaries with:
                - test_id: str
                - llm_score: float (0.0-1.0)
                - llm_explanation: str
        """
        if not self.llm_provider:
            logger.warning("LLM provider not available, skipping LLM reasoning")
            return []
        
        if not test_candidates:
            return []
        
        # Limit to top N candidates
        candidates_to_assess = test_candidates[:top_n]
        _max_tokens = min(12000, 2000 + top_n * 280)

        try:
            # Build prompt
            prompt = self._build_relevance_prompt(diff_content, candidates_to_assess)
            
            # Call LLM
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert in mapping code changes to tests. "
                            "Score how likely each test needs to run given the diff — either because it directly "
                            "exercises the new/changed code, OR because it guards existing behavior in the same "
                            "file that could be broken by the change (regression guard). "
                            "Penalize same-domain-but-different-FILE matches (semantic false positives). "
                            "Never penalize same-file tests just because they test a different action/method "
                            "than the one that changed — those are regression guards and should score 0.70+. "
                            "You MUST return valid JSON with an assessment for EVERY test id provided. "
                            "Never return an empty assessments array."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,  # Lower temperature for more consistent scoring
                max_tokens=_max_tokens,
            )
            
            response = await self.llm_provider.chat_completion(request)
            content = response.content
            
            logger.debug(f"LLM raw response (first 1000 chars): {content[:1000]}")
            
            # Parse LLM response
            results = self._parse_llm_response(content, candidates_to_assess)
            
            # Store raw response in results for access later
            # Add raw_response to each result for tracking
            for result in results:
                result['raw_response'] = content[:2000]  # Store first 2000 chars
            
            logger.info(f"LLM reasoning completed: assessed {len(results)} tests")
            return results
            
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}", exc_info=True)
            # Return empty scores on failure
            return []
    
    def _build_relevance_prompt(self, diff_content: str, test_candidates: List[Dict]) -> str:
        """Build prompt for LLM relevance assessment."""
        
        # Truncate diff if too long (keep first 8000 chars for better context)
        truncated_diff = diff_content[:8000]
        if len(diff_content) > 8000:
            truncated_diff += "\n... (diff truncated for brevity, but all key changes are included)"
        
        # Format test candidates
        test_list = []
        for i, test in enumerate(test_candidates, 1):
            test_id = test.get('test_id', 'unknown')
            class_name = test.get('class_name', '')
            method_name = test.get('method_name', '')
            file_path = test.get('test_file_path', '')
            match_reasons = test.get('match_reasons', [])
            
            test_info = f"{i}. Test ID: {test_id}\n"
            if class_name:
                test_info += f"   Class: {class_name}\n"
            test_info += f"   Method: {method_name}\n"
            test_info += f"   File: {file_path}\n"
            if match_reasons:
                test_info += f"   Match Reasons: {', '.join(match_reasons[:3])}\n"
            
            test_list.append(test_info)
        
        # Build a more explicit prompt that requires all tests to be assessed
        test_ids_list = [f'"{test.get("test_id", "unknown")}"' for test in test_candidates]
        
        prompt = f"""You are analyzing **production code changes** and must score {len(test_candidates)} **test** candidates.

## Code changes (git diff)
```
{truncated_diff}
```

## Tests to score (assess ALL {len(test_candidates)} — none may be omitted)
{chr(10).join(test_list)}

## Scoring rubric (read carefully)
Infer the **changed file paths and symbols** from the diff (added/removed/modified functions, classes, hooks, constants, reducer cases). You do not need a scenario name.

**0.85 – 1.0 — Direct**
The test almost certainly executes, imports, or asserts behavior of code in the **same files or symbols** that changed, OR it directly tests the **new symbol/feature** introduced in the diff.

**0.70 – 0.84 — Regression guard (same file, different symbol)**
The test covers **other behavior in the same changed file** (e.g. a different action in the same reducer, a different method in the same class, a different export from the same module).
Even though the test does not directly test the new/changed symbol, it **must run** to confirm the change did not accidentally break existing behavior.
→ Apply this band when: the test class/describe name or file path references the **same module** as the changed file (e.g. "paymentReducer" tests when `paymentReducer.js` changed).
→ This is especially important for **additive diffs** (new case/method added, nothing removed).

**0.55 – 0.69 — Strong indirect**
The test targets a **named dependency** that appears in the diff (e.g. same helper, shared constant, or barrel import the diff edits) even if the test file path and class differ.

**0.25 – 0.50 — Weak / thematic**
Same **product area** (e.g. "auth", "checkout") but the test does **not** clearly reference the changed files/symbols. Typical semantic-search false positive.

**0.0 – 0.20 — Unrelated**
Different feature, different module, or only vague vocabulary overlap. The test would not be expected to fail from this diff.

**Match type hints:**
- If match reasons show `exact`, `function_level`, or `direct_file` → the static code analyser confirmed a dependency link. Treat this as strong evidence; score at least 0.55 unless the test is clearly in an unrelated file.
- If match reasons show only `semantic` → be **extra skeptical**. Require explicit overlap with changed paths/symbols for scores above 0.35. Semantic matches can be vocabulary false positives (e.g. two different reducers that use similar words).

## Retrieval context
These candidates were already retrieved by embedding search and static analysis; this step scores **what you are given**.
- **Semantic false positives** (same domain, different file) are expected — penalize them.
- **Regression guards** (same file, different symbol) are expected and valuable — reward them.
- **False positive (scoring)** = giving a high score to a test in a **completely different file/module**.
- **False negative (scoring)** = giving a low score to a test that **covers the same file/module** as the diff.

## Rules
1. One assessment per test id; **never** omit a test.
2. Uncertainty bias differs by match type:
   - **AST-confirmed** (match reasons: exact/function_level/direct_file): when uncertain → score **≥ 0.55**. The static analyser already confirmed a code link; trust that evidence.
   - **Semantic-only** (match reasons: only semantic/colocated): when uncertain → score **≤ 0.35**. Semantic similarity alone can be misleading.
3. One short explanation per test (what overlaps or why it misses the diff).
4. For **additive diffs** (diff only adds new code, nothing removed): all tests for the changed file are regression guards even if they test pre-existing behavior — score them 0.70+.

You MUST return a JSON object with exactly {len(test_candidates)} assessments. The JSON must have this structure:

{{
  "assessments": [
    {{
      "test_id": "{test_candidates[0].get('test_id', 'test_0001')}",
      "score": 0.75,
      "explanation": "This test is relevant because..."
    }},
    {{
      "test_id": "{test_candidates[1].get('test_id', 'test_0002') if len(test_candidates) > 1 else 'test_0002'}",
      "score": 0.25,
      "explanation": "This test has low relevance because..."
    }}
    ... (continue for all {len(test_candidates)} tests)
  ]
}}

REQUIRED TEST IDs (you must include all of these):
{', '.join(test_ids_list)}

Your response must be valid JSON starting with {{ and ending with }}. Include all {len(test_candidates)} test IDs in the assessments array.

CRITICAL: Do NOT return an empty assessments array {{"assessments": []}}. Even if all tests have low relevance (score 0.1-0.3), you must still provide scores for all of them. An empty array is NOT acceptable.
"""
        return prompt
    
    def _parse_llm_response(self, content: str, test_candidates: List[Dict]) -> List[Dict]:
        """Parse LLM response to extract scores and explanations."""
        results = []
        
        try:
            if not content or not content.strip():
                logger.warning("LLM response content is empty")
                raise ValueError("Empty response content")
            
            # Try to extract JSON from response
            json_str = None
            extraction_method = None
            
            # Strategy 1: Look for JSON block in markdown code fences
            # Find the code fence start
            code_fence_match = re.search(r'```(?:json)?\s*\{', content, re.DOTALL)
            if code_fence_match:
                # Find the start of JSON (after code fence)
                start_pos = code_fence_match.end() - 1  # Position of '{'
                # Find matching closing brace
                brace_count = 0
                end_pos = start_pos
                for i in range(start_pos, len(content)):
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break
                if brace_count == 0:
                    json_str = content[start_pos:end_pos]
                    extraction_method = "code_fence"
                    logger.debug(f"Found JSON in code fence: {json_str[:200]}...")
            
            # Strategy 2: Find JSON object directly (look for opening brace followed by "assessments")
            if not json_str:
                json_match = re.search(r'\{[^{}]*"assessments"', content, re.DOTALL)
                if json_match:
                    start_pos = json_match.start()
                    brace_count = 0
                    end_pos = start_pos
                    for i in range(start_pos, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                    if brace_count == 0:
                        json_str = content[start_pos:end_pos]
                        extraction_method = "direct_object"
                        logger.debug(f"Found JSON object directly: {json_str[:200]}...")
            
            # Strategy 3: Find any JSON object (greedy match with brace counting)
            if not json_str:
                first_brace = content.find('{')
                if first_brace != -1:
                    brace_count = 0
                    end_pos = first_brace
                    for i in range(first_brace, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                    if brace_count == 0:
                        json_str = content[first_brace:end_pos]
                        extraction_method = "fallback_object"
                        logger.debug(f"Found JSON object (fallback): {json_str[:200]}...")
            
            # Strategy 4: Try parsing entire content (might be pure JSON)
            if not json_str:
                json_str = content.strip()
                extraction_method = "entire_content"
                logger.debug(f"Using entire content as JSON: {json_str[:200]}...")
            
            if not json_str:
                raise ValueError("Could not extract JSON from LLM response")
            
            # Clean up JSON string (remove any leading/trailing whitespace or markdown)
            json_str = json_str.strip()
            # Remove markdown code fence markers if still present (more aggressive cleanup)
            json_str = re.sub(r'^```(?:json)?\s*', '', json_str, flags=re.MULTILINE)
            json_str = re.sub(r'\s*```\s*$', '', json_str, flags=re.MULTILINE)
            json_str = json_str.strip()
            
            logger.debug(f"JSON extraction method: {extraction_method}")
            logger.debug(f"Extracted JSON length: {len(json_str)}")
            logger.debug(f"Extracted JSON (first 500 chars): {json_str[:500]}")
            
            # Try to parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                # Log detailed error information
                logger.error(f"JSON parsing failed at position {e.pos}: {e.msg}")
                logger.error(f"JSON string length: {len(json_str)}")
                if e.pos < len(json_str):
                    logger.error(f"JSON string around error (pos {e.pos}): {json_str[max(0, e.pos-50):e.pos+50]}")
                logger.error(f"Full JSON string: {json_str}")
                logger.error(f"Original content length: {len(content)}")
                logger.error(f"Original content (first 1000 chars): {content[:1000]}")
                raise
            assessments = data.get("assessments", [])

            if not assessments:
                logger.error(
                    "LLM returned empty assessments array. Expected %s assessments; "
                    "using llm_score=0 for candidates (no synthetic scores).",
                    len(test_candidates),
                )
                logger.error(
                    "LLM response content (first 1000 chars): %s", content[:1000]
                )
                logger.error("Parsed JSON data: %s", data)

            # Create a map of test_id -> assessment
            assessment_map = {}
            for assessment in assessments:
                test_id = assessment.get('test_id')
                if test_id:
                    score = float(assessment.get('score', 0.0))
                    # Ensure score is in valid range
                    score = max(0.0, min(1.0, score))
                    assessment_map[test_id] = {
                        'llm_score': score,
                        'llm_explanation': assessment.get('explanation', 'No explanation provided')
                    }
                else:
                    logger.warning(f"Assessment missing test_id: {assessment}")
            
            # Build results for all candidates
            # Log warning if assessments are missing
            missing_assessments = []
            for test in test_candidates:
                test_id = test.get('test_id')
                if test_id in assessment_map:
                    results.append({
                        'test_id': test_id,
                        **assessment_map[test_id]
                    })
                else:
                    # Test not in LLM response - log warning and use default
                    missing_assessments.append(test_id)
                    results.append({
                        'test_id': test_id,
                        'llm_score': 0.0,
                        'llm_explanation': f'Not included in LLM response (expected {len(test_candidates)} assessments, got {len(assessments)})'
                    })
            
            # Log warning if some tests were not assessed
            if missing_assessments:
                logger.warning(f"LLM did not assess {len(missing_assessments)} out of {len(test_candidates)} tests")
                logger.warning(f"Missing test IDs (first 5): {missing_assessments[:5]}")
                logger.warning(f"LLM returned {len(assessments)} assessments but {len(test_candidates)} were expected")
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.warning(f"LLM response content (first 1000 chars): {content[:1000]}")
            logger.warning(f"LLM response content length: {len(content)}")
            # Fallback: return empty scores
            for test in test_candidates:
                results.append({
                    'test_id': test.get('test_id'),
                    'llm_score': 0.0,
                    'llm_explanation': f'Failed to parse LLM response: {str(e)}'
                })
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}", exc_info=True)
            # Fallback: return empty scores
            for test in test_candidates:
                results.append({
                    'test_id': test.get('test_id'),
                    'llm_score': 0.0,
                    'llm_explanation': 'Error parsing LLM response'
                })
        
        return results
