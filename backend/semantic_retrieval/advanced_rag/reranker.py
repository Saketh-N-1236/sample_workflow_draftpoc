"""
LLM Re-ranking Service for Advanced RAG.

Re-ranks semantic search results using LLM to assess relevance
beyond similarity scores.
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


class RerankerService:
    """Service for re-ranking semantic search results with LLM."""
    
    def __init__(self):
        """Initialize reranker service."""
        self.settings = get_settings()
        try:
            self.llm_provider = LLMFactory.create_provider(self.settings)
            logger.info(
                f"Re-ranking Service initialized | "
                f"Provider: {self.llm_provider.provider_name.upper()} | "
                f"Model: {self.llm_provider.model_name}"
            )
        except Exception as e:
            logger.error(f"Re-ranking Service initialization failed: {e}")
            self.llm_provider = None
    
    async def rerank_with_llm(
        self,
        candidates: List[Dict],
        diff_content: Optional[str] = None,
        query_understanding: Optional[Dict] = None,
        top_k: int = 50
    ) -> List[Dict]:
        """
        Re-rank semantic search candidates using LLM relevance assessment.
        
        Args:
            candidates: List of test candidate dicts with:
                - test_id: str
                - method_name: str
                - class_name: Optional[str]
                - similarity: float (from vector search)
                - Other test metadata
            diff_content: Optional git diff content for context
            query_understanding: Optional understanding dict from QueryUnderstandingService
            top_k: Number of top candidates to re-rank (default: 50)
        
        Returns:
            Re-ranked list of candidates with:
                - All original fields
                - rerank_score: float (0.0-1.0) - LLM relevance score
                - rerank_reasoning: str - LLM explanation
        """
        if not self.llm_provider:
            logger.warning("LLM provider not available, returning candidates sorted by similarity")
            return sorted(candidates, key=lambda x: x.get('similarity', 0), reverse=True)
        
        if not candidates:
            return []
        
        # Limit to top K candidates for re-ranking
        candidates_to_rerank = candidates[:top_k]
        
        if len(candidates_to_rerank) == 0:
            return candidates
        
        # For very large candidate sets (>100), process in batches to avoid timeouts
        # Batch size of 50 is optimal for Gemini API performance
        batch_size = 50
        if len(candidates_to_rerank) > batch_size:
            logger.info(f"Processing {len(candidates_to_rerank)} candidates in batches of {batch_size}")
            all_reranked = []
            remaining_candidates = candidates[top_k:] if len(candidates) > top_k else []
            
            for i in range(0, len(candidates_to_rerank), batch_size):
                batch = candidates_to_rerank[i:i + batch_size]
                try:
                    batch_reranked = await self._rerank_batch(batch, diff_content, query_understanding)
                    all_reranked.extend(batch_reranked)
                except Exception as e:
                    logger.warning(f"Batch {i//batch_size + 1} re-ranking failed: {e}, using similarity scores")
                    # Fallback: use similarity scores for this batch
                    for candidate in batch:
                        candidate['rerank_score'] = candidate.get('similarity', 0.0)
                        candidate['rerank_reasoning'] = 'Batch re-ranking failed, using similarity score'
                    all_reranked.extend(batch)
            
            # Sort all reranked by rerank_score (descending)
            all_reranked.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
            
            # Append remaining candidates (keep original similarity order)
            final_results = all_reranked + remaining_candidates
            
            logger.info(f"Re-ranking completed: re-ranked {len(all_reranked)} candidates in batches")
            return final_results
        else:
            # Small batch - process normally
            try:
                reranked = await self._rerank_batch(candidates_to_rerank, diff_content, query_understanding)
                
                # Combine with remaining candidates (beyond top_k)
                remaining_candidates = candidates[top_k:] if len(candidates) > top_k else []
                
                # Sort reranked by rerank_score (descending)
                reranked.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
                
                # Append remaining candidates (keep original similarity order)
                final_results = reranked + remaining_candidates
                
                logger.info(f"Re-ranking completed: re-ranked {len(reranked)} candidates")
                return final_results
                
            except Exception as e:
                logger.error(f"Re-ranking failed: {e}", exc_info=True)
                # Fallback: return sorted by similarity, but mark with default rerank_score
                fallback_results = []
                for candidate in candidates:
                    candidate_copy = candidate.copy()
                    candidate_copy['rerank_score'] = candidate.get('similarity', 0.0)
                    candidate_copy['rerank_reasoning'] = 'Re-ranking failed, using similarity score'
                    fallback_results.append(candidate_copy)
                return sorted(fallback_results, key=lambda x: x.get('similarity', 0), reverse=True)
    
    async def _rerank_batch(
        self,
        batch: List[Dict],
        diff_content: Optional[str] = None,
        query_understanding: Optional[Dict] = None
    ) -> List[Dict]:
        """Re-rank a batch of candidates (internal method)."""
        try:
            # Build prompt
            prompt = self._build_reranking_prompt(batch, diff_content, query_understanding)
            
            # Calculate max_tokens dynamically based on number of candidates
            # Estimate: ~120 tokens per test (test_id, score, reasoning)
            # Add 2000 tokens for prompt overhead
            estimated_tokens = len(batch) * 120 + 2000
            # Cap at 32000 (most models' limit) and ensure minimum of 4000
            max_tokens = min(max(estimated_tokens, 4000), 32000)
            
            # Call LLM
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert software testing assistant. You MUST respond with valid JSON containing relevance assessments for ALL test cases provided. Assess how relevant each test is to the code changes, considering both semantic similarity and actual test coverage."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,  # Lower temperature for more consistent scoring
                max_tokens=max_tokens  # Dynamic based on number of candidates
            )
            
            response = await self.llm_provider.chat_completion(request)
            content = response.content
            
            # Parse LLM response
            reranked = self._parse_reranking_response(content, batch)
            
            return reranked
            
        except Exception as e:
            logger.error(f"Batch re-ranking failed: {e}", exc_info=True)
            raise
    
    def _build_reranking_prompt(
        self,
        candidates: List[Dict],
        diff_content: Optional[str] = None,
        understanding: Optional[Dict] = None
    ) -> str:
        """Build prompt for re-ranking."""
        
        # Truncate diff if too long
        diff_snippet = ""
        if diff_content:
            diff_snippet = diff_content[:3000]  # First 3000 chars
            if len(diff_content) > 3000:
                diff_snippet += "\n... (diff truncated)"
        
        # Build understanding summary
        understanding_summary = ""
        if understanding:
            primary_intent = understanding.get('primary_intent', '')
            related_concepts = understanding.get('related_concepts', [])
            understanding_summary = f"""
Context Understanding:
- Primary Intent: {primary_intent}
- Related Concepts: {', '.join(related_concepts[:10]) if related_concepts else 'None'}
"""
        
        # Format candidates
        test_list = []
        for i, test in enumerate(candidates, 1):
            test_id = test.get('test_id', 'unknown')
            class_name = test.get('class_name', '')
            method_name = test.get('method_name', '')
            similarity = test.get('similarity', 0)
            description = test.get('description', '')
            
            test_info = f"{i}. Test ID: {test_id}\n"
            if class_name:
                test_info += f"   Class: {class_name}\n"
            test_info += f"   Method: {method_name}\n"
            test_info += f"   Similarity Score: {similarity:.3f}\n"
            if description:
                test_info += f"   Description: {description[:200]}\n"
            
            test_list.append(test_info)
        
        test_ids_list = [f'"{test.get("test_id", "unknown")}"' for test in candidates]
        
        prompt = f"""You are analyzing {len(candidates)} test candidates that were found by semantic search. Re-rank them based on their actual relevance to the code changes.

Code Changes (Git Diff):
```
{diff_snippet if diff_snippet else 'No diff content provided'}
```
{understanding_summary}

Test Candidates to Re-rank (YOU MUST ASSESS ALL {len(candidates)} TESTS):
{chr(10).join(test_list)}

CRITICAL INSTRUCTIONS:
1. You MUST provide an assessment for EVERY SINGLE test case listed above ({len(candidates)} total)
2. Consider both semantic similarity AND actual test coverage of the changed functionality
3. For each test, provide a relevance score from 0.0 to 1.0:
   - 0.0-0.3: Low relevance (test is unrelated or only tangentially related)
   - 0.4-0.6: Medium relevance (test may be related but doesn't directly test changed code)
   - 0.7-0.9: High relevance (test directly validates changed functionality)
   - 0.95-1.0: Very high relevance (test is a perfect match for the changes)
4. Provide a brief explanation (1 sentence) for each test explaining why it's relevant or not
5. Filter out false positives - tests that match semantically but don't actually test the changed code

You MUST return a JSON object with exactly {len(candidates)} assessments. The JSON must have this structure:

{{
  "assessments": [
    {{
      "test_id": "{candidates[0].get('test_id', 'test_0001')}",
      "score": 0.85,
      "reasoning": "This test directly validates the changed authentication logic"
    }},
    {{
      "test_id": "{candidates[1].get('test_id', 'test_0002') if len(candidates) > 1 else 'test_0002'}",
      "score": 0.25,
      "reasoning": "This test is only tangentially related"
    }}
    ... (continue for all {len(candidates)} tests)
  ]
}}

REQUIRED TEST IDs (you must include all of these):
{', '.join(test_ids_list)}

Your response must be valid JSON starting with {{ and ending with }}. Include all {len(candidates)} test IDs in the assessments array.
"""
        return prompt
    
    def _parse_reranking_response(self, content: str, candidates: List[Dict]) -> List[Dict]:
        """Parse LLM response and merge with candidates."""
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
            
            # Strategy 2: Find JSON object with "assessments"
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
            assessments = data.get('assessments', [])
            
            # Create map of test_id -> assessment
            assessment_map = {}
            for assessment in assessments:
                test_id = assessment.get('test_id')
                if test_id:
                    score = float(assessment.get('score', 0.0))
                    score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
                    assessment_map[test_id] = {
                        'rerank_score': score,
                        'rerank_reasoning': assessment.get('reasoning', 'No reasoning provided')
                    }
            
            # Merge assessments with candidates
            reranked = []
            for candidate in candidates:
                test_id = candidate.get('test_id')
                candidate_copy = candidate.copy()
                
                if test_id in assessment_map:
                    candidate_copy['rerank_score'] = assessment_map[test_id]['rerank_score']
                    candidate_copy['rerank_reasoning'] = assessment_map[test_id]['rerank_reasoning']
                else:
                    # Default scores if not in LLM response
                    candidate_copy['rerank_score'] = candidate.get('similarity', 0.0)
                    candidate_copy['rerank_reasoning'] = 'Not assessed by LLM'
                
                reranked.append(candidate_copy)
            
            return reranked
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse reranking response as JSON: {e}")
            logger.error(f"Response content (first 500 chars): {content[:500]}")
            # Fallback: return candidates with similarity as rerank_score
            return [
                {**c, 'rerank_score': c.get('similarity', 0.0), 'rerank_reasoning': 'Failed to parse LLM response'}
                for c in candidates
            ]
        except Exception as e:
            logger.error(f"Error parsing reranking response: {e}", exc_info=True)
            # Fallback: return candidates with similarity as rerank_score
            return [
                {**c, 'rerank_score': c.get('similarity', 0.0), 'rerank_reasoning': 'Error parsing response'}
                for c in candidates
            ]
