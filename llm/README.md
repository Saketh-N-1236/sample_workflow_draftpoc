# LLM Provider Abstraction Layer

This module provides a unified abstraction layer for multiple LLM and embedding providers, allowing easy switching between providers via environment variables.

## Supported Providers

### Chat/Completion Providers
- **Gemini** (Google)
- **OpenAI** (GPT-4, GPT-3.5-turbo, etc.)
- **Anthropic** (Claude)
- **Ollama** (Local models)

### Embedding Providers
- **OpenAI** (text-embedding-3-small, text-embedding-ada-002)
- **Ollama** (nomic-embed-text, etc.)
- **Gemini** (embedding-001)

## Quick Start

### Environment Variables

Add these to your `.env` file:

```bash
# LLM Provider Selection
LLM_PROVIDER=gemini  # or "openai", "anthropic", "ollama"

# Model Name Override (optional - overrides provider-specific default)
MODEL_NAME=gpt-4  # e.g., "gpt-4", "gemini-2.5-flash", "claude-3-5-sonnet-20241022"

# Embedding Provider Selection
EMBEDDING_PROVIDER=ollama  # or "openai", "gemini"

# Embedding Model Override (optional)
EMBEDDING_MODEL_NAME=text-embedding-3-small  # e.g., "text-embedding-3-small", "nomic-embed-text"

# Provider-Specific API Keys
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Provider-Specific Models (used if MODEL_NAME not set)
GEMINI_MODEL=gemini-2.5-flash
OPENAI_MODEL=gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

## Usage Examples

### Switch to OpenAI

```bash
# In .env file
LLM_PROVIDER=openai
MODEL_NAME=gpt-4
OPENAI_API_KEY=sk-...
```

### Switch to Gemini

```bash
# In .env file
LLM_PROVIDER=gemini
MODEL_NAME=gemini-2.5-flash
GEMINI_API_KEY=...
```

### Use OpenAI for Embeddings

```bash
# In .env file
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small
OPENAI_API_KEY=sk-...
```

### Use Ollama for Embeddings

```bash
# In .env file
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

## Code Usage

```python
from config.settings import get_settings
from llm.factory import LLMFactory

# Get settings
settings = get_settings()

# Create LLM provider (uses LLM_PROVIDER from env)
llm_provider = LLMFactory.create_provider(settings)

# Create embedding provider (uses EMBEDDING_PROVIDER from env)
embedding_provider = LLMFactory.create_embedding_provider(settings)

# Use the providers
from llm.models import LLMRequest, EmbeddingRequest

# Chat completion
request = LLMRequest(
    messages=[{"role": "user", "content": "Hello!"}],
    temperature=0.7,
    max_tokens=100
)
response = await llm_provider.chat_completion(request)
print(response.content)

# Embeddings
embedding_request = EmbeddingRequest(texts=["Hello world"])
embedding_response = await embedding_provider.get_embeddings(embedding_request)
print(embedding_response.embeddings)
```

## Model Name Override

The `MODEL_NAME` environment variable allows you to override the provider-specific default model:

```bash
# Use GPT-4 even if OPENAI_MODEL is set to gpt-3.5-turbo
LLM_PROVIDER=openai
MODEL_NAME=gpt-4
```

This is useful for quick testing without changing provider-specific settings.

## Provider-Specific Notes

### OpenAI
- Chat models: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
- Embedding models: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
- Requires `OPENAI_API_KEY`

### Gemini
- Chat models: `gemini-2.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash-exp`
- Embedding model: Fixed to `embedding-001` (model parameter ignored)
- Requires `GEMINI_API_KEY`

### Ollama
- Chat models: Any model installed locally (e.g., `llama3`, `mistral`, `codellama`)
- Embedding models: `nomic-embed-text`, `all-minilm`, etc.
- Requires local Ollama server running
- Default URL: `http://localhost:11434`

## Error Handling

All providers include:
- Automatic retry logic for rate limits (429 errors)
- Proper error messages with API details
- Timeout handling (5 minutes for large requests)
