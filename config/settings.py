"""Application settings with multi-provider LLM support."""

from typing import Optional, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Configuration for environment variable loading
    # Note: env_file is set dynamically in get_settings() to find .env relative to project root
    # This allows the settings to work regardless of the current working directory
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields instead of raising errors
        env_ignore_empty=True,
    )
    
    # LLM Provider Selection
    llm_provider: str = "gemini"  # Options: gemini, openai, anthropic, ollama
    
    # Model Name Override (if set, overrides provider-specific model)
    model_name: Optional[str] = None  # e.g., "gpt-4", "gemini-2.5-flash"
    
    # Embedding Provider Selection (can be different from LLM provider)
    embedding_provider: str = "ollama"  # Options: gemini, ollama, openai
    
    # Embedding Model Name Override (if set, overrides provider-specific embedding model)
    embedding_model_name: Optional[str] = None  # e.g., "text-embedding-3-small", "nomic-embed-text"
    
    # Gemini Configuration
    gemini_api_key: Optional[str] = None  # Loaded from GEMINI_API_KEY env var
    gemini_model: str = "gemini-2.5-flash"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None  # Loaded from OPENAI_API_KEY env var
    openai_model: str = "gpt-4"
    openai_embedding_model: str = "text-embedding-3-small"
    
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


def get_settings() -> Settings:
    """Get settings instance.
    
    Note: Settings are not cached to ensure environment variable changes
    are immediately reflected. This function creates a new Settings instance
    each time, which reads fresh from both .env file and os.environ.
    
    Important: If you change .env file, you may need to restart the application
    or ensure the .env file is reloaded. Environment variables set in the shell
    (os.environ) take precedence over .env file values.
    
    Returns:
        Settings instance
    """
    import logging
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    
    logger = logging.getLogger(__name__)
    
    # Find project root by looking for .env file or config/ directory
    # Start from current file location (config/settings.py)
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent  # config/ -> project_root/
    
    # Look for .env file in project root
    env_file = project_root / ".env"
    
    # If not found in project root, try current working directory
    if not env_file.exists():
        cwd_env_file = Path(".env").resolve()
        if cwd_env_file.exists():
            env_file = cwd_env_file
            logger.info(f"Found .env file in current working directory: {env_file}")
        else:
            logger.warning(f".env file not found at project root ({project_root / '.env'}) or current directory ({cwd_env_file})")
            logger.warning(f"  Project root: {project_root}")
            logger.warning(f"  Current working directory: {os.getcwd()}")
            env_file = None
    
    # Load .env file explicitly to ensure it's found regardless of working directory
    if env_file and env_file.exists():
        # Load .env file - override=True to ensure .env values are used
        # This ensures .env file values take precedence over any existing env vars
        # (except those explicitly set in the shell before this call)
        result = load_dotenv(env_file, override=True)
        if result:
            logger.info(f"Loaded .env file from: {env_file}")
        else:
            logger.warning(f"Failed to load .env file from: {env_file}")
    elif env_file is None:
        # .env file not found, but continue with defaults
        pass
    
    # Create new settings instance (reads fresh from .env and os.environ)
    # Pydantic reads os.environ first, then .env file
    # We've already loaded .env into os.environ, so Settings() will pick it up
    settings = Settings()
    
    # Log configuration summary (only on first call or when changed)
    model_display = settings.model_name or f"{settings.llm_provider} default"
    embedding_model_display = settings.embedding_model_name or f"{settings.embedding_provider} default"
    
    logger.info(
        f"Configuration: LLM Provider={settings.llm_provider.upper()}, "
        f"Model={model_display}, "
        f"Embedding Provider={settings.embedding_provider.upper()}, "
        f"Embedding Model={embedding_model_display}"
    )
    
    return settings
