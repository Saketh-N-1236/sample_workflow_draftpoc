"""Google Gemini LLM provider implementation."""

import httpx
import asyncio
import re
from typing import List, Dict, Any
from llm.base import LLMProvider
from llm.models import LLMRequest, LLMResponse, EmbeddingRequest, EmbeddingResponse


class GeminiClient(LLMProvider):
    """Google Gemini LLM provider implementation."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-exp"
    ):
        """Initialize Gemini client.
        
        Args:
            api_key: Google Gemini API key
            model: Model name (e.g., gemini-2.0-flash-exp, gemini-1.5-pro)
        """
        self._api_key = api_key
        self._model = model
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"
        # Increased timeout for large re-ranking requests (up to 5 minutes)
        self._client = httpx.AsyncClient(timeout=300.0)
    
    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "gemini"
    
    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model
    
    @property
    def supports_streaming(self) -> bool:
        """Gemini supports streaming."""
        return True
    
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate chat completion using Gemini.
        
        Args:
            request: LLM request with messages and parameters
            
        Returns:
            LLMResponse with generated content
        """
        try:
            # Convert messages to Gemini format
            contents = []
            for msg in request.messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Gemini uses 'user' and 'model' roles
                if role == "system":
                    # System messages are typically prepended to the first user message
                    if contents and contents[-1].get("role") == "user":
                        contents[-1]["parts"][0]["text"] = f"{content}\n\n{contents[-1]['parts'][0]['text']}"
                    else:
                        # If no user message yet, add as first user message
                        contents.append({
                            "role": "user",
                            "parts": [{"text": content}]
                        })
                elif role in ["user", "assistant"]:
                    # Convert 'assistant' to 'model' for Gemini
                    gemini_role = "model" if role == "assistant" else "user"
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": content}]
                    })
            
            # Prepare request
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": request.temperature,
                    "maxOutputTokens": request.max_tokens,
                }
            }
            
            if request.top_p is not None:
                payload["generationConfig"]["topP"] = request.top_p
            
            # Make API call with retry logic for rate limiting
            max_retries = 3
            retry_delay = 1.0  # Start with 1 second
            
            for attempt in range(max_retries):
                try:
                    response = await self._client.post(
                        f"{self._base_url}/models/{self._model}:generateContent",
                        params={"key": self._api_key},
                        json=payload
                    )
                    response.raise_for_status()
                    result = response.json()
                    break  # Success, exit retry loop
                except httpx.HTTPStatusError as e:
                    # Retry on both 429 (rate limit) and 503 (service unavailable)
                    if e.response.status_code in [429, 503]:
                        if attempt < max_retries - 1:
                            # Try to extract retry-after time from error message
                            retry_after = None
                            if e.response.text:
                                try:
                                    error_data = e.response.json()
                                    error_msg = error_data.get('error', {}).get('message', '')
                                    # Look for "Please retry in X.XXs" pattern
                                    match = re.search(r'retry in ([\d.]+)s', error_msg, re.IGNORECASE)
                                    if match:
                                        retry_after = float(match.group(1))
                                except:
                                    pass
                            
                            # Use extracted retry_after or exponential backoff
                            # For 503, use longer initial delay (5 seconds) since it's service overload
                            if e.response.status_code == 503:
                                base_delay = 5.0
                            else:
                                base_delay = retry_delay
                            
                            wait_time = retry_after if retry_after else (base_delay * (2 ** attempt))
                            wait_time = min(wait_time, 60)  # Cap at 60 seconds
                            
                            import logging
                            logger = logging.getLogger(__name__)
                            error_type = "rate limit (429)" if e.response.status_code == 429 else "service unavailable (503)"
                            logger.warning(
                                f"Gemini API {error_type} on attempt {attempt + 1}/{max_retries}. "
                                f"Retrying in {wait_time:.1f}s..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # All retries exhausted, raise the error
                            raise
                    else:
                        # Not a retryable error, raise immediately
                        raise
            
            # Extract response
            candidates = result.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in Gemini response")
            
            # Handle Gemini response structure
            candidate = candidates[0]
            content_obj = candidate.get("content", {})
            parts = content_obj.get("parts", [])
            
            if not parts:
                # Log the full candidate structure for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Gemini candidate structure: {candidate}")
                raise ValueError("No parts in Gemini candidate content")
            
            # Extract text from first part
            content = parts[0].get("text", "")
            
            # Check finish reason to see if response was truncated
            finish_reason = candidate.get("finishReason", "")
            if finish_reason == "MAX_TOKENS":
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Gemini response was truncated due to MAX_TOKENS. Content length: {len(content)}")
                logger.warning(f"Consider increasing max_tokens. Current content: {content[:500]}...")
            
            if not content:
                # Check if there's a finishReason that might explain why content is empty
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Gemini response has no content. Finish reason: {finish_reason}")
                logger.warning(f"Candidate structure: {candidate}")
                if finish_reason:
                    raise ValueError(f"Gemini response has no content. Finish reason: {finish_reason}")
                raise ValueError("Gemini response content is empty")
            
            # Build usage info if available
            usage = None
            if "usageMetadata" in result:
                metadata = result["usageMetadata"]
                usage = {
                    "prompt_tokens": metadata.get("promptTokenCount", 0),
                    "completion_tokens": metadata.get("candidatesTokenCount", 0),
                    "total_tokens": metadata.get("totalTokenCount", 0),
                }
            
            return LLMResponse(
                content=content,
                model=self._model,
                provider=self.provider_name,
                usage=usage
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Gemini API error: {e.response.status_code}"
            if e.response.text:
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get('error', {}).get('message', 'Unknown error')
                    error_msg += f" - {error_detail}"
                    
                    # For 429 and 503 errors, include retry information
                    if e.response.status_code in [429, 503]:
                        retry_match = re.search(r'retry in ([\d.]+)s', error_detail, re.IGNORECASE)
                        if retry_match:
                            retry_seconds = float(retry_match.group(1))
                            error_msg += f"\n* Please wait {retry_seconds:.1f} seconds before retrying."
                        elif e.response.status_code == 503:
                            error_msg += f"\n* Service is temporarily unavailable. Please retry in a few seconds."
                except:
                    error_msg += f" - {e.response.text[:200]}"
            raise Exception(error_msg) from e
        except Exception as e:
            raise Exception(f"Gemini API call failed: {str(e)}") from e
    
    async def get_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Get embeddings using Gemini.
        
        Args:
            request: Embedding request with texts
            
        Returns:
            EmbeddingResponse with embeddings
        """
        try:
            embeddings = []
            
            # Gemini embedding API endpoint
            for text in request.texts:
                payload = {
                    "model": f"models/embedding-001",  # Gemini embedding model
                    "content": {
                        "parts": [{"text": text}]
                    }
                }
                
                response = await self._client.post(
                    f"{self._base_url}/models/embedding-001:embedContent",
                    params={"key": self._api_key},
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                # Extract embedding
                embedding = result.get("embedding", {}).get("values", [])
                if embedding:
                    embeddings.append(embedding)
                else:
                    raise ValueError(f"No embedding returned for text: {text[:50]}...")
            
            return EmbeddingResponse(
                embeddings=embeddings,
                model="embedding-001",
                provider=self.provider_name
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Gemini Embedding API error: {e.response.status_code}"
            if e.response.text:
                try:
                    error_data = e.response.json()
                    error_msg += f" - {error_data.get('error', {}).get('message', 'Unknown error')}"
                except:
                    error_msg += f" - {e.response.text[:200]}"
            raise Exception(error_msg) from e
        except Exception as e:
            raise Exception(f"Gemini Embedding API call failed: {str(e)}") from e
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.aclose()
