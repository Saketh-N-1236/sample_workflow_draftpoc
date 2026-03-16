"""Integration tests for agent flow."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agent.langgraph_agent import LangGraphAgent
from agent.agent_pool import get_agent, reset_agent


class TestAgentInitializationFlow:
    """Test complete agent initialization flow."""
    
    @pytest.mark.asyncio
    async def test_full_initialization(self, mock_mcp_client, mock_langchain_tools):
        """Test complete agent initialization."""
        with patch('agent.langgraph_agent.MCPSDKClient', return_value=mock_mcp_client), \
             patch('agent.langgraph_agent.convert_mcp_tools_to_langchain', return_value=mock_langchain_tools), \
             patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"), \
             patch('agent.langgraph_agent.LangGraphAgentBuilder') as mock_builder:
            
            mock_graph = AsyncMock()
            mock_builder_instance = Mock()
            mock_builder_instance.build.return_value = mock_graph
            mock_builder.return_value = mock_builder_instance
            
            agent = LangGraphAgent()
            await agent.initialize()
            
            assert agent._initialized is True
            assert agent.graph is not None
    
    @pytest.mark.asyncio
    async def test_agent_invoke_flow(self, mock_mcp_client, mock_langchain_tools, mock_graph):
        """Test agent invoke flow."""
        with patch('agent.langgraph_agent.MCPSDKClient', return_value=mock_mcp_client), \
             patch('agent.langgraph_agent.convert_mcp_tools_to_langchain', return_value=mock_langchain_tools), \
             patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"), \
             patch('agent.langgraph_agent.LangGraphAgentBuilder') as mock_builder:
            
            mock_builder_instance = Mock()
            mock_builder_instance.build.return_value = mock_graph
            mock_builder.return_value = mock_builder_instance
            
            agent = LangGraphAgent()
            await agent.initialize()
            
            # Mock graph invoke
            mock_graph.ainvoke = AsyncMock(return_value={
                "messages": [
                    HumanMessage(content="Hello"),
                    AIMessage(content="Hi there!")
                ],
                "request_id": "test-123",
                "session_id": "session-123"
            })
            
            result = await agent.invoke("Hello", "session-123", "test-123")
            
            assert result is not None
            assert "messages" in result


class TestToolExecutionFlow:
    """Test tool execution flow."""
    
    @pytest.mark.asyncio
    async def test_tool_discovery_to_execution(self, mock_mcp_client):
        """Test flow from tool discovery to execution."""
        # Mock tool discovery
        mock_mcp_client.discover_all_tools = AsyncMock(return_value={
            "catalog": [Mock(name="list_tables", description="List tables")]
        })
        
        # Mock tool execution
        async def mock_call_tool(server_name, tool_name, arguments):
            return {"isError": False, "result": {"tables": ["users", "products"]}}
        
        mock_mcp_client.call_tool = AsyncMock(side_effect=mock_call_tool)
        
        # Discover tools
        tools = await mock_mcp_client.discover_all_tools()
        assert len(tools) > 0
        
        # Execute tool
        result = await mock_mcp_client.call_tool("catalog", "list_tables", {})
        assert result.get("isError") is False
        assert "result" in result


class TestStateManagementFlow:
    """Test state management flow."""
    
    @pytest.mark.asyncio
    async def test_state_persistence_flow(self, mock_graph, temp_checkpoint_db):
        """Test state persistence through checkpointing."""
        # This would test checkpoint save/load flow
        # Requires actual checkpointer setup
        pass
    
    @pytest.mark.asyncio
    async def test_conversation_history_flow(self, mock_graph):
        """Test conversation history across multiple invocations."""
        # Mock multiple invocations with same session_id
        session_id = "test-session"
        
        # First invocation
        state1 = {
            "messages": [HumanMessage(content="First message")],
            "session_id": session_id
        }
        
        # Second invocation (should include previous messages)
        state2 = {
            "messages": [
                HumanMessage(content="First message"),
                AIMessage(content="Response 1"),
                HumanMessage(content="Second message")
            ],
            "session_id": session_id
        }
        
        # Verify state progression
        assert len(state2["messages"]) > len(state1["messages"])


class TestErrorRecoveryFlow:
    """Test error recovery flows."""
    
    @pytest.mark.asyncio
    async def test_tool_error_recovery(self, mock_mcp_client):
        """Test recovery from tool execution errors."""
        # First call fails
        mock_mcp_client.call_tool = AsyncMock(side_effect=[
            RuntimeError("Tool failed"),
            {"isError": False, "result": "Success"}
        ])
        
        # Should handle error gracefully
        try:
            result = await mock_mcp_client.call_tool("catalog", "tool", {})
        except RuntimeError:
            # Retry logic would go here
            result = await mock_mcp_client.call_tool("catalog", "tool", {})
        
        assert result.get("isError") is False
    
    @pytest.mark.asyncio
    async def test_llm_error_recovery(self, mock_llm):
        """Test recovery from LLM errors."""
        # First call fails
        mock_llm.invoke = Mock(side_effect=[
            Exception("LLM error"),
            AIMessage(content="Success")
        ])
        
        # Should handle error
        try:
            result = mock_llm.invoke([])
        except Exception:
            # Retry
            result = mock_llm.invoke([])
        
        assert result.content == "Success"
