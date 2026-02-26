"""Tests for API routes module."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from api.main import create_app


class TestAPIRoutes:
    """Test suite for API routes."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_chat_endpoint(self, client):
        """Test chat endpoint."""
        with patch('api.routes.get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke = AsyncMock(return_value={
                "messages": [
                    {"role": "assistant", "content": "Test response"}
                ],
                "request_id": "test_123",
                "tool_calls": [],
                "tool_results": [],
                "current_step": 1,
                "session_id": None,
                "prompt_version": "v1",
                "model_name": "gemini-2.5-flash",
                "error": None
            })
            mock_get_agent.return_value = mock_agent
            
            response = client.post(
                "/api/v1/chat",
                json={
                    "message": "Hello",
                    "session_id": None,
                    "max_iterations": 10
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "request_id" in data
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_with_session(self, client):
        """Test chat endpoint with session ID."""
        with patch('api.routes.get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke = AsyncMock(return_value={
                "messages": [
                    {"role": "assistant", "content": "Test response"}
                ],
                "request_id": "test_123",
                "session_id": "session_123",
                "tool_calls": [],
                "tool_results": [],
                "current_step": 1,
                "prompt_version": "v1",
                "model_name": "gemini-2.5-flash",
                "error": None
            })
            mock_get_agent.return_value = mock_agent
            
            response = client.post(
                "/api/v1/chat",
                json={
                    "message": "Hello",
                    "session_id": "session_123",
                    "max_iterations": 10
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data.get("session_id") == "session_123"
    
    def test_chat_endpoint_invalid_request(self, client):
        """Test chat endpoint with invalid request."""
        response = client.post(
            "/api/v1/chat",
            json={}  # Missing required fields
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_chat_stream_endpoint(self, client):
        """Test chat stream endpoint."""
        with patch('api.routes.get_agent') as mock_get_agent:
            mock_agent = MagicMock()
            
            async def mock_stream(*args, **kwargs):
                yield {"stage": "initializing", "data": {}, "timestamp": "2024-01-01T00:00:00"}
                yield {"stage": "completed", "data": {"response": "Test"}, "timestamp": "2024-01-01T00:00:01"}
            
            mock_agent.stream_invoke = mock_stream
            mock_get_agent.return_value = mock_agent
            
            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "Hello",
                    "max_iterations": 10
                }
            )
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    @pytest.mark.asyncio
    async def test_tools_endpoint(self, client):
        """Test tools listing endpoint."""
        with patch('api.routes.MCPSDKClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.discover_all_tools = AsyncMock(return_value={
                "catalog": [],
                "sql_query": [],
                "vector_search": []
            })
            mock_client_class.return_value = mock_client
            
            response = client.get("/api/v1/tools")
            
            assert response.status_code == 200
            data = response.json()
            assert "tools" in data
            assert "count" in data
    
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client):
        """Test health check endpoint with system info."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "llm_provider" in data
        assert "mcp_servers" in data
    
    @pytest.mark.asyncio
    async def test_status_endpoint(self, client):
        """Test status endpoint."""
        response = client.get("/api/v1/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        assert "llm_provider" in data
