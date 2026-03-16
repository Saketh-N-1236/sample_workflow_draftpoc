"""Unit tests for state converter."""

import pytest
from unittest.mock import Mock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from agent.state_converter import (
    normalize_message_content,
    convert_to_langchain_messages,
    convert_langgraph_state_to_agent
)


class TestNormalizeMessageContent:
    """Test message content normalization."""
    
    def test_string_content(self):
        """Test normalization of string content."""
        content = "Hello, world!"
        result = normalize_message_content(content)
        assert result == "Hello, world!"
    
    def test_none_content(self):
        """Test normalization of None content."""
        result = normalize_message_content(None)
        assert result == ""
    
    def test_list_content_blocks(self):
        """Test normalization of list content blocks (Gemini format)."""
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "World"}
        ]
        result = normalize_message_content(content)
        assert "Hello" in result
        assert "World" in result
    
    def test_list_content_simple(self):
        """Test normalization of simple list content."""
        content = ["Hello", "World"]
        result = normalize_message_content(content)
        assert "Hello" in result
        assert "World" in result
    
    def test_dict_content(self):
        """Test normalization of dict content."""
        content = {"text": "Hello"}
        result = normalize_message_content(content)
        assert "Hello" in result
    
    def test_other_type_content(self):
        """Test normalization of other content types."""
        content = 12345
        result = normalize_message_content(content)
        assert result == "12345"


class TestConvertToLangChainMessages:
    """Test conversion to LangChain messages."""
    
    def test_convert_user_message(self):
        """Test conversion of user message."""
        messages = [{"role": "user", "content": "Hello"}]
        result = convert_to_langchain_messages(messages)
        
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "Hello"
    
    def test_convert_assistant_message(self):
        """Test conversion of assistant message."""
        messages = [{"role": "assistant", "content": "Hi there"}]
        result = convert_to_langchain_messages(messages)
        
        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "Hi there"
    
    def test_convert_system_message(self):
        """Test conversion of system message."""
        messages = [{"role": "system", "content": "You are a helpful assistant"}]
        result = convert_to_langchain_messages(messages)
        
        assert len(result) == 1
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "You are a helpful assistant"
    
    def test_convert_tool_message(self):
        """Test conversion of tool message."""
        messages = [{
            "role": "tool",
            "content": "Tool result",
            "tool_call_id": "call_123"
        }]
        result = convert_to_langchain_messages(messages)
        
        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert result[0].content == "Tool result"
        assert result[0].tool_call_id == "call_123"
    
    def test_convert_multiple_messages(self):
        """Test conversion of multiple messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "How are you?"}
        ]
        result = convert_to_langchain_messages(messages)
        
        assert len(result) == 3
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], HumanMessage)
    
    def test_convert_empty_list(self):
        """Test conversion of empty message list."""
        result = convert_to_langchain_messages([])
        assert result == []
    
    def test_convert_unknown_role(self):
        """Test conversion of message with unknown role."""
        messages = [{"role": "unknown", "content": "Test"}]
        result = convert_to_langchain_messages(messages)
        
        # Should default to HumanMessage
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)


class TestConvertLangGraphStateToAgent:
    """Test LangGraph state to AgentState conversion."""
    
    def test_basic_conversion(self, sample_langgraph_state):
        """Test basic state conversion."""
        result = convert_langgraph_state_to_agent(sample_langgraph_state)
        
        assert "messages" in result
        assert "request_id" in result
        assert "session_id" in result
        assert result["request_id"] == "test-request-123"
        assert result["session_id"] == "test-session-456"
    
    def test_message_conversion(self, sample_langgraph_state):
        """Test message conversion in state."""
        result = convert_langgraph_state_to_agent(sample_langgraph_state)
        
        messages = result["messages"]
        assert len(messages) > 0
        assert messages[0]["role"] == "user"
        assert "What tables" in messages[0]["content"]
    
    def test_tool_calls_extraction(self):
        """Test extraction of tool calls from state."""
        state = {
            "messages": [
                HumanMessage(content="List tables"),
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "catalog_list_tables",
                        "args": {},
                        "id": "call_123"
                    }]
                )
            ],
            "request_id": "test-123",
            "session_id": "session-123"
        }
        
        result = convert_langgraph_state_to_agent(state)
        
        assert "tool_calls" in result
        assert len(result["tool_calls"]) > 0
    
    def test_tool_results_extraction(self):
        """Test extraction of tool results from state."""
        state = {
            "messages": [
                HumanMessage(content="List tables"),
                AIMessage(content="", tool_calls=[{"name": "catalog_list_tables", "args": {}, "id": "call_123"}]),
                ToolMessage(content='{"tables": ["users"]}', tool_call_id="call_123")
            ],
            "request_id": "test-123",
            "session_id": "session-123"
        }
        
        result = convert_langgraph_state_to_agent(state)
        
        assert "tool_results" in result
        assert len(result["tool_results"]) > 0
    
    def test_empty_state(self):
        """Test conversion of empty state."""
        state = {
            "messages": [],
            "request_id": "test-123"
        }
        
        result = convert_langgraph_state_to_agent(state)
        
        assert result["messages"] == []
        assert result["request_id"] == "test-123"
