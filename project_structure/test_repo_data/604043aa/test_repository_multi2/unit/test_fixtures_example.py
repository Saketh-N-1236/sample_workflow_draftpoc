"""Example test showing how to use fixture files."""

import pytest
from fixtures.load_fixtures import (
    get_sample_state,
    get_tool_response,
    get_chat_request,
    get_chat_response,
    get_sample_tool,
    get_error_scenario,
    get_vector_search_result
)


class TestFixtureUsage:
    """Example tests demonstrating fixture usage."""
    
    def test_using_sample_state(self):
        """Example: Using sample states."""
        # Get a specific state
        state = get_sample_state('initial_user_message')
        
        assert state is not None
        assert 'messages' in state
        assert len(state['messages']) > 0
        assert state['messages'][0]['role'] == 'user'
    
    def test_using_tool_response(self):
        """Example: Using tool responses."""
        # Get a tool response
        response = get_tool_response('catalog_list_tables')
        
        assert response is not None
        assert response['isError'] is False
        assert 'result' in response
        assert 'tables' in response['result']
    
    def test_using_chat_request(self):
        """Example: Using chat requests."""
        # Get a chat request
        request = get_chat_request('simple_query')
        
        assert request is not None
        assert 'message' in request
        assert 'session_id' in request
        assert len(request['message']) > 0
    
    def test_using_chat_response(self):
        """Example: Using chat responses."""
        # Get a chat response
        response = get_chat_response('table_list_response')
        
        assert response is not None
        assert 'response' in response
        assert 'tool_calls' in response
        assert 'tool_results' in response
    
    def test_using_sample_tool(self):
        """Example: Using tool definitions."""
        # Get a tool definition
        tool = get_sample_tool('catalog', 'list_tables')
        
        assert tool is not None
        assert tool['name'] == 'list_tables'
        assert 'description' in tool
        assert 'inputSchema' in tool
    
    def test_using_error_scenario(self):
        """Example: Using error scenarios."""
        # Get an error scenario
        error = get_error_scenario('connection_errors', 'mcp_server_unavailable')
        
        assert error is not None
        assert 'error_type' in error
        assert 'message' in error
        assert error['error_type'] == 'ConnectionError'
    
    def test_using_vector_search_result(self):
        """Example: Using vector search results."""
        # Get a search result
        result = get_vector_search_result('electronics_search')
        
        assert result is not None
        assert 'query' in result
        assert 'results' in result
        assert 'count' in result
        assert len(result['results']) > 0
    
    def test_multiple_fixtures(self):
        """Example: Using multiple fixtures together."""
        # Get a request
        request = get_chat_request('table_list_query')
        
        # Get expected response
        response = get_chat_response('table_list_response')
        
        # Get tool response that would be used
        tool_response = get_tool_response('catalog_list_tables')
        
        # Verify consistency
        assert request['session_id'] is not None
        assert response['session_id'] is not None
        assert tool_response['isError'] is False
        
        # The response should reference the tool
        assert len(response['tool_calls']) > 0
        assert response['tool_calls'][0]['name'] == 'catalog_list_tables'
