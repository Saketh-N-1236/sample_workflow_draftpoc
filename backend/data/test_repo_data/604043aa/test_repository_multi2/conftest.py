"""Pytest configuration and shared fixtures for test suite."""

import pytest
import asyncio
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import json

# Test imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from config.settings import Settings
from agent.langgraph_state import LangGraphAgentState
from agent.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import StructuredTool
from mcp.types import Tool as MCPTool


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_db_path(temp_dir):
    """Create a temporary SQLite database path."""
    return temp_dir / "test.db"


@pytest.fixture
def temp_checkpoint_db(temp_dir):
    """Create a temporary checkpoint database path."""
    return temp_dir / "checkpoints.db"


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=Settings)
    settings.llm_provider = "gemini"
    settings.embedding_provider = "ollama"
    settings.gemini_api_key = "test-gemini-key"
    settings.gemini_model = "gemini-2.5-pro"
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_chat_model = "llama3"
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.ollama_timeout = 300
    settings.llm_temperature = 0.7
    settings.llm_max_tokens = 2048
    settings.catalog_mcp_port = 8001
    settings.sql_mcp_port = 8002
    settings.vector_mcp_port = 8003
    settings.max_parallel_mcp_calls = 5
    settings.mcp_call_timeout = 30
    settings.mcp_connect_timeout = 10
    settings.checkpoint_db_path = "data/checkpoints.db"
    settings.enable_mlflow = False
    settings.enable_inference_logging = False
    return settings


@pytest.fixture
def mock_mcp_tool():
    """Create a mock MCP tool."""
    tool = Mock(spec=MCPTool)
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.inputSchema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The query string"
            },
            "limit": {
                "type": "integer",
                "description": "Result limit",
                "default": 10
            }
        },
        "required": ["query"]
    }
    return tool


@pytest.fixture
def mock_mcp_tools_dict(mock_mcp_tool):
    """Create a dictionary of mock MCP tools by server."""
    return {
        "catalog": [mock_mcp_tool],
        "sql_query": [mock_mcp_tool],
        "vector_search": [mock_mcp_tool]
    }


@pytest.fixture
def mock_langchain_tool():
    """Create a mock LangChain StructuredTool."""
    async def tool_func(query: str, limit: int = 10) -> str:
        return json.dumps({"result": f"Query: {query}, Limit: {limit}"})
    
    tool = StructuredTool(
        name="catalog_test_tool",
        description="A test tool",
        args_schema=type("Args", (), {
            "query": str,
            "limit": int
        }),
        func=tool_func,
        coroutine=tool_func
    )
    return tool


@pytest.fixture
def mock_langchain_tools(mock_langchain_tool):
    """Create a list of mock LangChain tools."""
    return [mock_langchain_tool]


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP SDK client."""
    client = AsyncMock()
    client.server_configs = {
        "catalog": "http://localhost:8001/sse",
        "sql_query": "http://localhost:8002/sse",
        "vector_search": "http://localhost:8003/sse"
    }
    client._initialized = True
    
    # Mock discover_all_tools
    async def discover_all_tools():
        return {
            "catalog": [Mock(name="list_tables", description="List tables")],
            "sql_query": [Mock(name="execute_query", description="Execute SQL")],
            "vector_search": [Mock(name="search_documents", description="Search vectors")]
        }
    
    client.discover_all_tools = AsyncMock(side_effect=discover_all_tools)
    
    # Mock call_tool
    async def call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "isError": False,
            "result": {"data": f"Result from {server_name}.{tool_name}"}
        }
    
    client.call_tool = AsyncMock(side_effect=call_tool)
    
    return client


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    llm = AsyncMock()
    
    # Mock invoke to return AIMessage
    def invoke_side_effect(messages, **kwargs):
        # Check if tools are bound
        if hasattr(llm, 'bound_tools') and llm.bound_tools:
            # Return AIMessage with tool calls
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "catalog_test_tool",
                    "args": {"query": "test"},
                    "id": "call_123"
                }]
            )
        else:
            # Return regular AIMessage
            return AIMessage(content="This is a test response")
    
    llm.invoke = Mock(side_effect=invoke_side_effect)
    llm.ainvoke = AsyncMock(side_effect=lambda messages, **kwargs: invoke_side_effect(messages, **kwargs))
    llm.bind_tools = Mock(return_value=llm)
    llm.bound_tools = []
    
    return llm


@pytest.fixture
def sample_langgraph_state():
    """Create a sample LangGraph state."""
    return {
        "messages": [
            HumanMessage(content="What tables are available?")
        ],
        "request_id": "test-request-123",
        "session_id": "test-session-456"
    }


@pytest.fixture
def sample_agent_state():
    """Create a sample AgentState."""
    return {
        "messages": [
            {"role": "user", "content": "What tables are available?"}
        ],
        "request_id": "test-request-123",
        "session_id": "test-session-456",
        "tool_calls": [],
        "tool_results": []
    }


@pytest.fixture
def mock_graph():
    """Create a mock LangGraph StateGraph."""
    graph = AsyncMock()
    
    async def ainvoke_side_effect(state, config=None):
        # Simulate graph execution
        messages = state.get("messages", [])
        messages.append(AIMessage(content="Test response"))
        return {
            "messages": messages,
            "request_id": state.get("request_id"),
            "session_id": state.get("session_id")
        }
    
    graph.ainvoke = AsyncMock(side_effect=ainvoke_side_effect)
    return graph


@pytest.fixture
def mock_checkpointer():
    """Create a mock checkpointer."""
    checkpointer = Mock()
    return checkpointer


@pytest.fixture
def sample_chat_request():
    """Create a sample chat request."""
    return {
        "message": "What tables are available?",
        "session_id": "test-session-123"
    }


@pytest.fixture
def sample_chat_response():
    """Create a sample chat response."""
    return {
        "response": "Here are the available tables: users, products, orders",
        "request_id": "test-request-123",
        "session_id": "test-session-123",
        "tool_calls": [
            {
                "name": "catalog_list_tables",
                "arguments": {},
                "step": 1
            }
        ],
        "tool_results": [
            {
                "tool_name": "catalog_list_tables",
                "result": {"tables": ["users", "products", "orders"]},
                "step": 1
            }
        ],
        "iterations": 2
    }


@pytest.fixture
def mock_fastapi_app():
    """Create a mock FastAPI app."""
    app = Mock()
    app.router = Mock()
    return app


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client for MCP server calls."""
    client = AsyncMock()
    
    async def get_side_effect(url, **kwargs):
        response = Mock()
        response.status_code = 200
        response.json = Mock(return_value={"tools": []})
        response.text = Mock(return_value="")
        return response
    
    client.get = AsyncMock(side_effect=get_side_effect)
    client.post = AsyncMock(side_effect=get_side_effect)
    return client


@pytest.fixture
def mock_sse_client():
    """Create a mock SSE client."""
    async def sse_client_context(url):
        read = AsyncMock()
        write = AsyncMock()
        yield (read, write)
    
    return sse_client_context


@pytest.fixture
def mock_client_session():
    """Create a mock MCP ClientSession."""
    session = AsyncMock()
    
    async def initialize():
        pass
    
    async def list_tools():
        response = Mock()
        response.tools = []
        return response
    
    async def call_tool(name, arguments):
        return {"result": f"Tool {name} executed"}
    
    session.initialize = AsyncMock(side_effect=initialize)
    session.list_tools = AsyncMock(side_effect=list_tools)
    session.call_tool = AsyncMock(side_effect=call_tool)
    
    return session


@pytest.fixture
def error_scenarios():
    """Provide various error scenarios for testing."""
    return {
        "connection_error": ConnectionError("Cannot connect to MCP server"),
        "timeout_error": TimeoutError("Request timed out"),
        "validation_error": ValueError("Invalid input"),
        "tool_error": RuntimeError("Tool execution failed"),
        "llm_error": Exception("LLM API error"),
        "empty_response": None,
        "invalid_json": "{invalid json}",
        "missing_required_field": {"incomplete": "data"}
    }


@pytest.fixture
def edge_case_inputs():
    """Provide edge case inputs for testing."""
    return {
        "empty_string": "",
        "very_long_string": "x" * 10000,
        "special_characters": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
        "unicode": "测试 🚀 émojis",
        "sql_injection": "'; DROP TABLE users; --",
        "xss_attempt": "<script>alert('xss')</script>",
        "null_value": None,
        "empty_dict": {},
        "empty_list": [],
        "nested_dict": {"a": {"b": {"c": "deep"}}},
        "large_number": 999999999999999999,
        "negative_number": -1,
        "zero": 0
    }
