# Test Repository

Comprehensive test suite for the Multi-Tool Orchestration system.

## Structure

```
test_repository/
├── agent/              # Agent module tests
│   ├── test_langgraph_agent.py
│   ├── test_tool_converter.py
│   ├── test_state_converter.py
│   └── test_langgraph_builder.py
├── api/                # API module tests
│   ├── test_routes.py
│   └── test_main.py
├── llm/                # LLM module tests
│   ├── test_factory.py
│   └── test_clients.py
├── mcp_servers/         # MCP server tests
│   ├── test_catalog_server.py
│   ├── test_sql_query_server.py
│   └── test_vector_search_server.py
├── config/              # Configuration tests
│   └── test_settings.py
├── analytics/           # Analytics tests
│   └── test_aggregator.py
├── mlflow/              # MLflow tests
│   ├── test_tracking.py
│   └── test_evaluation.py
├── inference_logging/   # Inference logging tests
│   └── test_logger.py
├── integration/         # Integration tests
│   ├── test_end_to_end.py
│   └── test_agent_workflow.py
├── fixtures/            # Test fixtures
│   └── sample_data.py
├── conftest.py          # Pytest configuration
└── README.md            # This file
```

## Running Tests

### Run all tests
```bash
pytest test_repository/
```

### Run specific test module
```bash
pytest test_repository/agent/test_langgraph_agent.py
```

### Run with coverage
```bash
pytest test_repository/ --cov=backend --cov-report=html
```

### Run with verbose output
```bash
pytest test_repository/ -v
```

## Test Categories

### Unit Tests
- **Agent Tests**: Test individual agent components (langgraph_agent, builder, nodes, converters)
- **LLM Tests**: Test LLM factory and client implementations
- **API Tests**: Test API routes and endpoints
- **MCP Server Tests**: Test MCP server implementations
- **Config Tests**: Test configuration loading and validation

### Integration Tests
- **End-to-End Tests**: Test complete workflows from API to agent execution
- **Agent Workflow Tests**: Test agent execution with real MCP servers

## Test Fixtures

Common fixtures are defined in `conftest.py`:
- `mock_settings`: Mock settings object
- `mock_mcp_client`: Mock MCP SDK client
- `mock_llm_response`: Mock LLM response
- `sample_messages`: Sample message data
- `temp_dir`: Temporary directory for test data

## Requirements

Tests require the following packages:
- pytest
- pytest-asyncio
- pytest-cov
- unittest.mock (built-in)

## Notes

- Tests use mocks extensively to avoid dependencies on external services
- Integration tests may require running MCP servers
- Some tests may need environment variables set (see `conftest.py`)
