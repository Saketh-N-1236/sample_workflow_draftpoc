"""Integration tests for agent workflow."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))


class TestAgentWorkflow:
    """Integration tests for agent workflow."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization_workflow(self):
        """Test complete agent initialization workflow."""
        with patch('agent.langgraph_agent.MCPSDKClient') as mock_client_class:
            with patch('agent.langgraph_agent.convert_mcp_tools_to_langchain') as mock_convert:
                with patch('agent.langgraph_agent.load_system_prompt') as mock_prompt:
                    with patch('agent.langgraph_agent.LangGraphAgentBuilder') as mock_builder:
                        # Setup mocks
                        mock_client = MagicMock()
                        mock_client.initialize = AsyncMock()
                        mock_client.discover_all_tools = AsyncMock(return_value={
                            "catalog": [],
                            "sql_query": [],
                            "vector_search": []
                        })
                        mock_client_class.return_value = mock_client
                        
                        mock_convert.return_value = []
                        mock_prompt.return_value = "System prompt"
                        
                        mock_graph = MagicMock()
                        mock_builder_instance = MagicMock()
                        mock_builder_instance.build.return_value = mock_graph
                        mock_builder.return_value = mock_builder_instance
                        
                        # Test initialization
                        from agent.langgraph_agent import LangGraphAgent
                        agent = LangGraphAgent()
                        await agent.initialize()
                        
                        # Verify workflow
                        assert agent._initialized is True
                        mock_client.initialize.assert_called_once()
                        mock_client.discover_all_tools.assert_called_once()
                        mock_convert.assert_called_once()
                        mock_builder.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_invocation_workflow(self):
        """Test complete agent invocation workflow."""
        with patch('agent.langgraph_agent.MCPSDKClient') as mock_client_class:
            with patch('agent.langgraph_agent.convert_mcp_tools_to_langchain') as mock_convert:
                with patch('agent.langgraph_agent.load_system_prompt') as mock_prompt:
                    with patch('agent.langgraph_agent.LangGraphAgentBuilder') as mock_builder:
                        with patch('agent.langgraph_agent.create_langgraph_initial_state') as mock_init_state:
                            with patch('agent.langgraph_agent.convert_langgraph_state_to_agent') as mock_convert_state:
                                # Setup mocks
                                mock_client = MagicMock()
                                mock_client.initialize = AsyncMock()
                                mock_client.discover_all_tools = AsyncMock(return_value={
                                    "catalog": [],
                                    "sql_query": [],
                                    "vector_search": []
                                })
                                mock_client_class.return_value = mock_client
                                
                                mock_convert.return_value = []
                                mock_prompt.return_value = "System prompt"
                                
                                mock_graph = MagicMock()
                                mock_final_state = {
                                    "messages": [{"role": "assistant", "content": "Response"}],
                                    "request_id": "test_123",
                                    "tool_calls": [],
                                    "tool_results": [],
                                    "current_step": 1,
                                    "finished": True,
                                    "error": None,
                                    "prompt_version": "v1",
                                    "model_name": "gemini-2.5-flash"
                                }
                                mock_graph.ainvoke = AsyncMock(return_value=mock_final_state)
                                
                                mock_builder_instance = MagicMock()
                                mock_builder_instance.build.return_value = mock_graph
                                mock_builder.return_value = mock_builder_instance
                                
                                mock_init_state.return_value = mock_final_state
                                mock_convert_state.return_value = mock_final_state
                                
                                # Test invocation
                                from agent.langgraph_agent import LangGraphAgent
                                from agent.langgraph_nodes import get_available_tools
                                
                                with patch('agent.langgraph_nodes.get_available_tools', return_value=[]):
                                    agent = LangGraphAgent()
                                    await agent.initialize()
                                    
                                    result = await agent.invoke(
                                        user_message="Test message",
                                        request_id="test_123"
                                    )
                                    
                                    # Verify workflow
                                    assert result is not None
                                    assert "messages" in result
                                    mock_graph.ainvoke.assert_called_once()
