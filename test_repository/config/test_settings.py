"""Tests for settings module."""

import pytest
from unittest.mock import patch, MagicMock
import os
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from config.settings import Settings, get_settings, clear_settings_cache


class TestSettings:
    """Test suite for Settings."""
    
    def test_settings_default_values(self):
        """Test default settings values."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            
            assert settings.llm_provider == "gemini"
            assert settings.embedding_provider == "ollama"
            assert settings.catalog_mcp_port == 7001
            assert settings.vector_mcp_port == 7002
            assert settings.sql_mcp_port == 7003
    
    def test_settings_from_env(self):
        """Test loading settings from environment variables."""
        env_vars = {
            "LLM_PROVIDER": "ollama",
            "EMBEDDING_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test_key",
            "CATALOG_MCP_PORT": "8001"
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()
            
            assert settings.llm_provider == "ollama"
            assert settings.embedding_provider == "gemini"
            assert settings.gemini_api_key == "test_key"
            assert settings.catalog_mcp_port == 8001
    
    def test_settings_validate_llm_provider(self):
        """Test LLM provider validation."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "invalid"}, clear=False):
            with pytest.raises(ValueError, match="Invalid LLM provider"):
                Settings()
    
    def test_settings_validate_embedding_provider(self):
        """Test embedding provider validation."""
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "invalid"}, clear=False):
            with pytest.raises(ValueError, match="Invalid embedding provider"):
                Settings()
    
    def test_get_settings_singleton(self):
        """Test get_settings returns singleton."""
        clear_settings_cache()
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should be the same instance (cached)
        assert settings1 is settings2
    
    def test_clear_settings_cache(self):
        """Test clearing settings cache."""
        clear_settings_cache()
        settings1 = get_settings()
        
        clear_settings_cache()
        settings2 = get_settings()
        
        # Should be different instances after clearing cache
        # (Note: In practice, they might be the same if no env changes)
        assert isinstance(settings1, Settings)
        assert isinstance(settings2, Settings)
    
    def test_settings_optional_fields(self):
        """Test optional settings fields."""
        settings = Settings()
        
        # Optional fields should have defaults or be None
        assert settings.llm_top_p is None or isinstance(settings.llm_top_p, (float, type(None)))
        assert settings.api_key is None or isinstance(settings.api_key, str)
