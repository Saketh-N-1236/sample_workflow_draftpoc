"""Tests for LangGraph builder module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from agent.langgraph_builder import LangGraphAgentBuilder


class TestLangGraphBuilder:
    """Test suite for LangGraphAgentBuilder."""
    
    @pytest.fixture
    def mock_tools(self):
        """Create mock tools."""
        from unittest.mock import MagicMock
        tool1 = MagicMock()
        tool1.name = "tool1"
        tool2 = MagicMock()
        tool2.name = "tool2"
        return [tool1, tool2]
    
    def test_builder_initialization(self, mock_tools):
        """Test builder initialization."""
        builder = LangGraphAgentBuilder(tools=mock_tools)
        assert builder.tools == mock_tools
        assert builder._graph is None
    
    def test_builder_initialization_no_tools(self):
        """Test builder initialization with no tools."""
        builder = LangGraphAgentBuilder(tools=[])
        assert builder.tools == []
    
    def test_build_graph(self, mock_tools):
        """Test building the graph."""
        with patch('agent.langgraph_builder.StateGraph') as mock_graph_class:
            with patch('agent.langgraph_builder.set_available_tools') as mock_set_tools:
                with patch('agent.langgraph_builder.call_model') as mock_call_model:
                    with patch('agent.langgraph_builder.should_continue') as mock_should_continue:
                        with patch('agent.langgraph_builder.ToolNode') as mock_tool_node:
                            with patch('agent.langgraph_builder.get_settings') as mock_settings:
                                mock_settings.return_value.checkpoint_db_path = "test.db"
                                
                                mock_graph = MagicMock()
                                mock_graph_instance = MagicMock()
                                mock_graph_instance.compile.return_value = mock_graph
                                mock_graph_class.return_value = mock_graph_instance
                                
                                builder = LangGraphAgentBuilder(tools=mock_tools)
                                result = builder.build()
                                
                                assert result is not None
                                mock_set_tools.assert_called_once_with(mock_tools)
    
    def test_build_graph_no_tools(self):
        """Test building graph with no tools."""
        with patch('agent.langgraph_builder.StateGraph') as mock_graph_class:
            with patch('agent.langgraph_builder.set_available_tools') as mock_set_tools:
                with patch('agent.langgraph_builder.get_settings') as mock_settings:
                    mock_settings.return_value.checkpoint_db_path = "test.db"
                    
                    mock_graph = MagicMock()
                    mock_graph_instance = MagicMock()
                    mock_graph_instance.compile.return_value = mock_graph
                    mock_graph_class.return_value = mock_graph_instance
                    
                    builder = LangGraphAgentBuilder(tools=[])
                    result = builder.build()
                    
                    assert result is not None
    
    def test_get_graph(self, mock_tools):
        """Test getting the compiled graph."""
        with patch('agent.langgraph_builder.StateGraph') as mock_graph_class:
            with patch('agent.langgraph_builder.set_available_tools'):
                with patch('agent.langgraph_builder.get_settings') as mock_settings:
                    mock_settings.return_value.checkpoint_db_path = "test.db"
                    
                    mock_graph = MagicMock()
                    mock_graph_instance = MagicMock()
                    mock_graph_instance.compile.return_value = mock_graph
                    mock_graph_class.return_value = mock_graph_instance
                    
                    builder = LangGraphAgentBuilder(tools=mock_tools)
                    builder.build()
                    
                    result = builder.get_graph()
                    assert result == mock_graph
    
    def test_get_graph_not_built(self):
        """Test getting graph before building."""
        builder = LangGraphAgentBuilder(tools=[])
        result = builder.get_graph()
        assert result is None
