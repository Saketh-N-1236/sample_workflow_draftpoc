"""Tests for state converter module."""

import pytest
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from agent.state_converter import (
    normalize_message_content,
    convert_to_langchain_messages,
    convert_from_langchain_messages,
    convert_langgraph_state_to_agent
)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage


class TestStateConverter:
    """Test suite for state converter."""
    
    def test_normalize_message_content_string(self):
        """Test normalizing string content."""
        content = "Simple string content"
        result = normalize_message_content(content)
        assert result == "Simple string content"
        assert isinstance(result, str)
    
    def test_normalize_message_content_list(self):
        """Test normalizing list content (Gemini format)."""
        content = [
            {"type": "text", "text": "First part"},
            {"type": "text", "text": "Second part"}
        ]
        result = normalize_message_content(content)
        assert "First part" in result
        assert "Second part" in result
    
    def test_normalize_message_content_list_simple(self):
        """Test normalizing simple list content."""
        content = ["part1", "part2"]
        result = normalize_message_content(content)
        assert "part1" in result
        assert "part2" in result
    
    def test_normalize_message_content_none(self):
        """Test normalizing None content."""
        result = normalize_message_content(None)
        assert result == ""
    
    def test_normalize_message_content_dict_with_text(self):
        """Test normalizing dict with text key."""
        content = {"text": "Dict text content"}
        result = normalize_message_content(content)
        assert "Dict text content" in result
    
    def test_convert_to_langchain_messages(self):
        """Test converting custom messages to LangChain messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "system", "content": "System message"}
        ]
        
        langchain_messages = convert_to_langchain_messages(messages)
        
        assert len(langchain_messages) == 3
        assert isinstance(langchain_messages[0], HumanMessage)
        assert isinstance(langchain_messages[1], AIMessage)
        assert isinstance(langchain_messages[2], SystemMessage)
    
    def test_convert_to_langchain_messages_tool(self):
        """Test converting tool messages."""
        messages = [
            {"role": "tool", "content": "Tool result", "tool_call_id": "tc_1"}
        ]
        
        langchain_messages = convert_to_langchain_messages(messages)
        
        assert len(langchain_messages) == 1
        assert isinstance(langchain_messages[0], ToolMessage)
        assert langchain_messages[0].tool_call_id == "tc_1"
    
    def test_convert_from_langchain_messages(self):
        """Test converting LangChain messages to custom format."""
        langchain_messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there")
        ]
        
        custom_messages = convert_from_langchain_messages(langchain_messages)
        
        assert len(custom_messages) == 2
        assert custom_messages[0]["role"] == "user"
        assert custom_messages[1]["role"] == "assistant"
    
    def test_convert_from_langchain_messages_with_tool_calls(self):
        """Test converting AIMessage with tool calls."""
        mock_tool_call = MagicMock()
        mock_tool_call.name = "test_tool"
        mock_tool_call.id = "tc_1"
        mock_tool_call.args = {"param": "value"}
        
        ai_message = AIMessage(content="", tool_calls=[mock_tool_call])
        langchain_messages = [ai_message]
        
        custom_messages = convert_from_langchain_messages(langchain_messages)
        
        assert len(custom_messages) == 1
        assert custom_messages[0]["role"] == "assistant"
        assert "tool_calls" in custom_messages[0]
        assert len(custom_messages[0]["tool_calls"]) == 1
    
    def test_convert_langgraph_state_to_agent(self):
        """Test converting LangGraph state to agent state."""
        langgraph_state = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi")
            ],
            "tool_calls": [],
            "tool_results": [],
            "request_id": "test_123",
            "session_id": "session_123",
            "current_step": 1,
            "error": None,
            "finished": True,
            "prompt_version": "v1",
            "model_name": "gemini-2.5-flash"
        }
        
        agent_state = convert_langgraph_state_to_agent(langgraph_state)
        
        assert agent_state["request_id"] == "test_123"
        assert agent_state["session_id"] == "session_123"
        assert agent_state["current_step"] == 1
        assert agent_state["finished"] is True
        assert len(agent_state["messages"]) == 2
    
    def test_convert_langgraph_state_to_agent_with_tool_calls(self):
        """Test converting state with tool calls."""
        mock_tool_call = MagicMock()
        mock_tool_call.name = "test_tool"
        mock_tool_call.id = "tc_1"
        mock_tool_call.args = {"param": "value"}
        
        ai_message = AIMessage(content="", tool_calls=[mock_tool_call])
        tool_message = ToolMessage(content="Result", tool_call_id="tc_1")
        
        langgraph_state = {
            "messages": [ai_message, tool_message],
            "tool_calls": [],
            "tool_results": [],
            "request_id": "test_123",
            "session_id": None,
            "current_step": 0,
            "error": None,
            "finished": False,
            "prompt_version": "v1",
            "model_name": "gemini-2.5-flash"
        }
        
        agent_state = convert_langgraph_state_to_agent(langgraph_state)
        
        assert len(agent_state["tool_calls"]) > 0
        assert len(agent_state["tool_results"]) > 0
