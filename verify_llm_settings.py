"""
Quick verification script to check LLM provider settings.

Run this script to verify that your .env file is being read correctly
and that the LLM provider abstraction layer is working.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import get_settings
from llm.factory import LLMFactory

def main():
    print("=" * 60)
    print("LLM Provider Settings Verification")
    print("=" * 60)
    print()
    
    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        print(f"✓ .env file found at: {env_file.absolute()}")
        print()
        
        # Read .env file directly to show what's in it
        print("Contents of .env file (LLM-related):")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and any(key in line.upper() for key in ['LLM_PROVIDER', 'MODEL_NAME', 'EMBEDDING_PROVIDER', 'EMBEDDING_MODEL', 'OPENAI_API_KEY', 'GEMINI_API_KEY']):
                    # Mask API keys
                    if 'API_KEY' in line.upper():
                        key, value = line.split('=', 1) if '=' in line else (line, '')
                        if value:
                            masked_value = value[:8] + '...' if len(value) > 8 else '***'
                            print(f"  {key}={masked_value}")
                        else:
                            print(f"  {line}")
                    else:
                        print(f"  {line}")
        print()
    else:
        print(f"✗ .env file NOT found at: {env_file.absolute()}")
        print()
    
    # Check environment variables
    print("Environment Variables (os.environ):")
    env_vars = {
        'LLM_PROVIDER': os.getenv('LLM_PROVIDER', 'not set'),
        'MODEL_NAME': os.getenv('MODEL_NAME', 'not set'),
        'EMBEDDING_PROVIDER': os.getenv('EMBEDDING_PROVIDER', 'not set'),
        'EMBEDDING_MODEL_NAME': os.getenv('EMBEDDING_MODEL_NAME', 'not set'),
        'OPENAI_API_KEY': 'set' if os.getenv('OPENAI_API_KEY') else 'not set',
        'GEMINI_API_KEY': 'set' if os.getenv('GEMINI_API_KEY') else 'not set',
    }
    for key, value in env_vars.items():
        print(f"  {key}: {value}")
    print()
    
    # Load settings
    print("Loading Settings from get_settings():")
    try:
        settings = get_settings()
        print(f"  llm_provider: {settings.llm_provider}")
        print(f"  model_name: {settings.model_name or '(using provider default)'}")
        print(f"  embedding_provider: {settings.embedding_provider}")
        print(f"  embedding_model_name: {settings.embedding_model_name or '(using provider default)'}")
        print(f"  openai_api_key: {'set' if settings.openai_api_key else 'not set'}")
        print(f"  gemini_api_key: {'set' if settings.gemini_api_key else 'not set'}")
        print()
        
        # Try to create LLM provider
        print("Creating LLM Provider:")
        try:
            llm_provider = LLMFactory.create_provider(settings)
            print(f"  ✓ Successfully created provider: {llm_provider.provider_name}")
            print(f"  ✓ Model: {llm_provider.model_name}")
            print()
            
            if settings.llm_provider.lower() != llm_provider.provider_name.lower():
                print(f"  ⚠ WARNING: Settings say '{settings.llm_provider}' but provider is '{llm_provider.provider_name}'")
                print()
        except Exception as e:
            print(f"  ✗ Failed to create LLM provider: {e}")
            print()
            print("  Common issues:")
            print("    - Missing API key for the selected provider")
            print("    - Invalid provider name")
            print("    - Provider not supported")
            print()
        
        # Try to create embedding provider
        print("Creating Embedding Provider:")
        try:
            embedding_provider = LLMFactory.create_embedding_provider(settings)
            print(f"  ✓ Successfully created provider: {embedding_provider.provider_name}")
            if hasattr(embedding_provider, 'embedding_model'):
                print(f"  ✓ Embedding Model: {embedding_provider.embedding_model}")
            print()
        except Exception as e:
            print(f"  ✗ Failed to create embedding provider: {e}")
            print()
        
    except Exception as e:
        print(f"  ✗ Failed to load settings: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    print("=" * 60)
    print("Verification Complete")
    print("=" * 60)
    print()
    print("Note: If settings don't match your .env file:")
    print("  1. Environment variables (os.environ) take precedence over .env file")
    print("  2. Restart your application after changing .env file")
    print("  3. Or set environment variables in your shell before starting the app")
    print()

if __name__ == "__main__":
    main()
