"""Pytest configuration and shared fixtures for test suite."""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import tempfile
import shutil

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Test configuration
TEST_DB_PATH = "test_data/test.db"
TEST_VECTOR_STORE_PATH = "test_data/vector_store"
TEST_CHROMADB_PATH = "test_data/chromadb"
TEST_CHECKPOINT_DB_PATH = "test_data/checkpoints.db"
TEST_INFERENCE_LOG_DB_PATH = "test_data/inference_logs.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, tmp_path):
    """Set up test environment variables and paths."""
    # Set test database paths
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()
    
    monkeypatch.setenv("DATABASE_PATH", str(test_data_dir / "test.db"))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(test_data_dir / "vector_store"))
    monkeypatch.setenv("CHROMADB_DATA_PATH", str(test_data_dir / "chromadb"))
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(test_data_dir / "checkpoints.db"))
    monkeypatch.setenv("INFERENCE_LOG_DB_PATH", str(test_data_dir / "inference_logs.db"))
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # Clean up after tests
    yield
    if test_data_dir.exists():
        shutil.rmtree(test_data_dir, ignore_errors=True)


@pytest.fixture
def mock_settings():
    """Create a mock settings object."""
    from unittest.mock import MagicMock
    
    settings = MagicMock()
    settings.llm_provider = "gemini"
    settings.embedding_provider = "ollama"
    settings.gemini_api_key = "test_gemini_key"
    settings.gemini_model = "gemini-2.5-flash"
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_chat_model = "llama3"
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.ollama_timeout = 300
    settings.llm_temperature = 0.7
    settings.llm_max_tokens = 500
    settings.database_path = TEST_DB_PATH
    settings.vector_store_path = TEST_VECTOR_STORE_PATH
    settings.chromadb_data_path = TEST_CHROMADB_PATH
    settings.checkpoint_db_path = TEST_CHECKPOINT_DB_PATH
    settings.inference_log_db_path = TEST_INFERENCE_LOG_DB_PATH
    settings.catalog_mcp_port = 7001
    settings.vector_mcp_port = 7002
    settings.sql_mcp_port = 7003
    settings.max_parallel_mcp_calls = 5
    settings.mcp_call_timeout = 60
    settings.mcp_connect_timeout = 10
    settings.api_port = 8000
    settings.api_host = "0.0.0.0"
    settings.enable_mlflow_tracking = False
    settings.enable_graph_visualization = False
    settings.mlflow_tracking_uri = "http://localhost:5000"
    settings.mlflow_experiment_name = "test_experiments"
    
    return settings


@pytest.fixture
def mock_mcp_tool():
    """Create a mock MCP tool."""
    from unittest.mock import MagicMock
    
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "Test tool description"
    tool.inputSchema = {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Test parameter"
            }
        },
        "required": ["param1"]
    }
    return tool


@pytest.fixture
def mock_langchain_tool():
    """Create a mock LangChain StructuredTool."""
    from unittest.mock import MagicMock
    
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "Test tool description"
    tool.args_schema = MagicMock()
    return tool


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        {
            "role": "user",
            "content": "Hello, how are you?"
        },
        {
            "role": "assistant",
            "content": "I'm doing well, thank you!"
        }
    ]


@pytest.fixture
def sample_langchain_messages():
    """Sample LangChain messages for testing."""
    from langchain_core.messages import HumanMessage, AIMessage
    
    return [
        HumanMessage(content="Hello, how are you?"),
        AIMessage(content="I'm doing well, thank you!")
    ]


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    from unittest.mock import MagicMock
    
    response = MagicMock()
    response.content = "Test response"
    response.tool_calls = []
    return response


@pytest.fixture
def mock_agent_state():
    """Create a mock agent state."""
    return {
        "messages": [
            {"role": "user", "content": "Test message"}
        ],
        "tool_calls": [],
        "tool_results": [],
        "request_id": "test_request_123",
        "session_id": "test_session_123",
        "current_step": 0,
        "error": None,
        "finished": False,
        "prompt_version": "v1",
        "model_name": "gemini-2.5-flash"
    }


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP SDK client."""
    from unittest.mock import AsyncMock, MagicMock
    
    client = MagicMock()
    client.initialize = AsyncMock(return_value=None)
    client.discover_all_tools = AsyncMock(return_value={
        "catalog": [],
        "sql_query": [],
        "vector_search": []
    })
    client.call_tool = AsyncMock(return_value={
        "result": '{"status": "success", "data": {}}',
        "isError": False
    })
    client.close = AsyncMock(return_value=None)
    client.list_tools = AsyncMock(return_value=[])
    
    return client


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def cleanup_test_data():
    """Cleanup test data after tests."""
    yield
    # Cleanup will be handled by setup_test_environment fixture
