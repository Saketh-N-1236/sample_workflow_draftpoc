"""Factory for creating LLM provider instances."""

from typing import Optional, List
from llm.base import LLMProvider
from config.settings import Settings


class LLMFactory:
    """Factory class for creating LLM provider instances.
    
    This factory abstracts the creation of different LLM providers,
    allowing easy switching between providers via configuration.
    """
    
    @staticmethod
    def create_provider(settings: Settings) -> LLMProvider:
        """Create an LLM provider based on settings.
        
        Args:
            settings: Application settings with provider configuration
            
        Returns:
            LLMProvider instance
            
        Raises:
            ValueError: If provider is not supported or not configured
        """
        provider = settings.llm_provider.lower()
        
        if provider == "gemini":
            from llm.gemini_client import GeminiClient
            if not settings.gemini_api_key:
                raise ValueError("Gemini API key is required but not set")
            return GeminiClient(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model
            )
        
        elif provider == "openai":
            from llm.openai_client import OpenAIClient
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key is required but not set")
            return OpenAIClient(
                api_key=settings.openai_api_key,
                model=settings.openai_model
            )
        
        elif provider == "anthropic":
            from llm.anthropic_client import AnthropicClient
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key is required but not set")
            return AnthropicClient(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model
            )
        
        elif provider == "ollama":
            from llm.ollama_client import OllamaClient
            return OllamaClient(
                base_url=settings.ollama_base_url,
                chat_model=settings.ollama_chat_model,
                embedding_model=settings.ollama_embedding_model
            )
        
        else:
            raise ValueError(
                f"Unsupported LLM provider: {provider}. "
                f"Supported providers: gemini, openai, anthropic, ollama"
            )
    
    @staticmethod
    def get_available_providers() -> List[str]:
        """Get list of available provider names.
        
        Returns:
            List of provider names
        """
        return ["gemini", "openai", "anthropic", "ollama"]
    
    @staticmethod
    def create_embedding_provider(settings: Settings) -> LLMProvider:
        """Create an embedding provider (can be different from LLM provider).
        
        Args:
            settings: Application settings with provider configuration
            
        Returns:
            LLMProvider instance for embeddings
            
        Raises:
            ValueError: If provider is not supported or not configured
        """
        provider = settings.embedding_provider.lower()
        
        if provider == "gemini":
            from llm.gemini_client import GeminiClient
            if not settings.gemini_api_key:
                raise ValueError("Gemini API key is required but not set")
            return GeminiClient(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model
            )
        
        elif provider == "ollama":
            from llm.ollama_client import OllamaClient
            return OllamaClient(
                base_url=settings.ollama_base_url,
                chat_model=settings.ollama_chat_model,
                embedding_model=settings.ollama_embedding_model
            )
        
        else:
            raise ValueError(
                f"Unsupported embedding provider: {provider}. "
                f"Supported providers: gemini, ollama"
            )
