"""Unit tests for tool converter (MCP to LangChain)."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from agent.tool_converter import (
    json_schema_to_pydantic,
    mcp_tool_to_langchain,
    convert_mcp_tools_to_langchain
)
from mcp.types import Tool as MCPTool


class TestJSONSchemaToPydantic:
    """Test JSON Schema to Pydantic conversion."""
    
    def test_simple_string_schema(self):
        """Test conversion of simple string schema."""
        schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
        
        model = json_schema_to_pydantic(schema)
        assert model is not None
        
        # Test instantiation
        instance = model(query="test")
        assert instance.query == "test"
    
    def test_integer_schema(self):
        """Test conversion of integer schema."""
        schema = {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Result limit"
                }
            },
            "required": ["limit"]
        }
        
        model = json_schema_to_pydantic(schema)
        instance = model(limit=10)
        assert instance.limit == 10
    
    def test_optional_field_with_default(self):
        """Test optional field with default value."""
        schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Result limit",
                    "default": 10
                }
            },
            "required": ["query"]
        }
        
        model = json_schema_to_pydantic(schema)
        instance = model(query="test")
        assert instance.query == "test"
        assert instance.limit == 10  # Default applied
    
    def test_array_schema(self):
        """Test conversion of array schema."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of tags"
                }
            },
            "required": ["tags"]
        }
        
        model = json_schema_to_pydantic(schema)
        instance = model(tags=["tag1", "tag2"])
        assert instance.tags == ["tag1", "tag2"]
    
    def test_nested_object_schema(self):
        """Test conversion of nested object schema."""
        schema = {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "object",
                    "description": "Filter object"
                }
            },
            "required": ["filter"]
        }
        
        model = json_schema_to_pydantic(schema)
        instance = model(filter={"key": "value"})
        assert isinstance(instance.filter, dict)
    
    def test_empty_schema(self):
        """Test conversion of empty schema."""
        schema = {
            "type": "object",
            "properties": {}
        }
        
        model = json_schema_to_pydantic(schema)
        instance = model()
        assert instance is not None


class TestMCPToolToLangChain:
    """Test MCP tool to LangChain conversion."""
    
    @pytest.mark.asyncio
    async def test_basic_conversion(self, mock_mcp_tool):
        """Test basic MCP tool to LangChain conversion."""
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": False, "result": "Success"}
        
        tool = mcp_tool_to_langchain(mock_mcp_tool, "catalog", tool_executor)
        
        assert tool.name == "catalog_test_tool"
        assert "test tool" in tool.description.lower()
        
        # Test tool execution
        result = await tool.ainvoke({"query": "test", "limit": 5})
        assert "Success" in result
    
    @pytest.mark.asyncio
    async def test_tool_execution_with_validation(self, mock_mcp_tool):
        """Test tool execution with parameter validation."""
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": False, "result": json.dumps(arguments)}
        
        tool = mcp_tool_to_langchain(mock_mcp_tool, "catalog", tool_executor)
        
        # Test with valid arguments
        result = await tool.ainvoke({"query": "test", "limit": 10})
        assert "test" in result
    
    @pytest.mark.asyncio
    async def test_tool_execution_with_defaults(self, mock_mcp_tool):
        """Test tool execution applies default values."""
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": False, "result": json.dumps(arguments)}
        
        tool = mcp_tool_to_langchain(mock_mcp_tool, "catalog", tool_executor)
        
        # Test with only required field (default should be applied)
        result = await tool.ainvoke({"query": "test"})
        result_dict = json.loads(result)
        assert result_dict.get("limit") == 10  # Default value
    
    @pytest.mark.asyncio
    async def test_tool_execution_error_handling(self, mock_mcp_tool):
        """Test tool execution error handling."""
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": True, "error": "Tool execution failed"}
        
        tool = mcp_tool_to_langchain(mock_mcp_tool, "catalog", tool_executor)
        
        result = await tool.ainvoke({"query": "test"})
        assert "Error" in result
        assert "Tool execution failed" in result
    
    @pytest.mark.asyncio
    async def test_tool_execution_exception_handling(self, mock_mcp_tool):
        """Test tool execution exception handling."""
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            raise RuntimeError("Connection failed")
        
        tool = mcp_tool_to_langchain(mock_mcp_tool, "catalog", tool_executor)
        
        result = await tool.ainvoke({"query": "test"})
        assert "Error" in result
        assert "Connection failed" in result
    
    def test_tool_name_prefixing(self, mock_mcp_tool):
        """Test that tool names are prefixed with server name."""
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": False, "result": "Success"}
        
        tool = mcp_tool_to_langchain(mock_mcp_tool, "sql_query", tool_executor)
        
        assert tool.name.startswith("sql_query_")
    
    def test_invalid_schema_handling(self):
        """Test handling of invalid JSON schema."""
        invalid_tool = Mock(spec=MCPTool)
        invalid_tool.name = "invalid_tool"
        invalid_tool.description = "Invalid tool"
        invalid_tool.inputSchema = {"invalid": "schema"}
        
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": False, "result": "Success"}
        
        # Should fallback to dict schema
        tool = mcp_tool_to_langchain(invalid_tool, "catalog", tool_executor)
        assert tool is not None


class TestConvertMCPToolsToLangChain:
    """Test batch conversion of MCP tools."""
    
    @pytest.mark.asyncio
    async def test_convert_multiple_servers(self, mock_mcp_tools_dict):
        """Test conversion of tools from multiple servers."""
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": False, "result": "Success"}
        
        tools = convert_mcp_tools_to_langchain(mock_mcp_tools_dict, tool_executor)
        
        assert len(tools) == 3  # One tool from each server
        assert all(tool.name.startswith(("catalog_", "sql_query_", "vector_search_")) for tool in tools)
    
    @pytest.mark.asyncio
    async def test_convert_empty_dict(self):
        """Test conversion of empty tools dictionary."""
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": False, "result": "Success"}
        
        tools = convert_mcp_tools_to_langchain({}, tool_executor)
        
        assert tools == []
    
    @pytest.mark.asyncio
    async def test_convert_with_failed_tool(self):
        """Test conversion when one tool fails."""
        mock_tool1 = Mock(spec=MCPTool)
        mock_tool1.name = "valid_tool"
        mock_tool1.description = "Valid tool"
        mock_tool1.inputSchema = {"type": "object", "properties": {}}
        
        mock_tool2 = Mock(spec=MCPTool)
        mock_tool2.name = "invalid_tool"
        mock_tool2.description = "Invalid tool"
        mock_tool2.inputSchema = None  # Will cause error
        
        tools_dict = {
            "catalog": [mock_tool1, mock_tool2]
        }
        
        async def tool_executor(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            return {"isError": False, "result": "Success"}
        
        # Should handle error gracefully and continue
        tools = convert_mcp_tools_to_langchain(tools_dict, tool_executor)
        
        # At least one tool should be converted
        assert len(tools) >= 1
