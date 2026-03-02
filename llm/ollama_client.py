"""Ollama LLM provider implementation."""

import httpx
from typing import List, Dict, Any
from llm.base import LLMProvider
from llm.models import LLMRequest, LLMResponse, EmbeddingRequest, EmbeddingResponse


class OllamaClient(LLMProvider):
    """Ollama LLM provider implementation for local inference."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        chat_model: str = "llama3",
        embedding_model: str = "nomic-embed-text"
    ):
        """Initialize Ollama client.
        
        Args:
            base_url: Ollama server URL
            chat_model: Model name for chat completion
            embedding_model: Model name for embeddings
        """
        self._base_url = base_url.rstrip('/')
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._client = httpx.AsyncClient(timeout=60.0)
    
    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "ollama"
    
    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._chat_model
    
    @property
    def supports_streaming(self) -> bool:
        """Ollama supports streaming."""
        return True
    
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate chat completion using Ollama.
        
        Args:
            request: LLM request with messages and parameters
            
        Returns:
            LLMResponse with generated content
        """
        try:
            # Convert messages to Ollama format
            messages = []
            for msg in request.messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Ollama uses 'system', 'user', 'assistant' roles
                if role in ["system", "user", "assistant"]:
                    messages.append({"role": role, "content": content})
                elif role == "model":
                    # Convert 'model' to 'assistant' for Ollama
                    messages.append({"role": "assistant", "content": content})
            
            # Prepare request
            payload = {
                "model": self._chat_model,
                "messages": messages,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                }
            }
            
            if request.top_p is not None:
                payload["options"]["top_p"] = request.top_p
            
            # Make API call
            response = await self._client.post(
                f"{self._base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract response
            content = result.get("message", {}).get("content", "")
            
            # Build usage info if available
            usage = None
            if "prompt_eval_count" in result or "eval_count" in result:
                usage = {
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "completion_tokens": result.get("eval_count", 0),
                    "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
                }
            
            return LLMResponse(
                content=content,
                model=self._chat_model,
                provider=self.provider_name,
                usage=usage,
                finish_reason=result.get("done_reason")
            )
            
        except httpx.HTTPError as e:
            raise Exception(f"Ollama API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")
    
    async def get_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Get embeddings using Ollama.
        
        Args:
            request: Embedding request with texts
            
        Returns:
            EmbeddingResponse with embeddings
        """
        try:
            embeddings = []
            
            # Ollama processes one text at a time
            for text in request.texts:
                payload = {
                    "model": self._embedding_model,
                    "prompt": text
                }
                
                response = await self._client.post(
                    f"{self._base_url}/api/embeddings",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                # Extract embedding
                embedding = result.get("embedding", [])
                if not embedding:
                    raise ValueError(f"No embedding returned for text: {text[:50]}...")
                
                embeddings.append(embedding)
            
            return EmbeddingResponse(
                embeddings=embeddings,
                model=self._embedding_model,
                provider=self.provider_name,
                usage=None  # Ollama doesn't provide detailed usage for embeddings
            )
            
        except httpx.HTTPError as e:
            raise Exception(f"Ollama embedding API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Ollama embedding error: {str(e)}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.aclose()
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            if hasattr(self, '_client'):
                # Note: httpx client cleanup should be done explicitly
                pass
        except:
            pass
