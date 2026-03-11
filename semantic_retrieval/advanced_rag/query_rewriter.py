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


class QueryRewriterService:
    """Service for rewriting queries with multiple perspectives."""
    
    def __init__(self):
        """Initialize query rewriter service."""
        self.settings = get_settings()
        try:
            self.llm_provider = LLMFactory.create_provider(self.settings)
            logger.info(f"Query Rewriter Service initialized with LLM provider: {self.llm_provider.provider_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM provider: {e}. Query rewriting will be disabled.")
            self.llm_provider = None
    
    async def rewrite_queries(
        self,
        original_query: str,
        query_understanding: Dict,
        num_variations: int = 3
    ) -> List[str]:
        """
        Generate multiple query variations from different perspectives.
        
        Args:
            original_query: Original query string
            query_understanding: Understanding dict from QueryUnderstandingService
            num_variations: Number of query variations to generate (default: 3)
        
        Returns:
            List of rewritten query strings
        """
        if not self.llm_provider:
            logger.warning("LLM provider not available, returning original query")
            return [original_query]
        
        if not original_query or not query_understanding:
            return [original_query]
        
        try:
            # Build prompt
            prompt = self._build_rewriting_prompt(original_query, query_understanding, num_variations)
            
            # Call LLM
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at rewriting search queries for better semantic matching. You MUST respond with valid JSON containing an array of query variations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5,  # Medium temperature for creativity
                max_tokens=1500
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
        understanding: Dict,
        num_variations: int
    ) -> str:
        """Build prompt for query rewriting."""
        
        primary_intent = understanding.get('primary_intent', '')
        related_concepts = understanding.get('related_concepts', [])
        test_patterns = understanding.get('test_patterns', [])
        change_type = understanding.get('change_type', 'modified')
        
        concepts_str = ', '.join(related_concepts[:10]) if related_concepts else 'None'
        patterns_str = ', '.join(test_patterns[:5]) if test_patterns else 'None'
        
        prompt = f"""Rewrite the following search query into {num_variations} different variations for semantic test search.

Original Query:
{original_query}

Context Understanding:
- Primary Intent: {primary_intent}
- Related Concepts: {concepts_str}
- Test Patterns: {patterns_str}
- Change Type: {change_type}

Generate {num_variations} query variations from different perspectives:

1. **Technical Perspective**: Focus on technical implementation details, APIs, methods
2. **Behavioral Perspective**: Focus on user behavior, workflows, use cases
3. **Error/Edge Case Perspective**: Focus on error handling, edge cases, failure scenarios
4. **Integration Perspective**: Focus on integration points, dependencies, interactions

Each variation should:
- Use different wording but maintain the same core meaning
- Include related concepts and synonyms where appropriate
- Be optimized for finding relevant test cases
- Be concise (1-2 sentences or short phrases)

Respond with a JSON object in this exact format:
{{
  "variations": [
    "First query variation",
    "Second query variation",
    "Third query variation"
  ]
}}

You MUST generate exactly {num_variations} variations. Your response must be valid JSON starting with {{ and ending with }}.
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
            
            # Parse JSON
            data = json.loads(json_str)
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
