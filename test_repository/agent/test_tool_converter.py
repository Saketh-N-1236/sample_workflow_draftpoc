"""Tests for tool converter module."""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from agent.tool_converter import (
    json_schema_to_pydantic,
    mcp_tool_to_langchain,
    convert_mcp_tools_to_langchain
)


class TestToolConverter:
    """Test suite for tool converter."""
    
    @pytest.fixture
    def sample_json_schema(self):
        """Sample JSON schema for testing."""
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "First parameter"
                },
                "param2": {
                    "type": "integer",
                    "description": "Second parameter",
                    "default": 10
                },
                "param3": {
                    "type": "boolean",
                    "description": "Third parameter"
                }
            },
            "required": ["param1"]
        }
    
    @pytest.fixture
    def sample_mcp_tool(self):
        """Sample MCP tool for testing."""
        tool = MagicMock()
        tool.name = "test_tool"
        tool.description = "Test tool description"
        tool.inputSchema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
        return tool
    
    def test_json_schema_to_pydantic_string(self, sample_json_schema):
        """Test JSON schema to Pydantic conversion for string type."""
        model = json_schema_to_pydantic(sample_json_schema)
        
        # Test that model can be instantiated
        instance = model(param1="test")
        assert instance.param1 == "test"
        assert instance.param2 == 10  # Default value
        assert instance.param3 is None  # Optional field
    
    def test_json_schema_to_pydantic_integer(self):
        """Test JSON schema to Pydantic conversion for integer type."""
        schema = {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Count value"
                }
            },
            "required": ["count"]
        }
        
        model = json_schema_to_pydantic(schema)
        instance = model(count=5)
        assert instance.count == 5
        assert isinstance(instance.count, int)
    
    def test_json_schema_to_pydantic_array(self):
        """Test JSON schema to Pydantic conversion for array type."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of items"
                }
            },
            "required": ["items"]
        }
        
        model = json_schema_to_pydantic(schema)
        instance = model(items=["item1", "item2"])
        assert instance.items == ["item1", "item2"]
        assert isinstance(instance.items, list)
    
    def test_json_schema_to_pydantic_empty(self):
        """Test JSON schema to Pydantic conversion for empty schema."""
        schema = {
            "type": "object",
            "properties": {}
        }
        
        model = json_schema_to_pydantic(schema)
        instance = model()
        assert instance is not None
    
    @pytest.mark.asyncio
    async def test_mcp_tool_to_langchain(self, sample_mcp_tool):
        """Test MCP tool to LangChain conversion."""
        async def mock_tool_executor(server_name, tool_name, arguments):
            return {
                "result": '{"status": "success"}',
                "isError": False
            }
        
        tool = mcp_tool_to_langchain(
            sample_mcp_tool,
            "test_server",
            mock_tool_executor
        )
        
        assert tool.name == "test_server_test_tool"
        assert tool.description == "Test tool description"
        assert tool.args_schema is not None
        
        # Test tool execution
        result = await tool.ainvoke(query="test query")
        assert "status" in result or "success" in result
    
    @pytest.mark.asyncio
    async def test_mcp_tool_to_langchain_error_handling(self, sample_mcp_tool):
        """Test MCP tool to LangChain conversion with error handling."""
        async def mock_tool_executor(server_name, tool_name, arguments):
            return {
                "result": "",
                "isError": True,
                "error": "Test error"
            }
        
        tool = mcp_tool_to_langchain(
            sample_mcp_tool,
            "test_server",
            mock_tool_executor
        )
        
        result = await tool.ainvoke(query="test query")
        assert "Error" in result
    
    def test_convert_mcp_tools_to_langchain(self, sample_mcp_tool):
        """Test conversion of multiple MCP tools."""
        async def mock_tool_executor(server_name, tool_name, arguments):
            return {"result": '{"status": "success"}', "isError": False}
        
        mcp_tools = {
            "server1": [sample_mcp_tool],
            "server2": [sample_mcp_tool]
        }
        
        langchain_tools = convert_mcp_tools_to_langchain(
            mcp_tools,
            mock_tool_executor
        )
        
        assert len(langchain_tools) == 2
        assert all(tool.name.startswith("server") for tool in langchain_tools)
    
    def test_convert_mcp_tools_to_langchain_empty(self):
        """Test conversion with empty tool list."""
        async def mock_tool_executor(server_name, tool_name, arguments):
            return {"result": '{}', "isError": False}
        
        mcp_tools = {}
        
        langchain_tools = convert_mcp_tools_to_langchain(
            mcp_tools,
            mock_tool_executor
        )
        
        assert len(langchain_tools) == 0
    
    def test_convert_mcp_tools_to_langchain_conversion_error(self):
        """Test conversion with tool conversion error."""
        async def mock_tool_executor(server_name, tool_name, arguments):
            return {"result": '{}', "isError": False}
        
        # Create a tool with invalid schema
        bad_tool = MagicMock()
        bad_tool.name = "bad_tool"
        bad_tool.description = "Bad tool"
        bad_tool.inputSchema = "invalid_schema"  # Not a dict
        
        mcp_tools = {
            "server1": [bad_tool]
        }
        
        # Should handle error gracefully
        langchain_tools = convert_mcp_tools_to_langchain(
            mcp_tools,
            mock_tool_executor
        )
        
        # May return empty list or handle error
        assert isinstance(langchain_tools, list)
