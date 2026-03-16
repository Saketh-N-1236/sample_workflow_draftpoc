# Test Fixtures

This directory contains reusable test data fixtures in JSON format and utility functions to load them.

## Files

### `sample_states.json`
Sample agent states for testing:
- `empty_state`: Empty state
- `initial_user_message`: State with initial user message
- `with_tool_call`: State with tool call
- `with_tool_result`: State with tool result
- `multi_turn_conversation`: Multi-turn conversation state
- `with_multiple_tool_calls`: State with multiple tool calls

### `sample_tools.json`
Tool definitions and responses:
- `mcp_tools`: Tool definitions by server (catalog, sql_query, vector_search)
- `tool_responses`: Sample successful tool responses
- `tool_errors`: Sample error responses

### `sample_requests.json`
Chat requests and responses:
- `chat_requests`: Various chat request examples
- `chat_responses`: Corresponding response examples

### `sample_database_schemas.json`
Database schema and query examples:
- `sample_database`: Database schema with tables and columns
- `sample_queries`: Sample SQL queries
- `sample_query_results`: Expected query results

### `sample_vector_data.json`
Vector search data:
- `collections`: Vector collection definitions
- `sample_documents`: Sample documents with metadata
- `sample_search_results`: Sample search results
- `embedding_config`: Embedding configuration

### `error_scenarios.json`
Error scenarios for testing:
- `connection_errors`: Connection-related errors
- `validation_errors`: Input validation errors
- `execution_errors`: Tool/query execution errors
- `llm_errors`: LLM API errors
- `state_errors`: State management errors
- `tool_conversion_errors`: Tool conversion errors

### `load_fixtures.py`
Utility functions to load fixture data:
- `load_json_fixture()`: Load any JSON fixture file
- `get_sample_state()`: Get a specific state
- `get_sample_tool()`: Get a tool definition
- `get_tool_response()`: Get a tool response
- `get_chat_request()`: Get a chat request
- `get_chat_response()`: Get a chat response
- And more...

## Usage

### In Tests

```python
from fixtures.load_fixtures import (
    get_sample_state,
    get_tool_response,
    get_chat_request
)

def test_my_function():
    # Load a sample state
    state = get_sample_state('initial_user_message')
    
    # Load a tool response
    response = get_tool_response('catalog_list_tables')
    
    # Load a chat request
    request = get_chat_request('simple_query')
```

### Direct JSON Loading

```python
from fixtures.load_fixtures import load_json_fixture

# Load any fixture file
fixtures = load_json_fixture('sample_states')
state = fixtures['empty_state']
```

### Using in conftest.py

```python
import pytest
from fixtures.load_fixtures import get_sample_state

@pytest.fixture
def sample_state():
    return get_sample_state('initial_user_message')
```

## Adding New Fixtures

1. Create a new JSON file in this directory
2. Add utility functions to `load_fixtures.py` if needed
3. Document the fixture structure in this README

## Best Practices

- Keep fixture data realistic but minimal
- Use consistent naming conventions
- Include both success and error scenarios
- Document any special requirements or assumptions
- Keep fixtures independent (no cross-references unless necessary)
