"""Tests for LangGraph agent implementation."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from typing import Dict, Any

# Import agent modules
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from agent.langgraph_agent import LangGraphAgent
from agent.langgraph_state import LangGraphAgentState, create_langgraph_initial_state
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


class TestLangGraphAgent:
    """Test suite for LangGraphAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a LangGraphAgent instance."""
        return LangGraphAgent()
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent, mock_mcp_client):
        """Test agent initialization."""
        with patch('agent.langgraph_agent.MCPSDKClient', return_value=mock_mcp_client):
            with patch('agent.langgraph_agent.convert_mcp_tools_to_langchain', return_value=[]):
                with patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"):
                    with patch('agent.langgraph_agent.LangGraphAgentBuilder') as mock_builder:
                        mock_graph = MagicMock()
                        mock_builder_instance = MagicMock()
                        mock_builder_instance.build.return_value = mock_graph
                        mock_builder.return_value = mock_builder_instance
                        
                        await agent.initialize()
                        
                        assert agent._initialized is True
                        assert agent.graph is not None
                        mock_mcp_client.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_initialization_failure_no_servers(self, agent):
        """Test agent initialization failure when MCP servers are not available."""
        with patch('agent.langgraph_agent.MCPSDKClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.initialize = AsyncMock()
            mock_client.discover_all_tools = AsyncMock(side_effect=RuntimeError("No servers available"))
            mock_client_class.return_value = mock_client
            
            with pytest.raises(RuntimeError, match="Agent initialization failed"):
                await agent.initialize()
    
    @pytest.mark.asyncio
    async def test_agent_initialization_no_tools(self, agent, mock_mcp_client):
        """Test agent initialization when no tools are available."""
        with patch('agent.langgraph_agent.MCPSDKClient', return_value=mock_mcp_client):
            with patch('agent.langgraph_agent.convert_mcp_tools_to_langchain', return_value=[]):
                with patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"):
                    with patch('agent.langgraph_agent.LangGraphAgentBuilder') as mock_builder:
                        mock_graph = MagicMock()
                        mock_builder_instance = MagicMock()
                        mock_builder_instance.build.return_value = mock_graph
                        mock_builder.return_value = mock_builder_instance
                        
                        await agent.initialize()
                        
                        # Should still initialize even with no tools
                        assert agent._initialized is True
    
    @pytest.mark.asyncio
    async def test_agent_invoke(self, agent, mock_mcp_client):
        """Test agent invocation."""
        # Setup mocks
        mock_graph = MagicMock()
        mock_final_state = {
            "messages": [AIMessage(content="Test response")],
            "request_id": "test_123",
            "session_id": None,
            "tool_calls": [],
            "tool_results": [],
            "current_step": 1,
            "finished": True,
            "error": None,
            "prompt_version": "v1",
            "model_name": "gemini-2.5-flash"
        }
        mock_graph.ainvoke = AsyncMock(return_value=mock_final_state)
        agent.graph = mock_graph
        agent._initialized = True
        agent._has_checkpointer = False
        
        with patch('agent.langgraph_agent.create_langgraph_initial_state', return_value=mock_final_state):
            with patch('agent.langgraph_agent.convert_langgraph_state_to_agent', return_value=mock_final_state):
                with patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"):
                    with patch('agent.langgraph_nodes.get_available_tools', return_value=[]):
                        result = await agent.invoke(
                            user_message="Test message",
                            request_id="test_123"
                        )
                        
                        assert result is not None
                        assert "messages" in result
                        mock_graph.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_invoke_with_session_id(self, agent, mock_mcp_client):
        """Test agent invocation with session ID."""
        mock_graph = MagicMock()
        mock_final_state = {
            "messages": [AIMessage(content="Test response")],
            "request_id": "test_123",
            "session_id": "session_123",
            "tool_calls": [],
            "tool_results": [],
            "current_step": 1,
            "finished": True,
            "error": None,
            "prompt_version": "v1",
            "model_name": "gemini-2.5-flash"
        }
        mock_graph.ainvoke = AsyncMock(return_value=mock_final_state)
        agent.graph = mock_graph
        agent._initialized = True
        agent._has_checkpointer = False
        
        with patch('agent.langgraph_agent.create_langgraph_initial_state', return_value=mock_final_state):
            with patch('agent.langgraph_agent.convert_langgraph_state_to_agent', return_value=mock_final_state):
                with patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"):
                    with patch('agent.langgraph_nodes.get_available_tools', return_value=[]):
                        result = await agent.invoke(
                            user_message="Test message",
                            request_id="test_123",
                            session_id="session_123"
                        )
                        
                        assert result is not None
                        assert result.get("session_id") == "session_123"
    
    @pytest.mark.asyncio
    async def test_agent_stream_invoke(self, agent, mock_mcp_client):
        """Test agent streaming invocation."""
        mock_graph = MagicMock()
        
        # Create mock stream events
        async def mock_stream(*args, **kwargs):
            yield {"agent": {"messages": [AIMessage(content="Thinking...")]}}
            yield {"tools": {"messages": [ToolMessage(content="Tool result", tool_call_id="tc_1")]}}
            yield {"agent": {
                "messages": [AIMessage(content="Final response")],
                "request_id": "test_123",
                "finished": True
            }}
        
        mock_graph.astream = mock_stream
        agent.graph = mock_graph
        agent._initialized = True
        agent._has_checkpointer = False
        
        with patch('agent.langgraph_agent.create_langgraph_initial_state') as mock_init_state:
            mock_init_state.return_value = {
                "messages": [HumanMessage(content="Test")],
                "request_id": "test_123"
            }
            with patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"):
                with patch('agent.langgraph_nodes.get_available_tools', return_value=[]):
                    stages = []
                    async for stage in agent.stream_invoke(
                        user_message="Test message",
                        request_id="test_123"
                    ):
                        stages.append(stage)
                    
                    assert len(stages) > 0
                    assert any(s.get("stage") == "completed" for s in stages)
    
    @pytest.mark.asyncio
    async def test_agent_stream_invoke_error(self, agent, mock_mcp_client):
        """Test agent streaming invocation with error."""
        mock_graph = MagicMock()
        mock_graph.astream = AsyncMock(side_effect=Exception("Test error"))
        agent.graph = mock_graph
        agent._initialized = True
        agent._has_checkpointer = False
        
        with patch('agent.langgraph_agent.create_langgraph_initial_state') as mock_init_state:
            mock_init_state.return_value = {
                "messages": [HumanMessage(content="Test")],
                "request_id": "test_123"
            }
            with patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"):
                with patch('agent.langgraph_nodes.get_available_tools', return_value=[]):
                    stages = []
                    async for stage in agent.stream_invoke(
                        user_message="Test message",
                        request_id="test_123"
                    ):
                        stages.append(stage)
                    
                    # Should yield error stage
                    assert any(s.get("stage") == "error" for s in stages)
    
    @pytest.mark.asyncio
    async def test_agent_close(self, agent, mock_mcp_client):
        """Test agent cleanup."""
        agent.mcp_client = mock_mcp_client
        agent._initialized = True
        
        await agent.close()
        
        mock_mcp_client.close.assert_called_once()
        assert agent._initialized is False
    
    @pytest.mark.asyncio
    async def test_agent_context_manager(self, agent, mock_mcp_client):
        """Test agent as async context manager."""
        with patch('agent.langgraph_agent.MCPSDKClient', return_value=mock_mcp_client):
            with patch('agent.langgraph_agent.convert_mcp_tools_to_langchain', return_value=[]):
                with patch('agent.langgraph_agent.load_system_prompt', return_value="System prompt"):
                    with patch('agent.langgraph_agent.LangGraphAgentBuilder') as mock_builder:
                        mock_graph = MagicMock()
                        mock_builder_instance = MagicMock()
                        mock_builder_instance.build.return_value = mock_graph
                        mock_builder.return_value = mock_builder_instance
                        
                        async with agent:
                            assert agent._initialized is True
                        
                        mock_mcp_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_extract_stage_info_agent_thinking(self, agent):
        """Test stage info extraction for agent thinking."""
        state = {
            "messages": [AIMessage(content="Thinking...")]
        }
        
        stage_info = agent._extract_stage_info("agent", state, 1)
        
        assert stage_info is not None
        assert stage_info["stage"] == "agent_thinking"
    
    @pytest.mark.asyncio
    async def test_agent_extract_stage_info_tool_executing(self, agent):
        """Test stage info extraction for tool execution."""
        from langchain_core.messages import AIMessage
        
        mock_tool_call = MagicMock()
        mock_tool_call.name = "test_tool"
        
        ai_message = AIMessage(content="", tool_calls=[mock_tool_call])
        state = {
            "messages": [ai_message]
        }
        
        stage_info = agent._extract_stage_info("agent", state, 1)
        
        assert stage_info is not None
        assert stage_info["stage"] == "tool_executing"
        assert "test_tool" in stage_info["data"]["tools"]
    
    @pytest.mark.asyncio
    async def test_agent_extract_stage_info_tool_completed(self, agent):
        """Test stage info extraction for tool completion."""
        from langchain_core.messages import AIMessage, ToolMessage
        
        ai_message = AIMessage(content="", tool_calls=[MagicMock(name="test_tool")])
        tool_message = ToolMessage(content="Result", tool_call_id="tc_1")
        
        state = {
            "messages": [ai_message, tool_message]
        }
        
        stage_info = agent._extract_stage_info("tools", state, 1)
        
        assert stage_info is not None
        assert stage_info["stage"] == "tool_completed"
