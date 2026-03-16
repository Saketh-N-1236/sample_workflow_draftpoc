# Quick Start Guide - LLM Provider Switching

## Simple Environment Variable Configuration

### Switch to OpenAI

Add to your `.env` file:

```bash
# LLM Provider
LLM_PROVIDER=openai
MODEL_NAME=gpt-4
OPENAI_API_KEY=sk-your-api-key-here

# Embedding Provider (optional - can use OpenAI or Ollama)
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small
```

### Switch to Gemini

Add to your `.env` file:

```bash
# LLM Provider
LLM_PROVIDER=gemini
MODEL_NAME=gemini-2.5-flash
GEMINI_API_KEY=your-gemini-api-key-here

# Embedding Provider (optional - can use Ollama for local embeddings)
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=nomic-embed-text
```

### Use Ollama for Embeddings

```bash
# Embedding Provider
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

## Testing

Run the example script to test your configuration:

```bash
python llm/example_usage.py
```

## Common Model Names

### OpenAI Models
- Chat: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
- Embeddings: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`

### Gemini Models
- Chat: `gemini-2.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash-exp`
- Embeddings: Fixed to `embedding-001` (no override needed)

### Ollama Models
- Chat: `llama3`, `mistral`, `codellama` (any installed model)
- Embeddings: `nomic-embed-text`, `all-minilm`

## Notes

- `MODEL_NAME` overrides provider-specific defaults
- `EMBEDDING_MODEL_NAME` overrides embedding model defaults
- You can mix providers (e.g., OpenAI for LLM, Ollama for embeddings)
- All changes take effect immediately (no code changes needed)
