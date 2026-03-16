"""Common models for LLM providers."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class LLMRequest(BaseModel):
    """Request model for LLM chat completion."""
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


class LLMResponse(BaseModel):
    """Response model for LLM chat completion."""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class EmbeddingRequest(BaseModel):
    """Request model for embeddings."""
    texts: List[str]
    model: Optional[str] = None


class EmbeddingResponse(BaseModel):
    """Response model for embeddings."""
    embeddings: List[List[float]]
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
