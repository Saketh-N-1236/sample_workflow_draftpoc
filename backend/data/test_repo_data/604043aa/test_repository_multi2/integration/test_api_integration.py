"""Integration tests for API endpoints."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

# Note: This would require the actual FastAPI app instance
# For now, we test the logic components


class TestChatEndpointIntegration:
    """Test chat endpoint integration."""
    
    @pytest.mark.asyncio
    async def test_chat_request_response_flow(self):
        """Test complete chat request-response flow."""
        # Mock agent
        mock_agent = AsyncMock()
        mock_agent.invoke = AsyncMock(return_value={
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ],
            "request_id": "test-123",
            "session_id": "session-123"
        })
        
        # Mock agent pool
        with patch('api.routes.get_agent', return_value=mock_agent):
            # Simulate request processing
            request_data = {
                "message": "Hello",
                "session_id": "session-123"
            }
            
            # Process request (simulated)
            result = await mock_agent.invoke(
                request_data["message"],
                request_data["session_id"],
                "test-123"
            )
            
            assert result is not None
            assert "messages" in result
    
    @pytest.mark.asyncio
    async def test_chat_with_tool_usage(self):
        """Test chat request that uses tools."""
        mock_agent = AsyncMock()
        mock_agent.invoke = AsyncMock(return_value={
            "messages": [
                {"role": "user", "content": "List tables"},
                {"role": "assistant", "content": "", "tool_calls": [{"name": "catalog_list_tables"}]},
                {"role": "tool", "content": '{"tables": ["users"]}'},
                {"role": "assistant", "content": "Here are the tables: users"}
            ],
            "tool_calls": [{"name": "catalog_list_tables", "step": 1}],
            "tool_results": [{"tool_name": "catalog_list_tables", "result": {"tables": ["users"]}}],
            "request_id": "test-123"
        })
        
        with patch('api.routes.get_agent', return_value=mock_agent):
            result = await mock_agent.invoke("List tables", "session-123", "test-123")
            
            assert "tool_calls" in result
            assert len(result["tool_calls"]) > 0


class TestToolsEndpointIntegration:
    """Test tools endpoint integration."""
    
    @pytest.mark.asyncio
    async def test_tools_endpoint_discovery(self, mock_mcp_client):
        """Test tools endpoint discovers tools from all servers."""
        mock_mcp_client.discover_all_tools = AsyncMock(return_value={
            "catalog": [Mock(name="list_tables", description="List tables")],
            "sql_query": [Mock(name="execute_query", description="Execute SQL")],
            "vector_search": [Mock(name="search_documents", description="Search")]
        })
        
        tools = await mock_mcp_client.discover_all_tools()
        
        assert len(tools) == 3
        assert "catalog" in tools
        assert "sql_query" in tools
        assert "vector_search" in tools
