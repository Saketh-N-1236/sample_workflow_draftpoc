"""Unit tests for settings configuration."""

import pytest
import os
from unittest.mock import patch, Mock
from pathlib import Path

from config.settings import Settings, get_settings


class TestSettings:
    """Test settings configuration."""
    
    def test_default_settings(self):
        """Test default settings values."""
        with patch('config.settings.Path.exists', return_value=False):
            settings = Settings()
            
            assert settings.llm_provider == "gemini"
            assert settings.embedding_provider == "ollama"
    
    def test_llm_provider_validation(self):
        """Test LLM provider validation."""
        with patch('config.settings.Path.exists', return_value=False):
            # Valid provider
            settings = Settings(llm_provider="openai")
            assert settings.llm_provider == "openai"
            
            # Invalid provider
            with pytest.raises(ValueError, match="Invalid LLM provider"):
                Settings(llm_provider="invalid")
    
    def test_embedding_provider_validation(self):
        """Test embedding provider validation."""
        with patch('config.settings.Path.exists', return_value=False):
            # Valid provider
            settings = Settings(embedding_provider="gemini")
            assert settings.embedding_provider == "gemini"
            
            # Invalid provider
            with pytest.raises(ValueError, match="Invalid embedding provider"):
                Settings(embedding_provider="invalid")
    
    def test_gemini_configuration(self):
        """Test Gemini configuration."""
        with patch('config.settings.Path.exists', return_value=False):
            settings = Settings(
                llm_provider="gemini",
                gemini_api_key="test-key",
                gemini_model="gemini-2.5-pro"
            )
            
            assert settings.gemini_api_key == "test-key"
            assert settings.gemini_model == "gemini-2.5-pro"
    
    def test_openai_configuration(self):
        """Test OpenAI configuration."""
        with patch('config.settings.Path.exists', return_value=False):
            settings = Settings(
                llm_provider="openai",
                openai_api_key="test-key",
                openai_model="gpt-4"
            )
            
            assert settings.openai_api_key == "test-key"
            assert settings.openai_model == "gpt-4"
    
    def test_anthropic_configuration(self):
        """Test Anthropic configuration."""
        with patch('config.settings.Path.exists', return_value=False):
            settings = Settings(
                llm_provider="anthropic",
                anthropic_api_key="test-key",
                anthropic_model="claude-3-5-sonnet"
            )
            
            assert settings.anthropic_api_key == "test-key"
            assert settings.anthropic_model == "claude-3-5-sonnet"
    
    def test_ollama_configuration(self):
        """Test Ollama configuration."""
        with patch('config.settings.Path.exists', return_value=False):
            settings = Settings(
                llm_provider="ollama",
                ollama_base_url="http://localhost:11434",
                ollama_chat_model="llama3"
            )
            
            assert settings.ollama_base_url == "http://localhost:11434"
            assert settings.ollama_chat_model == "llama3"
    
    def test_mcp_port_configuration(self):
        """Test MCP server port configuration."""
        with patch('config.settings.Path.exists', return_value=False):
            settings = Settings(
                catalog_mcp_port=8001,
                sql_mcp_port=8002,
                vector_mcp_port=8003
            )
            
            assert settings.catalog_mcp_port == 8001
            assert settings.sql_mcp_port == 8002
            assert settings.vector_mcp_port == 8003
    
    def test_get_settings_singleton(self):
        """Test that get_settings returns singleton."""
        with patch('config.settings.Path.exists', return_value=False):
            settings1 = get_settings()
            settings2 = get_settings()
            
            # Should return same instance (cached)
            assert settings1 is settings2
    
    def test_settings_from_env(self):
        """Test loading settings from environment variables."""
        with patch.dict(os.environ, {
            'LLM_PROVIDER': 'openai',
            'OPENAI_API_KEY': 'env-key',
            'OPENAI_MODEL': 'gpt-3.5-turbo'
        }), patch('config.settings.Path.exists', return_value=False):
            settings = Settings()
            
            assert settings.llm_provider == "openai"
            assert settings.openai_api_key == "env-key"
            assert settings.openai_model == "gpt-3.5-turbo"
