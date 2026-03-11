"""
Query Understanding Service for Advanced RAG.

Analyzes code changes to extract intent, components, and related concepts
for better semantic search queries.
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


class QueryUnderstandingService:
    """Service for understanding query intent from code changes."""
    
    def __init__(self):
        """Initialize query understanding service."""
        self.settings = get_settings()
        try:
            self.llm_provider = LLMFactory.create_provider(self.settings)
            logger.info(f"Query Understanding Service initialized with LLM provider: {self.llm_provider.provider_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM provider: {e}. Query understanding will be disabled.")
            self.llm_provider = None
    
    async def analyze_query_intent(
        self,
        changed_functions: List[Dict],
        file_changes: Optional[List[Dict]] = None,
        diff_content: Optional[str] = None
    ) -> Dict:
        """
        Analyze code changes to extract query intent and understanding.
        
        Args:
            changed_functions: List of dicts with 'module' and 'function' keys
            file_changes: Optional list of file change dictionaries
            diff_content: Optional git diff content for context
        
        Returns:
            Dictionary with:
                - primary_intent: str - Main functionality changed
                - affected_components: List[str] - Classes, modules affected
                - test_patterns: List[str] - Types of tests to look for
                - related_concepts: List[str] - Related terms and synonyms
                - change_type: str - Type of change (new, modified, deleted)
        """
        if not self.llm_provider:
            logger.warning("LLM provider not available, returning basic understanding")
            return self._get_basic_understanding(changed_functions, file_changes)
        
        if not changed_functions:
            return {
                'primary_intent': '',
                'affected_components': [],
                'test_patterns': [],
                'related_concepts': [],
                'change_type': 'unknown'
            }
        
        try:
            # Build prompt
            prompt = self._build_understanding_prompt(changed_functions, file_changes, diff_content)
            
            # Call LLM
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert software engineer analyzing code changes. You MUST respond with valid JSON. Analyze the code changes and extract the primary intent, affected components, test patterns, and related concepts."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=4000  # Increased to prevent truncation
            )
            
            response = await self.llm_provider.chat_completion(request)
            content = response.content
            
            # Parse LLM response
            understanding = self._parse_understanding_response(content)
            
            logger.info(f"Query understanding completed: extracted {len(understanding.get('related_concepts', []))} related concepts")
            return understanding
            
        except Exception as e:
            logger.error(f"Query understanding failed: {e}", exc_info=True)
            # Fallback to basic understanding
            return self._get_basic_understanding(changed_functions, file_changes)
    
    def _build_understanding_prompt(
        self,
        changed_functions: List[Dict],
        file_changes: Optional[List[Dict]] = None,
        diff_content: Optional[str] = None
    ) -> str:
        """Build prompt for query understanding."""
        
        # Build function list
        func_list = []
        for cf in changed_functions[:10]:  # Limit to first 10
            module = cf.get('module', '')
            func = cf.get('function', '')
            func_list.append(f"  - {module}.{func}()")
        
        # Build file changes summary
        file_summary = ""
        if file_changes:
            file_summary = "\nChanged Files:\n"
            for fc in file_changes[:5]:  # Limit to first 5
                file_path = fc.get('file', '')
                status = fc.get('status', 'modified')
                changed_classes = fc.get('changed_classes', [])
                file_summary += f"  - {file_path} ({status})"
                if changed_classes:
                    file_summary += f" [Classes: {', '.join(changed_classes)}]"
                file_summary += "\n"
        
        # Truncate diff if too long
        diff_snippet = ""
        diff_section = ""
        if diff_content:
            diff_snippet = diff_content[:4000]  # First 4000 chars
            if len(diff_content) > 4000:
                diff_snippet += "\n... (diff truncated)"
            # Build diff section separately to avoid backslash in f-string expression
            diff_section = f"Git Diff (context):\n```\n{diff_snippet}\n```"
        
        prompt = f"""Analyze the following code changes and extract structured information for semantic test search.

Changed Functions:
{chr(10).join(func_list)}
{file_summary}

{diff_section}

Extract the following information:

1. **Primary Intent**: What is the main functionality or purpose of these changes? (1-2 sentences)
2. **Affected Components**: List of classes, modules, or components that were changed
3. **Test Patterns**: What types of tests should we look for? (e.g., "unit tests for authentication", "integration tests for API endpoints")
4. **Related Concepts**: List of related terms, synonyms, or concepts that might be used in test descriptions (e.g., if changing "login", include: "authentication", "sign-in", "credentials", "session")
5. **Change Type**: Type of change - "new" (new functionality), "modified" (existing functionality changed), "deleted" (functionality removed), or "refactor" (restructured without changing behavior)

Respond with a JSON object in this exact format:
{{
  "primary_intent": "Brief description of what changed",
  "affected_components": ["component1", "component2"],
  "test_patterns": ["pattern1", "pattern2"],
  "related_concepts": ["concept1", "concept2", "concept3"],
  "change_type": "new|modified|deleted|refactor"
}}

Your response must be valid JSON starting with {{ and ending with }}.
"""
        return prompt
    
    def _parse_understanding_response(self, content: str) -> Dict:
        """Parse LLM response to extract understanding."""
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
            
            # Strategy 2: Find JSON object directly
            if not json_str:
                json_match = re.search(r'\{[^{}]*"primary_intent"', content, re.DOTALL)
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
            
            # Validate and return
            return {
                'primary_intent': data.get('primary_intent', ''),
                'affected_components': data.get('affected_components', []),
                'test_patterns': data.get('test_patterns', []),
                'related_concepts': data.get('related_concepts', []),
                'change_type': data.get('change_type', 'modified')
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse understanding response as JSON: {e}")
            logger.error(f"Response content (first 500 chars): {content[:500]}")
            raise
        except Exception as e:
            logger.error(f"Error parsing understanding response: {e}", exc_info=True)
            raise
    
    def _get_basic_understanding(
        self,
        changed_functions: List[Dict],
        file_changes: Optional[List[Dict]] = None
    ) -> Dict:
        """Get basic understanding without LLM (fallback)."""
        components = []
        for cf in changed_functions:
            module = cf.get('module', '')
            if module:
                components.append(module)
        
        # Extract unique components
        components = list(set(components))
        
        return {
            'primary_intent': f"Changed {len(changed_functions)} function(s) in {len(components)} module(s)",
            'affected_components': components,
            'test_patterns': ['unit tests', 'integration tests'],
            'related_concepts': [],
            'change_type': 'modified'
        }
