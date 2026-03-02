"""Application settings with multi-provider LLM support."""

from typing import Optional, Any
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Allow extra fields from .env file (e.g., database settings)
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore extra fields instead of raising errors
    }
    
    # LLM Provider Selection
    llm_provider: str = "gemini"  # Options: gemini, openai, anthropic, ollama
    
    # Embedding Provider Selection (can be different from LLM provider)
    embedding_provider: str = "ollama"  # Options: gemini, ollama
    
    # Gemini Configuration
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-pro"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    
    # Anthropic Configuration
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    
    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout: int = 300
    
    # LLM Parameters (provider-agnostic)
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    llm_top_p: Optional[float] = None
    
    @field_validator('llm_top_p', mode='before')
    @classmethod
    def parse_optional_float(cls, v: Any) -> Optional[float]:
        """Parse empty string as None for optional float fields."""
        if v == "" or v is None:
            return None
        try:
            return float(v) if v else None
        except (ValueError, TypeError):
            return None
    
    # Databases
    database_path: str = "./data/sample_data.db"
    vector_store_path: str = "./data/vector_store"
    
    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "mcp_agent_experiments"
    
    # MCP Server ports
    catalog_mcp_port: int = 7001
    vector_mcp_port: int = 7002
    sql_mcp_port: int = 7003
    
    # MCP Authentication
    mcp_api_key: Optional[str] = None  # Shared MCP API key
    
    # API settings
    api_port: int = 8000
    api_key: Optional[str] = None
    api_host: str = "0.0.0.0"
    
    # Concurrency
    max_parallel_mcp_calls: int = 5
    mcp_call_timeout: int = 30
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Inference Logging
    inference_log_db_path: str = "./data/inference_logs.db"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Returns:
        Settings instance
    """
    return Settings()
