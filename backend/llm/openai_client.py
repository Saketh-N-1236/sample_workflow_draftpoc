"""OpenAI LLM provider implementation."""

import httpx
import asyncio
from typing import List, Dict, Any, Optional
from llm.base import LLMProvider
from llm.models import LLMRequest, LLMResponse, EmbeddingRequest, EmbeddingResponse


class OpenAIClient(LLMProvider):
    """OpenAI LLM provider implementation."""
    
    # Model name mappings for common mistakes/aliases
    MODEL_NAME_MAPPINGS = {
        "gpt-4.1 mini": "gpt-4o-mini",
        "gpt-4.1-mini": "gpt-4o-mini",
        "gpt4.1-mini": "gpt-4o-mini",
        "gpt-4.1": "gpt-4o",
        "gpt-4.1-turbo": "gpt-4o",
        "gpt4": "gpt-4",
        "gpt4-turbo": "gpt-4-turbo",
    }
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        embedding_model: str = "text-embedding-3-small"
    ):
        """Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            model: Model name for chat completion (e.g., gpt-4, gpt-4o-mini, gpt-3.5-turbo)
            embedding_model: Model name for embeddings (e.g., text-embedding-3-small, text-embedding-ada-002)
        """
        self._api_key = api_key
        
        # Normalize model name (handle common mistakes/aliases)
        original_model = model
        self._model = self.MODEL_NAME_MAPPINGS.get(model.lower(), model)
        
        # Log if model name was corrected
        if self._model != original_model:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"OpenAI model name corrected: '{original_model}' -> '{self._model}'. "
                f"Please update your configuration to use the correct model name."
            )
        
        # Normalize embedding model name
        original_embedding = embedding_model
        self._embedding_model = self.MODEL_NAME_MAPPINGS.get(embedding_model.lower(), embedding_model)
        
        if self._embedding_model != original_embedding:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"OpenAI embedding model name corrected: '{original_embedding}' -> '{self._embedding_model}'. "
                f"Please update your configuration to use the correct model name."
            )
        self._base_url = "https://api.openai.com/v1"
        # Increased timeout for large requests (up to 5 minutes)
        self._client = httpx.AsyncClient(
            timeout=300.0,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json"
            }
        )
    
    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "openai"
    
    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model
    
    @property
    def embedding_model(self) -> str:
        """Return embedding model name."""
        return self._embedding_model
    
    @property
    def supports_streaming(self) -> bool:
        """OpenAI supports streaming."""
        return True
    
    def get_embedding_dimensions(self) -> Optional[int]:
        """Return the expected embedding dimensions for OpenAI models."""
        # OpenAI embedding model dimensions
        model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return model_dimensions.get(self._embedding_model, 1536)  # Default to 1536
    
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate chat completion using OpenAI.
        
        Args:
            request: LLM request with messages and parameters
            
        Returns:
            LLMResponse with generated content
        """
        try:
            # Convert messages to OpenAI format
            messages = []
            for msg in request.messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # OpenAI uses 'system', 'user', 'assistant' roles
                if role in ["system", "user", "assistant"]:
                    messages.append({"role": role, "content": content})
                elif role == "model":
                    # Convert 'model' to 'assistant' for OpenAI
                    messages.append({"role": "assistant", "content": content})
            
            # Prepare request
            payload = {
                "model": self._model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }
            
            if request.top_p is not None:
                payload["top_p"] = request.top_p
            
            if request.frequency_penalty is not None:
                payload["frequency_penalty"] = request.frequency_penalty
            
            if request.presence_penalty is not None:
                payload["presence_penalty"] = request.presence_penalty
            
            # Make API call with retry logic for rate limiting
            max_retries = 3
            retry_delay = 1.0
            
            for attempt in range(max_retries):
                try:
                    response = await self._client.post(
                        f"{self._base_url}/chat/completions",
                        json=payload
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Extract response
                    choices = result.get("choices", [])
                    if not choices:
                        raise ValueError("No choices in OpenAI response")
                    
                    content = choices[0].get("message", {}).get("content", "")
                    finish_reason = choices[0].get("finish_reason", "stop")
                    
                    # Extract usage info
                    usage = result.get("usage", {})
                    
                    return LLMResponse(
                        content=content,
                        model=self._model,
                        provider=self.provider_name,
                        usage=usage,
                        finish_reason=finish_reason
                    )
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:  # Rate limit
                        if attempt < max_retries - 1:
                            # Try to extract retry-after from headers
                            retry_after = e.response.headers.get("Retry-After")
                            if retry_after:
                                try:
                                    wait_time = float(retry_after)
                                    wait_time = min(wait_time, 60.0)  # Cap at 60 seconds
                                except ValueError:
                                    wait_time = retry_delay * (2 ** attempt)
                            else:
                                wait_time = retry_delay * (2 ** attempt)
                            
                            await asyncio.sleep(wait_time)
                            retry_delay = wait_time
                            continue
                    
                    error_msg = f"OpenAI API error: {e.response.status_code}"
                    if e.response.text:
                        try:
                            error_data = e.response.json()
                            error_msg += f" - {error_data.get('error', {}).get('message', 'Unknown error')}"
                        except:
                            error_msg += f" - {e.response.text[:200]}"
                    raise Exception(error_msg) from e
            
            raise Exception("OpenAI API call failed after retries")
            
        except Exception as e:
            raise Exception(f"OpenAI API call failed: {str(e)}") from e
    
    async def get_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Get embeddings using OpenAI.
        
        Args:
            request: Embedding request with texts
            
        Returns:
            EmbeddingResponse with embeddings
        """
        try:
            # Use model from request if provided, otherwise use default
            model = request.model or self._embedding_model
            
            # Prepare request
            payload = {
                "model": model,
                "input": request.texts
            }
            
            # Make API call
            response = await self._client.post(
                f"{self._base_url}/embeddings",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract embeddings
            embeddings = [item.get("embedding", []) for item in result.get("data", [])]
            
            if not embeddings:
                raise ValueError("No embeddings returned from OpenAI")
            
            # Extract usage info if available
            usage = result.get("usage", {})
            
            return EmbeddingResponse(
                embeddings=embeddings,
                model=model,
                provider=self.provider_name,
                usage=usage
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"OpenAI Embedding API error: {e.response.status_code}"
            if e.response.text:
                try:
                    error_data = e.response.json()
                    error_msg += f" - {error_data.get('error', {}).get('message', 'Unknown error')}"
                except:
                    error_msg += f" - {e.response.text[:200]}"
            raise Exception(error_msg) from e
        except Exception as e:
            raise Exception(f"OpenAI Embedding API call failed: {str(e)}") from e
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.aclose()
