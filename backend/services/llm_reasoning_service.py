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
        
        try:
            # Build prompt
            prompt = self._build_relevance_prompt(diff_content, candidates_to_assess)
            
            # Call LLM
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert software testing assistant. You MUST respond with valid JSON containing assessments for ALL test cases provided. Do not omit any tests, even if they have low relevance scores. Your response must be a valid JSON object starting with { and ending with }. NEVER return an empty assessments array - always provide scores for all tests, even if they are low (0.1-0.3)."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,  # Lower temperature for more consistent scoring
                max_tokens=8000  # Increased to handle 20 tests with full explanations
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
        
        prompt = f"""You are analyzing code changes and must assess the relevance of {len(test_candidates)} test cases.

Code Changes (Git Diff):
```
{truncated_diff}
```

Test Cases to Assess (YOU MUST ASSESS ALL {len(test_candidates)} TESTS):
{chr(10).join(test_list)}

CRITICAL INSTRUCTIONS:
1. You MUST provide an assessment for EVERY SINGLE test case listed above ({len(test_candidates)} total)
2. Do NOT omit any tests, even if they seem unrelated
3. For each test, provide a relevance score from 0.0 to 1.0:
   - 0.0-0.2: Very low relevance (test is unrelated to changes)
   - 0.3-0.5: Low to medium relevance (test may be tangentially related)
   - 0.6-0.8: High relevance (test is likely related to changes)
   - 0.9-1.0: Very high relevance (test directly validates changed functionality)
4. Provide a brief explanation (1-2 sentences) for each test

IMPORTANT: Low scores (0.0-0.3) are VALID and REQUIRED. Do not skip tests just because they have low relevance.
The scoring system needs scores for ALL tests to calculate confidence properly.

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
            assessments = data.get('assessments', [])
            
            # Validate that we got assessments
            if not assessments or len(assessments) == 0:
                logger.error(f"LLM returned empty assessments array. Expected {len(test_candidates)} assessments.")
                logger.error(f"LLM response content (first 1000 chars): {content[:1000]}")
                logger.error(f"Parsed JSON data: {data}")
                # This is a critical issue - LLM should assess all tests
                # Create default assessments with low scores as fallback
                logger.warning(f"Creating fallback assessments with default low scores for all {len(test_candidates)} tests")
                for test in test_candidates:
                    test_id = test.get('test_id')
                    assessments.append({
                        'test_id': test_id,
                        'score': 0.2,  # Default low score
                        'explanation': f'LLM returned empty response - assigned default low relevance score'
                    })
            
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
