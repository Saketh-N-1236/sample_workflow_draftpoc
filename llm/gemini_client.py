"""Google Gemini LLM provider implementation."""

import httpx
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
        self._client = httpx.AsyncClient(timeout=60.0)
    
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
            
            # Make API call
            response = await self._client.post(
                f"{self._base_url}/models/{self._model}:generateContent",
                params={"key": self._api_key},
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
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
                    error_msg += f" - {error_data.get('error', {}).get('message', 'Unknown error')}"
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
