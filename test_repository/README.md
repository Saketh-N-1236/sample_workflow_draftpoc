# Test Repository

Comprehensive test suite for the Multi-Tool Orchestration project, covering unit tests, integration tests, end-to-end tests, and edge cases.

## Structure

```
test_repository/
├── conftest.py              # Shared pytest fixtures and configuration
├── unit/                    # Unit tests for individual components
│   ├── test_agent_pool.py
│   ├── test_api_routes.py
│   ├── test_langgraph_nodes.py
│   ├── test_llm_factory.py
│   ├── test_mcp_client.py
│   ├── test_state_converter.py
│   ├── test_tool_converter.py
│   └── test_edge_cases.py
├── integration/            # Integration tests for component interactions
│   ├── test_agent_flow.py
│   └── test_api_integration.py
├── e2e/                    # End-to-end tests for complete workflows
│   └── test_complete_chat_flow.py
└── fixtures/               # Test fixtures and mock data
```

## Test Coverage

### Unit Tests

- **Agent Pool** (`test_agent_pool.py`): Tests singleton management, initialization, TTL, concurrency
- **API Routes** (`test_api_routes.py`): Tests route handlers, validation, formatting
- **LangGraph Nodes** (`test_langgraph_nodes.py`): Tests `call_model`, `should_continue`, tool management
- **LLM Factory** (`test_llm_factory.py`): Tests provider creation, error handling
- **MCP Client** (`test_mcp_client.py`): Tests tool discovery, execution, error recovery
- **State Converter** (`test_state_converter.py`): Tests state conversion, message normalization
- **Tool Converter** (`test_tool_converter.py`): Tests MCP to LangChain conversion, schema handling
- **Edge Cases** (`test_edge_cases.py`): Tests boundary conditions, error scenarios, concurrency

### Integration Tests

- **Agent Flow** (`test_agent_flow.py`): Tests complete initialization, tool execution, state management
- **API Integration** (`test_api_integration.py`): Tests endpoint interactions, tool discovery

### End-to-End Tests

- **Complete Chat Flow** (`test_complete_chat_flow.py`): Tests full user interaction flows, multi-turn conversations, error scenarios

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov
```

### Run All Tests

```bash
# From project root
pytest test_repository/ -v

# With coverage
pytest test_repository/ --cov=backend --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest test_repository/unit/ -v

# Integration tests only
pytest test_repository/integration/ -v

# End-to-end tests only
pytest test_repository/e2e/ -v
```

### Run Specific Test Files

```bash
# Run specific test file
pytest test_repository/unit/test_agent_pool.py -v

# Run specific test class
pytest test_repository/unit/test_agent_pool.py::TestAgentPool -v

# Run specific test
pytest test_repository/unit/test_agent_pool.py::TestAgentPool::test_get_agent_creates_new_instance -v
```

### Run with Markers

```bash
# Run only async tests
pytest test_repository/ -m asyncio -v

# Run tests matching pattern
pytest test_repository/ -k "test_agent" -v
```

## Test Fixtures

The `conftest.py` file provides shared fixtures:

- `mock_settings`: Mock application settings
- `mock_mcp_tool`: Mock MCP tool
- `mock_langchain_tool`: Mock LangChain tool
- `mock_mcp_client`: Mock MCP SDK client
- `mock_llm`: Mock LLM instance
- `mock_graph`: Mock LangGraph StateGraph
- `sample_langgraph_state`: Sample LangGraph state
- `sample_agent_state`: Sample AgentState
- `error_scenarios`: Various error scenarios
- `edge_case_inputs`: Edge case input data
- `temp_dir`: Temporary directory for test files
- `temp_db_path`: Temporary database path

## Writing New Tests

### Unit Test Example

```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestMyComponent:
    """Test my component."""
    
    @pytest.mark.asyncio
    async def test_my_function(self, mock_fixture):
        """Test my function."""
        # Arrange
        mock_fixture.method = AsyncMock(return_value="result")
        
        # Act
        result = await my_function(mock_fixture)
        
        # Assert
        assert result == "result"
        mock_fixture.method.assert_called_once()
```

### Integration Test Example

```python
import pytest
from unittest.mock import patch

class TestMyIntegration:
    """Test component integration."""
    
    @pytest.mark.asyncio
    async def test_component_flow(self, mock_component1, mock_component2):
        """Test flow between components."""
        with patch('module.component1', return_value=mock_component1):
            result = await integrated_function()
            assert result is not None
```

## Edge Cases Covered

### Input Validation
- Empty strings
- Very long strings (10,000+ characters)
- Special characters
- Unicode characters
- SQL injection attempts
- XSS attempts
- Null values
- Empty dictionaries/lists
- Deeply nested structures
- Large numbers
- Negative numbers
- Zero values

### Error Scenarios
- Connection errors
- Timeout errors
- Validation errors
- Tool execution errors
- LLM API errors
- Empty responses
- Invalid JSON
- Missing required fields

### Boundary Conditions
- Minimum/maximum collection name lengths
- Zero/negative limits
- Maximum integer values
- Empty states
- States with missing fields
- States with extra fields
- Very large states

### Concurrency
- Concurrent agent requests
- Rapid sequential requests
- Parallel tool calls
- Semaphore limits

## Test Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Mocking**: Use mocks for external dependencies (MCP servers, LLM APIs)
3. **Fixtures**: Reuse fixtures from `conftest.py` for common setup
4. **Async**: Use `@pytest.mark.asyncio` for async tests
5. **Assertions**: Use descriptive assertions with clear error messages
6. **Coverage**: Aim for high code coverage, especially for critical paths
7. **Edge Cases**: Always test boundary conditions and error scenarios

## Continuous Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pytest test_repository/ -v --cov=backend --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Troubleshooting

### Import Errors

If you encounter import errors, ensure the backend directory is in the Python path:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
```

Or add to `conftest.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
```

### Async Test Issues

Ensure `pytest-asyncio` is installed and configured:

```bash
pip install pytest-asyncio
```

### Mock Issues

If mocks aren't working as expected, check:
1. Mock is patched in the correct namespace
2. Async mocks use `AsyncMock` instead of `Mock`
3. Patches are applied before imports if needed

## Coverage Goals

- **Unit Tests**: 80%+ coverage for core components
- **Integration Tests**: Cover all major component interactions
- **E2E Tests**: Cover all user-facing workflows
- **Edge Cases**: Cover all identified edge cases and error scenarios

## Contributing

When adding new features:
1. Write unit tests for new components
2. Add integration tests for component interactions
3. Add E2E tests for new user workflows
4. Test edge cases and error scenarios
5. Ensure all tests pass before submitting

## Notes

- Tests use mocks extensively to avoid requiring actual MCP servers or LLM APIs
- Some integration tests may require actual services (marked with appropriate markers)
- E2E tests simulate complete flows but may use mocks for external services
- All tests are designed to run in isolation and clean up after themselves
