"""
Example usage of LLM Provider Abstraction Layer.

This script demonstrates how to switch between different LLM providers
by simply changing environment variables.
"""

import sys
import asyncio
import os
from pathlib import Path

# Add project root to path (this script is in llm/ directory)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import LLMRequest, EmbeddingRequest


async def test_llm_provider():
    """Test LLM provider with current configuration."""
    settings = get_settings()
    
    print(f"Using LLM Provider: {settings.llm_provider}")
    print(f"Model (from config): {settings.model_name or 'default'}")
    print(f"Embedding Provider: {settings.embedding_provider}")
    print(f"Embedding Model (from config): {settings.embedding_model_name or 'default'}")
    print("-" * 50)
    
    try:
        # Create LLM provider
        llm_provider = LLMFactory.create_provider(settings)
        print(f"[OK] LLM Provider initialized: {llm_provider.provider_name}")
        print(f"     Model (actual): {llm_provider.model_name}")
        
        # Show warning if model name was corrected
        if settings.model_name and llm_provider.model_name != settings.model_name:
            print(f"     [NOTE] Model name was corrected from '{settings.model_name}' to '{llm_provider.model_name}'")
        
        # Test chat completion
        print("\nTesting chat completion...")
        request = LLMRequest(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello' in one word."}
            ],
            temperature=0.7,
            max_tokens=50
        )
        
        response = await llm_provider.chat_completion(request)
        print(f"[OK] Response: {response.content}")
        print(f"     Model: {response.model}")
        print(f"     Provider: {response.provider}")
        
    except Exception as e:
        print(f"[ERROR] LLM Provider test failed: {e}")
        return False
    
    try:
        # Create embedding provider
        embedding_provider = LLMFactory.create_embedding_provider(settings)
        print(f"\n[OK] Embedding Provider initialized: {embedding_provider.provider_name}")
        
        # Test embeddings
        print("\nTesting embeddings...")
        embedding_request = EmbeddingRequest(texts=["Hello world", "Test embedding"])
        embedding_response = await embedding_provider.get_embeddings(embedding_request)
        print(f"[OK] Generated {len(embedding_response.embeddings)} embeddings")
        print(f"     Model: {embedding_response.model}")
        print(f"     Provider: {embedding_response.provider}")
        print(f"     Embedding dimension: {len(embedding_response.embeddings[0]) if embedding_response.embeddings else 0}")
        
    except Exception as e:
        print(f"[ERROR] Embedding Provider test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("All tests passed!")
    return True


async def main():
    """Main function."""
    print("=" * 50)
    print("LLM Provider Abstraction Layer - Test")
    print("=" * 50)
    print("\nCurrent environment variables:")
    print(f"  LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'not set')}")
    print(f"  MODEL_NAME: {os.getenv('MODEL_NAME', 'not set')}")
    print(f"  EMBEDDING_PROVIDER: {os.getenv('EMBEDDING_PROVIDER', 'not set')}")
    print(f"  EMBEDDING_MODEL_NAME: {os.getenv('EMBEDDING_MODEL_NAME', 'not set')}")
    print()
    
    success = await test_llm_provider()
    
    if not success:
        print("\n[WARNING] Some tests failed. Check your API keys and configuration.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
