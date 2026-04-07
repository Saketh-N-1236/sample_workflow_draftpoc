"""
Query Rewriting Service for Advanced RAG.

Generates multiple query variations from different perspectives
to improve semantic search coverage.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging
import json
import re

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from llm.factory import LLMFactory
from llm.models import LLMRequest
from config.settings import get_settings

logger = logging.getLogger(__name__)


def _repair_json_invalid_string_escapes(text: str) -> str:
    """
    Fix invalid backslash escapes inside JSON string literals.

    Chat models often emit regex fragments like /\\s/g inside JSON strings; JSON only allows
    \\\", \\\\\\, \\/, \\b, \\f, \\n, \\r, \\t, \\uXXXX. Sequences like \\s are invalid and
    break json.loads — double the backslash so the payload becomes valid.
    """
    result: List[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if not in_string:
            if ch == '"':
                in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = False
            result.append(ch)
            i += 1
            continue
        if ch == "\\":
            if i + 1 >= len(text):
                result.append("\\\\")
                i += 1
                continue
            nxt = text[i + 1]
            if nxt in ('"', "\\", "/", "b", "f", "n", "r", "t"):
                result.append(ch)
                result.append(nxt)
                i += 2
                continue
            if nxt == "u":
                result.append(ch)
                result.append(nxt)
                i += 2
                hexdigits = 0
                while i < len(text) and hexdigits < 4 and text[i] in "0123456789abcdefABCDEF":
                    result.append(text[i])
                    i += 1
                    hexdigits += 1
                continue
            result.append("\\\\")
            result.append(nxt)
            i += 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _loads_rewriter_json(json_str: str) -> dict:
    """Parse rewriter JSON; repair invalid string escapes on JSONDecodeError."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as first_err:
        repaired = _repair_json_invalid_string_escapes(json_str)
        try:
            data = json.loads(repaired)
            logger.info(
                "Query rewriter JSON parsed after repairing invalid string escapes (%s)",
                first_err,
            )
            return data
        except json.JSONDecodeError:
            raise first_err


class QueryRewriterService:
    """Service for rewriting queries with multiple perspectives."""
    
    def __init__(self):
        """Initialize query rewriter service."""
        self.settings = get_settings()
        try:
            self.llm_provider = LLMFactory.create_provider(self.settings)
            logger.info(
                f"Query Rewriter Service initialized | "
                f"Provider: {self.llm_provider.provider_name.upper()} | "
                f"Model: {self.llm_provider.model_name}"
            )
        except Exception as e:
            logger.error(f"Query Rewriter Service initialization failed: {e}")
            self.llm_provider = None
    
    async def rewrite_queries(
        self,
        original_query: str,
        query_understanding: Optional[Dict] = None,
        num_variations: int = 3
    ) -> List[str]:
        """
        Generate multiple query variations from different perspectives.
        
        Args:
            original_query: Original query string (e.g. comprehensive diff summary)
            query_understanding: Optional understanding dict; if None/empty, uses original_query only
            num_variations: Number of query variations to generate (default: 3)
        
        Returns:
            List of rewritten query strings
        """
        if not self.llm_provider:
            logger.warning("LLM provider not available, returning original query")
            return [original_query]

        if not original_query:
            return [original_query]

        try:
            # Build prompt (understanding can be None or {} when no Query Understanding step)
            prompt = self._build_rewriting_prompt(original_query, query_understanding or {}, num_variations)
            
            # Call LLM
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You rewrite retrieval queries for vector search over test descriptions. "
                            "Goals: (1) preserve every file path and identifier from the original query "
                            "(including lines inside [Diff symbols] blocks) in EACH variation — copy them verbatim; "
                            "(2) rephrase *around* those anchors, do not broaden to unrelated features; "
                            "(3) output valid JSON only: one object with key \"variations\" (array of strings). "
                            "JSON rules: inside each string value, backslashes must be valid JSON escapes only "
                            "(use \\\\ for a literal backslash). Do not paste raw regex like /\\s/g — say "
                            "'whitespace regex' or double every backslash. No unescaped newlines or tabs inside strings."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.35,
                max_tokens=1800
            )
            
            response = await self.llm_provider.chat_completion(request)
            content = response.content
            
            # Parse LLM response
            rewritten_queries = self._parse_rewritten_queries(content, num_variations)
            
            # Always include original query as first variation
            if original_query not in rewritten_queries:
                rewritten_queries.insert(0, original_query)
            else:
                # Move original to front if it's in the list
                rewritten_queries.remove(original_query)
                rewritten_queries.insert(0, original_query)
            
            logger.info(f"Query rewriting completed: generated {len(rewritten_queries)} query variations")
            return rewritten_queries[:num_variations + 1]  # Include original + variations
            
        except Exception as e:
            logger.error(f"Query rewriting failed: {e}", exc_info=True)
            # Fallback to original query
            return [original_query]
    
    def _build_rewriting_prompt(
        self,
        original_query: str,
        understanding: Optional[Dict],
        num_variations: int
    ) -> str:
        """Build prompt for query rewriting. understanding can be None or empty."""
        understanding = understanding or {}
        primary_intent = understanding.get('primary_intent', '')
        related_concepts = understanding.get('related_concepts', [])
        test_patterns = understanding.get('test_patterns', [])
        change_type = understanding.get('change_type', 'modified')
        
        concepts_str = ', '.join(related_concepts[:10]) if related_concepts else 'None'
        patterns_str = ', '.join(test_patterns[:5]) if test_patterns else 'None'
        
        prompt = f"""Rewrite the following search query into **exactly {num_variations}** alternative strings for semantic (embedding) search over **test cases**.

## Original Query (do not drop information from this)
{original_query}

## Optional context (may be empty; do not override concrete paths/symbols above)
- Primary intent: {primary_intent or "—"}
- Related concepts: {concepts_str}
- Test naming patterns: {patterns_str}
- Change type hint: {change_type}

## Hard requirements
1. **Verbatim anchors**: Every variation MUST still contain **all** path-like substrings from the Original Query (e.g. `src/.../file.ts`) and **all** symbol names listed in a `[Diff symbols]` section if present. Copy those tokens exactly; you may reorder surrounding text.
2. **No topic drift**: Do not introduce unrelated product areas (e.g. do not jump to "login page" if the query is about a specific hook file unless that hook name appears in the Original Query).
3. **Perspectives** (same anchors, different emphasis) — distribute across your {num_variations} strings:
   - Implementation: APIs, functions, hooks, modules named in the query
   - Behavior: observable rules/outcomes implied by the changed code
   - Edge cases: empty input, boundaries, validation failures **for the named symbols**
   - Integration: imports/callees **already mentioned** in the Original Query
4. Each variation: one or two sentences, dense with identifiers; no JSON inside the strings.
5. **Valid JSON**: Each array string must be valid JSON text — double every literal backslash, or avoid raw regex (say "whitespace pattern" instead of slash-backslash-s-slash-g).

Respond with JSON only:
{{
  "variations": [
    "...",
    "...",
    "... (exactly {num_variations} strings total)"
  ]
}}
"""
        return prompt
    
    def _parse_rewritten_queries(self, content: str, expected_count: int) -> List[str]:
        """Parse LLM response to extract rewritten queries."""
        try:
            if not content or not content.strip():
                logger.warning("LLM response content is empty")
                raise ValueError("Empty response content")
            
            # Try to extract JSON from response
            json_str = None
            
            # Strategy 1: Look for JSON block in markdown code fences
            code_fence_match = re.search(r'```(?:json)?\s*\{', content, re.DOTALL)
            if code_fence_match:
                start_pos = code_fence_match.end() - 1
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
            
            # Strategy 2: Find JSON object with "variations"
            if not json_str:
                json_match = re.search(r'\{[^{}]*"variations"', content, re.DOTALL)
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
            
            # Strategy 3: Find any JSON object
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
            
            # Strategy 4: Try parsing entire content
            if not json_str:
                json_str = content.strip()
            
            if not json_str:
                raise ValueError("Could not extract JSON from LLM response")
            
            # Clean up JSON string
            json_str = json_str.strip()
            json_str = re.sub(r'^```(?:json)?\s*', '', json_str, flags=re.MULTILINE)
            json_str = re.sub(r'\s*```\s*$', '', json_str, flags=re.MULTILINE)
            json_str = json_str.strip()
            
            # Parse JSON (with repair for invalid escapes e.g. regex \\s in string values)
            data = _loads_rewriter_json(json_str)
            variations = data.get('variations', [])
            
            # Validate variations
            if not variations or not isinstance(variations, list):
                logger.warning(f"LLM returned invalid variations: {variations}")
                return []
            
            # Filter out empty variations
            variations = [v.strip() for v in variations if v and v.strip()]
            
            if not variations:
                logger.warning("LLM returned empty variations list")
                return []
            
            return variations
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse rewriting response as JSON: {e}")
            logger.error(f"Response content (first 500 chars): {content[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error parsing rewriting response: {e}", exc_info=True)
            return []
