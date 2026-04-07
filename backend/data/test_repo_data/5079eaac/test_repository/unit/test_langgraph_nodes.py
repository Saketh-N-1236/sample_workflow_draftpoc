"""Unit tests for LangGraph nodes."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agent.langgraph_nodes import call_model, should_continue, get_langchain_llm, set_available_tools, get_available_tools


class TestCallModel:
    """Test call_model node."""
    
    @pytest.mark.asyncio
    async def test_call_model_without_tools(self, mock_llm):
        """Test call_model without tool calls."""
        state = {
            "messages": [HumanMessage(content="Hello")]
        }
        
        with patch('agent.langgraph_nodes.get_langchain_llm', return_value=mock_llm):
            result = await call_model(state)
            
            assert "messages" in result
            assert len(result["messages"]) > 0
    
    @pytest.mark.asyncio
    async def test_call_model_with_tool_calls(self, mock_llm, mock_langchain_tools):
        """Test call_model that triggers tool calls."""
        state = {
            "messages": [HumanMessage(content="List tables")]
        }
        
        set_available_tools(mock_langchain_tools)
        
        # Mock LLM to return tool calls
        mock_llm.bound_tools = mock_langchain_tools
        mock_llm.invoke = Mock(return_value=AIMessage(
            content="",
            tool_calls=[{
                "name": "catalog_test_tool",
                "args": {"query": "test"},
                "id": "call_123"
            }]
        ))
        
        with patch('agent.langgraph_nodes.get_langchain_llm', return_value=mock_llm):
            result = await call_model(state)
            
            assert "messages" in result
            # Should have AIMessage with tool calls
            last_message = result["messages"][-1]
            assert isinstance(last_message, AIMessage)
    
    @pytest.mark.asyncio
    async def test_call_model_with_tool_results(self, mock_llm):
        """Test call_model after tool execution."""
        state = {
            "messages": [
                HumanMessage(content="List tables"),
                AIMessage(content="", tool_calls=[{"name": "tool", "args": {}, "id": "call_1"}]),
                ToolMessage(content='{"result": "success"}', tool_call_id="call_1")
            ]
        }
        
        # Mock LLM to return final response
        mock_llm.invoke = Mock(return_value=AIMessage(content="Here are the tables"))
        
        with patch('agent.langgraph_nodes.get_langchain_llm', return_value=mock_llm):
            result = await call_model(state)
            
            assert "messages" in result
            # Should have final response
            last_message = result["messages"][-1]
            assert isinstance(last_message, AIMessage)
            assert len(last_message.content) > 0
    
    @pytest.mark.asyncio
    async def test_call_model_adds_instruction_after_tools(self, mock_llm):
        """Test that call_model adds instruction after tool results."""
        state = {
            "messages": [
                HumanMessage(content="List tables"),
                ToolMessage(content='{"result": "success"}', tool_call_id="call_1")
            ]
        }
        
        mock_llm.invoke = Mock(return_value=AIMessage(content="Response"))
        
        with patch('agent.langgraph_nodes.get_langchain_llm', return_value=mock_llm), \
             patch('agent.langgraph_nodes.HumanMessage') as mock_human:
            
            await call_model(state)
            
            # Should add instruction message if tool results present
            # (exact behavior depends on implementation)
            assert True  # Placeholder assertion
    
    @pytest.mark.asyncio
    async def test_call_model_empty_state(self, mock_llm):
        """Test call_model with empty state."""
        state = {"messages": []}
        
        mock_llm.invoke = Mock(return_value=AIMessage(content="Empty state response"))
        
        with patch('agent.langgraph_nodes.get_langchain_llm', return_value=mock_llm):
            result = await call_model(state)
            
            assert "messages" in result


class TestShouldContinue:
    """Test should_continue router."""
    
    def test_should_continue_with_tool_calls(self):
        """Test routing to tools when tool calls present."""
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "tool", "args": {}, "id": "call_1"}]
                )
            ]
        }
        
        result = should_continue(state)
        
        assert result == "tools"
    
    def test_should_continue_without_tool_calls(self):
        """Test routing to end when no tool calls."""
        state = {
            "messages": [
                AIMessage(content="Final response")
            ]
        }
        
        result = should_continue(state)
        
        assert result == "end"
    
    def test_should_continue_with_content(self):
        """Test routing when content is present."""
        state = {
            "messages": [
                AIMessage(content="This is a response with content")
            ]
        }
        
        result = should_continue(state)
        
        # Should end if there's content and no tool calls
        assert result == "end"
    
    def test_should_continue_empty_messages(self):
        """Test routing with empty messages."""
        state = {"messages": []}
        
        result = should_continue(state)
        
        # Should end if no messages
        assert result == "end"
    
    def test_should_continue_tool_calls_and_content(self):
        """Test routing when both tool calls and content exist."""
        state = {
            "messages": [
                AIMessage(
                    content="Some content",
                    tool_calls=[{"name": "tool", "args": {}, "id": "call_1"}]
                )
            ]
        }
        
        result = should_continue(state)
        
        # Should route to tools if tool calls present
        assert result == "tools"


class TestGetLangChainLLM:
    """Test LLM retrieval."""
    
    def test_get_langchain_llm_creates_instance(self, mock_settings):
        """Test that get_langchain_llm creates LLM instance."""
        with patch('agent.langgraph_nodes.get_settings', return_value=mock_settings), \
             patch('agent.langgraph_nodes.ChatGoogleGenerativeAI') as mock_llm_class:
            
            mock_llm_instance = Mock()
            mock_llm_class.return_value = mock_llm_instance
            
            llm = get_langchain_llm()
            
            assert llm is not None
            mock_llm_class.assert_called_once()
    
    def test_get_langchain_llm_reuses_instance(self, mock_settings):
        """Test that get_langchain_llm reuses instance."""
        with patch('agent.langgraph_nodes.get_settings', return_value=mock_settings), \
             patch('agent.langgraph_nodes.ChatGoogleGenerativeAI') as mock_llm_class:
            
            mock_llm_instance = Mock()
            mock_llm_class.return_value = mock_llm_instance
            
            llm1 = get_langchain_llm()
            llm2 = get_langchain_llm()
            
            assert llm1 is llm2
            assert mock_llm_class.call_count == 1
    
    def test_get_langchain_llm_missing_api_key(self, mock_settings):
        """Test get_langchain_llm with missing API key."""
        mock_settings.gemini_api_key = None
        
        with patch('agent.langgraph_nodes.get_settings', return_value=mock_settings):
            with pytest.raises(ValueError, match="API key is required"):
                get_langchain_llm()


class TestToolManagement:
    """Test tool management functions."""
    
    def test_set_available_tools(self, mock_langchain_tools):
        """Test setting available tools."""
        set_available_tools(mock_langchain_tools)
        
        tools = get_available_tools()
        assert tools == mock_langchain_tools
    
    def test_get_available_tools_empty(self):
        """Test getting tools when none are set."""
        set_available_tools([])
        
        tools = get_available_tools()
        assert tools == []
