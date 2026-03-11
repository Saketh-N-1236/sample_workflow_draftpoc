"""Unit tests for LangGraph builder."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from langgraph.graph import StateGraph, END

from agent.langgraph_builder import LangGraphAgentBuilder
from agent.langgraph_state import LangGraphAgentState


class TestLangGraphAgentBuilder:
    """Test LangGraph agent builder."""
    
    def test_builder_initialization(self, mock_langchain_tools):
        """Test builder initialization."""
        builder = LangGraphAgentBuilder(tools=mock_langchain_tools)
        
        assert builder.tools == mock_langchain_tools
        assert builder._graph is None
    
    def test_build_creates_graph(self, mock_langchain_tools):
        """Test that build creates a StateGraph."""
        with patch('agent.langgraph_builder.StateGraph') as mock_graph_class, \
             patch('agent.langgraph_builder.set_available_tools'), \
             patch('agent.langgraph_builder.call_model'), \
             patch('agent.langgraph_builder.should_continue'), \
             patch('agent.langgraph_builder.ToolNode') as mock_tool_node, \
             patch('agent.langgraph_builder.SqliteSaver') as mock_checkpointer:
            
            mock_graph_instance = Mock()
            mock_graph_class.return_value = mock_graph_instance
            mock_graph_instance.add_node = Mock(return_value=None)
            mock_graph_instance.set_entry_point = Mock(return_value=None)
            mock_graph_instance.add_conditional_edges = Mock(return_value=None)
            mock_graph_instance.add_edge = Mock(return_value=None)
            mock_graph_instance.compile = Mock(return_value=Mock())
            
            mock_tool_node.return_value = Mock()
            mock_checkpointer.from_conn_string = Mock(return_value=Mock())
            
            builder = LangGraphAgentBuilder(tools=mock_langchain_tools)
            graph = builder.build()
            
            assert graph is not None
            mock_graph_class.assert_called_once_with(LangGraphAgentState)
    
    def test_build_without_tools(self):
        """Test building graph without tools."""
        with patch('agent.langgraph_builder.StateGraph') as mock_graph_class, \
             patch('agent.langgraph_builder.set_available_tools'), \
             patch('agent.langgraph_builder.call_model'), \
             patch('agent.langgraph_builder.should_continue'):
            
            mock_graph_instance = Mock()
            mock_graph_class.return_value = mock_graph_instance
            mock_graph_instance.add_node = Mock(return_value=None)
            mock_graph_instance.set_entry_point = Mock(return_value=None)
            mock_graph_instance.add_conditional_edges = Mock(return_value=None)
            mock_graph_instance.add_edge = Mock(return_value=None)
            mock_graph_instance.compile = Mock(return_value=Mock())
            
            builder = LangGraphAgentBuilder(tools=[])
            graph = builder.build()
            
            assert graph is not None
    
    def test_build_with_checkpointer(self, mock_langchain_tools, temp_checkpoint_db):
        """Test building graph with checkpointer."""
        with patch('agent.langgraph_builder.StateGraph') as mock_graph_class, \
             patch('agent.langgraph_builder.set_available_tools'), \
             patch('agent.langgraph_builder.call_model'), \
             patch('agent.langgraph_builder.should_continue'), \
             patch('agent.langgraph_builder.ToolNode') as mock_tool_node, \
             patch('agent.langgraph_builder.SqliteSaver') as mock_checkpointer, \
             patch('agent.langgraph_builder.get_settings') as mock_settings:
            
            mock_settings.return_value.checkpoint_db_path = str(temp_checkpoint_db)
            
            mock_graph_instance = Mock()
            mock_graph_class.return_value = mock_graph_instance
            mock_graph_instance.add_node = Mock(return_value=None)
            mock_graph_instance.set_entry_point = Mock(return_value=None)
            mock_graph_instance.add_conditional_edges = Mock(return_value=None)
            mock_graph_instance.add_edge = Mock(return_value=None)
            mock_graph_instance.compile = Mock(return_value=Mock())
            
            mock_checkpointer_instance = Mock()
            mock_checkpointer.from_conn_string = Mock(return_value=mock_checkpointer_instance)
            
            builder = LangGraphAgentBuilder(tools=mock_langchain_tools)
            graph = builder.build()
            
            assert graph is not None
            # Checkpointer should be created
            mock_checkpointer.from_conn_string.assert_called()
    
    def test_build_without_checkpointer(self, mock_langchain_tools):
        """Test building graph without checkpointer."""
        with patch('agent.langgraph_builder.StateGraph') as mock_graph_class, \
             patch('agent.langgraph_builder.set_available_tools'), \
             patch('agent.langgraph_builder.call_model'), \
             patch('agent.langgraph_builder.should_continue'), \
             patch('agent.langgraph_builder.ToolNode') as mock_tool_node, \
             patch('agent.langgraph_builder.get_settings') as mock_settings:
            
            mock_settings.return_value.checkpoint_db_path = None
            
            mock_graph_instance = Mock()
            mock_graph_class.return_value = mock_graph_instance
            mock_graph_instance.add_node = Mock(return_value=None)
            mock_graph_instance.set_entry_point = Mock(return_value=None)
            mock_graph_instance.add_conditional_edges = Mock(return_value=None)
            mock_graph_instance.add_edge = Mock(return_value=None)
            mock_graph_instance.compile = Mock(return_value=Mock())
            
            builder = LangGraphAgentBuilder(tools=mock_langchain_tools)
            graph = builder.build()
            
            assert graph is not None
    
    def test_get_graph(self, mock_langchain_tools):
        """Test getting the built graph."""
        with patch('agent.langgraph_builder.StateGraph') as mock_graph_class, \
             patch('agent.langgraph_builder.set_available_tools'), \
             patch('agent.langgraph_builder.call_model'), \
             patch('agent.langgraph_builder.should_continue'), \
             patch('agent.langgraph_builder.ToolNode'), \
             patch('agent.langgraph_builder.SqliteSaver'):
            
            mock_graph_instance = Mock()
            mock_graph_class.return_value = mock_graph_instance
            mock_graph_instance.add_node = Mock(return_value=None)
            mock_graph_instance.set_entry_point = Mock(return_value=None)
            mock_graph_instance.add_conditional_edges = Mock(return_value=None)
            mock_graph_instance.add_edge = Mock(return_value=None)
            compiled_graph = Mock()
            mock_graph_instance.compile = Mock(return_value=compiled_graph)
            
            builder = LangGraphAgentBuilder(tools=mock_langchain_tools)
            builder.build()
            
            graph = builder.get_graph()
            
            assert graph is not None
            assert graph == compiled_graph
    
    def test_get_graph_before_build(self, mock_langchain_tools):
        """Test getting graph before building."""
        builder = LangGraphAgentBuilder(tools=mock_langchain_tools)
        
        graph = builder.get_graph()
        
        # Should return None if not built
        assert graph is None
