"""Unit tests for LLM factory."""

import pytest
from unittest.mock import Mock, patch
from config.settings import Settings

from llm.factory import LLMFactory


class TestLLMFactory:
    """Test LLM factory."""
    
    def test_create_gemini_provider(self, mock_settings):
        """Test creating Gemini provider."""
        mock_settings.llm_provider = "gemini"
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "gemini-2.5-pro"
        
        with patch('llm.factory.GeminiClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            
            provider = LLMFactory.create_provider(mock_settings)
            
            assert provider is not None
            mock_client.assert_called_once_with(
                api_key="test-key",
                model="gemini-2.5-pro"
            )
    
    def test_create_gemini_missing_key(self, mock_settings):
        """Test creating Gemini provider without API key."""
        mock_settings.llm_provider = "gemini"
        mock_settings.gemini_api_key = None
        
        with pytest.raises(ValueError, match="API key is required"):
            LLMFactory.create_provider(mock_settings)
    
    def test_create_openai_provider(self, mock_settings):
        """Test creating OpenAI provider."""
        mock_settings.llm_provider = "openai"
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4"
        
        with patch('llm.factory.OpenAIClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            
            provider = LLMFactory.create_provider(mock_settings)
            
            assert provider is not None
            mock_client.assert_called_once()
    
    def test_create_openai_missing_key(self, mock_settings):
        """Test creating OpenAI provider without API key."""
        mock_settings.llm_provider = "openai"
        mock_settings.openai_api_key = None
        
        with pytest.raises(ValueError, match="API key is required"):
            LLMFactory.create_provider(mock_settings)
    
    def test_create_anthropic_provider(self, mock_settings):
        """Test creating Anthropic provider."""
        mock_settings.llm_provider = "anthropic"
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.anthropic_model = "claude-3-5-sonnet"
        
        with patch('llm.factory.AnthropicClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            
            provider = LLMFactory.create_provider(mock_settings)
            
            assert provider is not None
            mock_client.assert_called_once()
    
    def test_create_anthropic_missing_key(self, mock_settings):
        """Test creating Anthropic provider without API key."""
        mock_settings.llm_provider = "anthropic"
        mock_settings.anthropic_api_key = None
        
        with pytest.raises(ValueError, match="API key is required"):
            LLMFactory.create_provider(mock_settings)
    
    def test_create_ollama_provider(self, mock_settings):
        """Test creating Ollama provider."""
        mock_settings.llm_provider = "ollama"
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_chat_model = "llama3"
        mock_settings.ollama_embedding_model = "nomic-embed"
        mock_settings.ollama_timeout = 300
        
        with patch('llm.factory.OllamaClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            
            provider = LLMFactory.create_provider(mock_settings)
            
            assert provider is not None
            mock_client.assert_called_once()
    
    def test_create_unsupported_provider(self, mock_settings):
        """Test creating unsupported provider."""
        mock_settings.llm_provider = "unsupported"
        
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMFactory.create_provider(mock_settings)
    
    def test_get_available_providers(self):
        """Test getting list of available providers."""
        providers = LLMFactory.get_available_providers()
        
        assert isinstance(providers, list)
        assert "gemini" in providers
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers
