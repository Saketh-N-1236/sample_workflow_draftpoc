"""Tests for LLM factory module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from llm.factory import LLMFactory
from config.settings import Settings


class TestLLMFactory:
    """Test suite for LLMFactory."""
    
    @pytest.fixture
    def gemini_settings(self):
        """Create settings for Gemini provider."""
        settings = MagicMock(spec=Settings)
        settings.llm_provider = "gemini"
        settings.gemini_api_key = "test_gemini_key"
        settings.gemini_model = "gemini-2.5-flash"
        return settings
    
    @pytest.fixture
    def ollama_settings(self):
        """Create settings for Ollama provider."""
        settings = MagicMock(spec=Settings)
        settings.llm_provider = "ollama"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_chat_model = "llama3"
        settings.ollama_embedding_model = "nomic-embed-text"
        settings.ollama_timeout = 300
        return settings
    
    def test_create_provider_gemini(self, gemini_settings):
        """Test creating Gemini provider."""
        with patch('llm.factory.GeminiClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            provider = LLMFactory.create_provider(gemini_settings)
            
            assert provider is not None
            mock_client.assert_called_once_with(
                api_key="test_gemini_key",
                model="gemini-2.5-flash"
            )
    
    def test_create_provider_gemini_missing_key(self, gemini_settings):
        """Test creating Gemini provider without API key."""
        gemini_settings.gemini_api_key = None
        
        with pytest.raises(ValueError, match="Gemini API key is required"):
            LLMFactory.create_provider(gemini_settings)
    
    def test_create_provider_ollama(self, ollama_settings):
        """Test creating Ollama provider."""
        with patch('llm.factory.OllamaClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            provider = LLMFactory.create_provider(ollama_settings)
            
            assert provider is not None
            mock_client.assert_called_once()
    
    def test_create_provider_invalid(self):
        """Test creating provider with invalid name."""
        settings = MagicMock(spec=Settings)
        settings.llm_provider = "invalid_provider"
        
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMFactory.create_provider(settings)
    
    def test_get_available_providers(self):
        """Test getting list of available providers."""
        providers = LLMFactory.get_available_providers()
        
        assert isinstance(providers, list)
        assert "gemini" in providers
        assert "ollama" in providers
        assert "openai" in providers
        assert "anthropic" in providers
    
    def test_create_embedding_provider_gemini(self, gemini_settings):
        """Test creating Gemini embedding provider."""
        gemini_settings.embedding_provider = "gemini"
        
        with patch('llm.factory.GeminiClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            provider = LLMFactory.create_embedding_provider(gemini_settings)
            
            assert provider is not None
            mock_client.assert_called_once()
    
    def test_create_embedding_provider_ollama(self, ollama_settings):
        """Test creating Ollama embedding provider."""
        ollama_settings.embedding_provider = "ollama"
        
        with patch('llm.factory.OllamaClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            provider = LLMFactory.create_embedding_provider(ollama_settings)
            
            assert provider is not None
            mock_client.assert_called_once()
    
    def test_create_embedding_provider_invalid(self):
        """Test creating embedding provider with invalid name."""
        settings = MagicMock(spec=Settings)
        settings.embedding_provider = "invalid_provider"
        
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            LLMFactory.create_embedding_provider(settings)
