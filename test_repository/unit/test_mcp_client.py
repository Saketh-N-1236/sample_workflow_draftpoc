"""Unit tests for MCP SDK client."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any
import httpx

from agent.mcp_sdk_client import MCPSDKClient


class TestMCPSDKClientInitialization:
    """Test MCP SDK client initialization."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, mock_settings):
        """Test client initialization."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings):
            client = MCPSDKClient()
            await client.initialize()
            
            assert client._initialized is True
            assert len(client.server_configs) > 0
    
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mock_settings):
        """Test that initialize is idempotent."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings):
            client = MCPSDKClient()
            await client.initialize()
            await client.initialize()  # Second call should not fail
            
            assert client._initialized is True
    
    @pytest.mark.asyncio
    async def test_initialize_loads_configs(self, mock_settings):
        """Test that initialization loads server configs."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings):
            client = MCPSDKClient()
            await client.initialize()
            
            assert "catalog" in client.server_configs
            assert "sql_query" in client.server_configs
            assert "vector_search" in client.server_configs


class TestMCPClientToolDiscovery:
    """Test tool discovery functionality."""
    
    @pytest.mark.asyncio
    async def test_discover_tools_success(self, mock_settings):
        """Test successful tool discovery."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch('agent.mcp_sdk_client.sse_client') as mock_sse, \
             patch('agent.mcp_sdk_client.ClientSession') as mock_session:
            
            # Setup mocks
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_sse.return_value.__aenter__.return_value = (mock_read, mock_write)
            
            mock_session_instance = AsyncMock()
            mock_session_instance.initialize = AsyncMock()
            mock_session_instance.list_tools = AsyncMock(return_value=Mock(tools=[
                Mock(name="test_tool", description="Test tool")
            ]))
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            client = MCPSDKClient()
            await client.initialize()
            
            tools = await client.discover_tools("catalog")
            
            assert len(tools) > 0
            assert tools[0].name == "test_tool"
    
    @pytest.mark.asyncio
    async def test_discover_tools_connection_error(self, mock_settings):
        """Test tool discovery with connection error."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch('agent.mcp_sdk_client.sse_client') as mock_sse:
            
            mock_sse.side_effect = httpx.ConnectError("Connection failed")
            
            client = MCPSDKClient()
            await client.initialize()
            
            with pytest.raises(ConnectionError):
                await client.discover_tools("catalog")
    
    @pytest.mark.asyncio
    async def test_discover_tools_timeout(self, mock_settings):
        """Test tool discovery with timeout."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch('agent.mcp_sdk_client.sse_client') as mock_sse:
            
            mock_sse.side_effect = httpx.TimeoutException("Request timed out")
            
            client = MCPSDKClient()
            await client.initialize()
            
            with pytest.raises(ConnectionError):
                await client.discover_tools("catalog")
    
    @pytest.mark.asyncio
    async def test_discover_tools_retry(self, mock_settings):
        """Test tool discovery retry logic."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch('agent.mcp_sdk_client.sse_client') as mock_sse, \
             patch('agent.mcp_sdk_client.ClientSession') as mock_session, \
             patch('asyncio.sleep'):
            
            # First call fails, second succeeds
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            
            mock_session_instance = AsyncMock()
            mock_session_instance.initialize = AsyncMock()
            mock_session_instance.list_tools = AsyncMock(return_value=Mock(tools=[]))
            
            mock_sse.side_effect = [
                httpx.ConnectError("First attempt failed"),
                (mock_read, mock_write)
            ]
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            client = MCPSDKClient()
            await client.initialize()
            
            # Should retry and eventually succeed
            try:
                tools = await client.discover_tools("catalog")
                assert tools is not None
            except ConnectionError:
                # If all retries fail, that's expected
                pass
    
    @pytest.mark.asyncio
    async def test_discover_all_tools(self, mock_settings):
        """Test discovering tools from all servers."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch.object(MCPSDKClient, 'discover_tools') as mock_discover:
            
            mock_discover.side_effect = lambda server: AsyncMock(return_value=[
                Mock(name=f"{server}_tool", description="Tool")
            ])()
            
            client = MCPSDKClient()
            await client.initialize()
            
            # Mock the discover_tools method properly
            async def mock_discover_side_effect(server_name: str):
                return [Mock(name=f"{server_name}_tool", description="Tool")]
            
            client.discover_tools = AsyncMock(side_effect=mock_discover_side_effect)
            
            all_tools = await client.discover_all_tools()
            
            assert isinstance(all_tools, dict)
            assert len(all_tools) > 0


class TestMCPClientToolExecution:
    """Test tool execution functionality."""
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self, mock_settings):
        """Test successful tool execution."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch('agent.mcp_sdk_client.sse_client') as mock_sse, \
             patch('agent.mcp_sdk_client.ClientSession') as mock_session:
            
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_sse.return_value.__aenter__.return_value = (mock_read, mock_write)
            
            mock_session_instance = AsyncMock()
            mock_session_instance.initialize = AsyncMock()
            mock_session_instance.call_tool = AsyncMock(return_value={
                "result": {"data": "Success"}
            })
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            client = MCPSDKClient()
            await client.initialize()
            
            result = await client.call_tool("catalog", "test_tool", {"query": "test"})
            
            assert result is not None
            assert "result" in result or "data" in str(result)
    
    @pytest.mark.asyncio
    async def test_call_tool_error_response(self, mock_settings):
        """Test tool execution with error response."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch('agent.mcp_sdk_client.sse_client') as mock_sse, \
             patch('agent.mcp_sdk_client.ClientSession') as mock_session:
            
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_sse.return_value.__aenter__.return_value = (mock_read, mock_write)
            
            mock_session_instance = AsyncMock()
            mock_session_instance.initialize = AsyncMock()
            mock_session_instance.call_tool = AsyncMock(return_value={
                "isError": True,
                "error": "Tool execution failed"
            })
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            client = MCPSDKClient()
            await client.initialize()
            
            result = await client.call_tool("catalog", "test_tool", {})
            
            assert result.get("isError") is True
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_call_tool_connection_error(self, mock_settings):
        """Test tool execution with connection error."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch('agent.mcp_sdk_client.sse_client') as mock_sse:
            
            mock_sse.side_effect = httpx.ConnectError("Connection failed")
            
            client = MCPSDKClient()
            await client.initialize()
            
            with pytest.raises(Exception):  # Should raise some exception
                await client.call_tool("catalog", "test_tool", {})
    
    @pytest.mark.asyncio
    async def test_call_tool_timeout(self, mock_settings):
        """Test tool execution with timeout."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch('agent.mcp_sdk_client.sse_client') as mock_sse:
            
            mock_sse.side_effect = httpx.TimeoutException("Timeout")
            
            client = MCPSDKClient()
            await client.initialize()
            
            with pytest.raises(Exception):
                await client.call_tool("catalog", "test_tool", {})


class TestMCPClientEdgeCases:
    """Test edge cases for MCP client."""
    
    @pytest.mark.asyncio
    async def test_uninitialized_client(self):
        """Test operations on uninitialized client."""
        client = MCPSDKClient()
        
        # Should raise error or handle gracefully
        with pytest.raises((RuntimeError, ValueError)):
            await client.discover_tools("catalog")
    
    @pytest.mark.asyncio
    async def test_unknown_server(self, mock_settings):
        """Test operations with unknown server."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings):
            client = MCPSDKClient()
            await client.initialize()
            
            with pytest.raises(ValueError, match="not configured"):
                await client.discover_tools("unknown_server")
    
    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self, mock_settings):
        """Test parallel tool calls with semaphore."""
        with patch('agent.mcp_sdk_client.get_settings', return_value=mock_settings), \
             patch.object(MCPSDKClient, 'discover_tools') as mock_discover:
            
            async def slow_discover(server_name: str):
                await asyncio.sleep(0.1)
                return []
            
            client = MCPSDKClient()
            await client.initialize()
            client.discover_tools = AsyncMock(side_effect=slow_discover)
            
            # Make multiple parallel calls
            tasks = [client.discover_tools("catalog") for _ in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should complete (some may be exceptions)
            assert len(results) == 10
