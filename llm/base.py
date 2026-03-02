"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from llm.models import LLMRequest, LLMResponse, EmbeddingRequest, EmbeddingResponse


class LLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    All LLM providers must implement this interface to ensure
    consistent behavior across different providers.
    """
    
    @abstractmethod
    async def chat_completion(
        self,
        request: LLMRequest
    ) -> LLMResponse:
        """Generate chat completion.
        
        Args:
            request: LLM request with messages and parameters
            
        Returns:
            LLMResponse with generated content
            
        Raises:
            Exception: If the API call fails
        """
        pass
    
    @abstractmethod
    async def get_embeddings(
        self,
        request: EmbeddingRequest
    ) -> EmbeddingResponse:
        """Get embeddings for texts.
        
        Args:
            request: Embedding request with texts
            
        Returns:
            EmbeddingResponse with embeddings
            
        Raises:
            Exception: If the API call fails
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name (e.g., 'gemini', 'openai', 'anthropic')."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return model name being used."""
        pass
    
    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Return whether this provider supports streaming responses."""
        pass
    
    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(provider={self.provider_name}, model={self.model_name})"
