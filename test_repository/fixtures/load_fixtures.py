"""Utility functions to load fixture data."""

import json
from pathlib import Path
from typing import Dict, Any, Optional

# Fixture directory
FIXTURES_DIR = Path(__file__).parent


def load_json_fixture(filename: str) -> Dict[str, Any]:
    """Load a JSON fixture file.
    
    Args:
        filename: Name of the fixture file (with or without .json extension)
        
    Returns:
        Dictionary containing the fixture data
        
    Raises:
        FileNotFoundError: If the fixture file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    if not filename.endswith('.json'):
        filename += '.json'
    
    filepath = FIXTURES_DIR / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"Fixture file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_sample_state(state_name: str) -> Dict[str, Any]:
    """Get a sample state by name.
    
    Args:
        state_name: Name of the state (e.g., 'empty_state', 'with_tool_call')
        
    Returns:
        State dictionary
        
    Example:
        >>> state = get_sample_state('initial_user_message')
    """
    fixtures = load_json_fixture('sample_states')
    if state_name not in fixtures:
        raise KeyError(f"State '{state_name}' not found in fixtures. Available: {list(fixtures.keys())}")
    return fixtures[state_name]


def get_sample_tool(server_name: str, tool_name: str) -> Dict[str, Any]:
    """Get a sample tool definition.
    
    Args:
        server_name: Name of the server (e.g., 'catalog', 'sql_query')
        tool_name: Name of the tool (e.g., 'list_tables', 'execute_query')
        
    Returns:
        Tool definition dictionary
    """
    fixtures = load_json_fixture('sample_tools')
    tools = fixtures['mcp_tools'].get(server_name, [])
    
    for tool in tools:
        if tool['name'] == tool_name:
            return tool
    
    raise KeyError(f"Tool '{tool_name}' not found in server '{server_name}'")


def get_tool_response(tool_name: str) -> Dict[str, Any]:
    """Get a sample tool response.
    
    Args:
        tool_name: Full tool name (e.g., 'catalog_list_tables')
        
    Returns:
        Tool response dictionary
    """
    fixtures = load_json_fixture('sample_tools')
    responses = fixtures['tool_responses']
    
    if tool_name not in responses:
        raise KeyError(f"Tool response '{tool_name}' not found. Available: {list(responses.keys())}")
    
    return responses[tool_name]


def get_tool_error(error_name: str) -> Dict[str, Any]:
    """Get a sample tool error response.
    
    Args:
        error_name: Name of the error (e.g., 'connection_error', 'timeout_error')
        
    Returns:
        Error response dictionary
    """
    fixtures = load_json_fixture('sample_tools')
    errors = fixtures['tool_errors']
    
    if error_name not in errors:
        raise KeyError(f"Tool error '{error_name}' not found. Available: {list(errors.keys())}")
    
    return errors[error_name]


def get_chat_request(request_name: str) -> Dict[str, Any]:
    """Get a sample chat request.
    
    Args:
        request_name: Name of the request (e.g., 'simple_query', 'table_list_query')
        
    Returns:
        Chat request dictionary
    """
    fixtures = load_json_fixture('sample_requests')
    requests = fixtures['chat_requests']
    
    if request_name not in requests:
        raise KeyError(f"Chat request '{request_name}' not found. Available: {list(requests.keys())}")
    
    return requests[request_name]


def get_chat_response(response_name: str) -> Dict[str, Any]:
    """Get a sample chat response.
    
    Args:
        response_name: Name of the response (e.g., 'simple_response', 'table_list_response')
        
    Returns:
        Chat response dictionary
    """
    fixtures = load_json_fixture('sample_requests')
    responses = fixtures['chat_responses']
    
    if response_name not in responses:
        raise KeyError(f"Chat response '{response_name}' not found. Available: {list(responses.keys())}")
    
    return responses[response_name]


def get_database_schema() -> Dict[str, Any]:
    """Get sample database schema.
    
    Returns:
        Database schema dictionary
    """
    return load_json_fixture('sample_database_schemas')['sample_database']


def get_sample_query(query_name: str) -> str:
    """Get a sample SQL query.
    
    Args:
        query_name: Name of the query (e.g., 'select_all_users')
        
    Returns:
        SQL query string
    """
    fixtures = load_json_fixture('sample_database_schemas')
    queries = fixtures['sample_queries']
    
    if query_name not in queries:
        raise KeyError(f"Query '{query_name}' not found. Available: {list(queries.keys())}")
    
    return queries[query_name]


def get_query_result(query_name: str) -> Dict[str, Any]:
    """Get a sample query result.
    
    Args:
        query_name: Name of the query (e.g., 'select_all_users')
        
    Returns:
        Query result dictionary
    """
    fixtures = load_json_fixture('sample_database_schemas')
    results = fixtures['sample_query_results']
    
    if query_name not in results:
        raise KeyError(f"Query result '{query_name}' not found. Available: {list(results.keys())}")
    
    return results[query_name]


def get_error_scenario(category: str, error_name: str) -> Dict[str, Any]:
    """Get an error scenario.
    
    Args:
        category: Error category (e.g., 'connection_errors', 'validation_errors')
        error_name: Name of the error scenario
        
    Returns:
        Error scenario dictionary
    """
    fixtures = load_json_fixture('error_scenarios')
    
    if category not in fixtures:
        raise KeyError(f"Error category '{category}' not found. Available: {list(fixtures.keys())}")
    
    errors = fixtures[category]
    
    if error_name not in errors:
        raise KeyError(f"Error '{error_name}' not found in category '{category}'. Available: {list(errors.keys())}")
    
    return errors[error_name]


def get_vector_collection(collection_name: str) -> Dict[str, Any]:
    """Get a vector collection definition.
    
    Args:
        collection_name: Name of the collection (e.g., 'products', 'documents')
        
    Returns:
        Collection definition dictionary
    """
    fixtures = load_json_fixture('sample_vector_data')
    collections = fixtures['collections']
    
    if collection_name not in collections:
        raise KeyError(f"Collection '{collection_name}' not found. Available: {list(collections.keys())}")
    
    return collections[collection_name]


def get_vector_search_result(result_name: str) -> Dict[str, Any]:
    """Get a sample vector search result.
    
    Args:
        result_name: Name of the result (e.g., 'electronics_search', 'empty_search')
        
    Returns:
        Search result dictionary
    """
    fixtures = load_json_fixture('sample_vector_data')
    results = fixtures['sample_search_results']
    
    if result_name not in results:
        raise KeyError(f"Search result '{result_name}' not found. Available: {list(results.keys())}")
    
    return results[result_name]


# Convenience functions for common use cases
def get_all_states() -> Dict[str, Any]:
    """Get all sample states."""
    return load_json_fixture('sample_states')


def get_all_tools() -> Dict[str, Any]:
    """Get all tool definitions."""
    return load_json_fixture('sample_tools')['mcp_tools']


def get_all_requests() -> Dict[str, Any]:
    """Get all chat requests."""
    return load_json_fixture('sample_requests')['chat_requests']


def get_all_responses() -> Dict[str, Any]:
    """Get all chat responses."""
    return load_json_fixture('sample_requests')['chat_responses']
