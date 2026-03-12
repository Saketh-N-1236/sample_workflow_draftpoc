"""Test script to verify .env file loading."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import get_settings
import logging

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

print("=" * 60)
print("Testing .env file loading")
print("=" * 60)
print()

# Check current working directory
print(f"Current working directory: {os.getcwd()}")
print()

# Check if .env file exists
env_file = project_root / ".env"
print(f"Looking for .env at: {env_file}")
print(f".env file exists: {env_file.exists()}")
print()

if env_file.exists():
    print("Contents of .env file (LLM-related lines):")
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and any(key in line.upper() for key in ['LLM_PROVIDER', 'MODEL_NAME', 'EMBEDDING_PROVIDER', 'EMBEDDING_MODEL', 'OPENAI_API_KEY']):
                if 'API_KEY' in line.upper():
                    key, value = line.split('=', 1) if '=' in line else (line, '')
                    if value:
                        masked = value[:10] + '...' if len(value) > 10 else '***'
                        print(f"  {key}={masked}")
                else:
                    print(f"  {line}")
    print()

# Check environment variables before loading
print("Environment variables BEFORE get_settings():")
print(f"  LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'not set')}")
print(f"  MODEL_NAME: {os.getenv('MODEL_NAME', 'not set')}")
print(f"  EMBEDDING_PROVIDER: {os.getenv('EMBEDDING_PROVIDER', 'not set')}")
print(f"  EMBEDDING_MODEL_NAME: {os.getenv('EMBEDDING_MODEL_NAME', 'not set')}")
print()

# Load settings
print("Loading settings...")
print("-" * 60)
settings = get_settings()
print("-" * 60)
print()

# Check environment variables after loading
print("Environment variables AFTER get_settings():")
print(f"  LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'not set')}")
print(f"  MODEL_NAME: {os.getenv('MODEL_NAME', 'not set')}")
print(f"  EMBEDDING_PROVIDER: {os.getenv('EMBEDDING_PROVIDER', 'not set')}")
print(f"  EMBEDDING_MODEL_NAME: {os.getenv('EMBEDDING_MODEL_NAME', 'not set')}")
print()

# Show actual settings values
print("Settings values:")
print(f"  llm_provider: {settings.llm_provider}")
print(f"  model_name: {settings.model_name}")
print(f"  embedding_provider: {settings.embedding_provider}")
print(f"  embedding_model_name: {settings.embedding_model_name}")
print(f"  openai_api_key: {'set' if settings.openai_api_key else 'not set'}")
print(f"  gemini_api_key: {'set' if settings.gemini_api_key else 'not set'}")
print()
