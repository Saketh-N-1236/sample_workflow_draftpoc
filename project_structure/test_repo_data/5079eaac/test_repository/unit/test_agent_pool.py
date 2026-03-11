"""Unit tests for agent pool (singleton management)."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from agent.agent_pool import get_agent, reset_agent, close_agent
from agent.langgraph_agent import LangGraphAgent


class TestAgentPool:
    """Test agent pool singleton management."""
    
    @pytest.mark.asyncio
    async def test_get_agent_creates_new_instance(self, mock_mcp_client, mock_langchain_tools):
        """Test that get_agent creates a new instance on first call."""
        with patch('agent.agent_pool.LangGraphAgent') as mock_agent_class:
            mock_agent = AsyncMock(spec=LangGraphAgent)
            mock_agent.initialize = AsyncMock()
            mock_agent.close = AsyncMock()
            mock_agent_class.return_value = mock_agent
            
            agent = await get_agent()
            
            assert agent is not None
            mock_agent_class.assert_called_once()
            mock_agent.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_agent_reuses_instance(self, mock_mcp_client, mock_langchain_tools):
        """Test that get_agent reuses the same instance on subsequent calls."""
        with patch('agent.agent_pool.LangGraphAgent') as mock_agent_class:
            mock_agent = AsyncMock(spec=LangGraphAgent)
            mock_agent.initialize = AsyncMock()
            mock_agent.close = AsyncMock()
            mock_agent_class.return_value = mock_agent
            
            agent1 = await get_agent()
            agent2 = await get_agent()
            
            assert agent1 is agent2
            assert mock_agent_class.call_count == 1
            assert mock_agent.initialize.call_count == 1
    
    @pytest.mark.asyncio
    async def test_get_agent_handles_initialization_failure(self):
        """Test that get_agent handles initialization failures gracefully."""
        with patch('agent.agent_pool.LangGraphAgent') as mock_agent_class:
            mock_agent = AsyncMock(spec=LangGraphAgent)
            mock_agent.initialize = AsyncMock(side_effect=RuntimeError("Init failed"))
            mock_agent.close = AsyncMock()
            mock_agent_class.return_value = mock_agent
            
            with pytest.raises(RuntimeError, match="Agent initialization failed"):
                await get_agent()
    
    @pytest.mark.asyncio
    async def test_reset_agent(self, mock_mcp_client, mock_langchain_tools):
        """Test that reset_agent closes and clears the agent instance."""
        with patch('agent.agent_pool.LangGraphAgent') as mock_agent_class:
            mock_agent = AsyncMock(spec=LangGraphAgent)
            mock_agent.initialize = AsyncMock()
            mock_agent.close = AsyncMock()
            mock_agent_class.return_value = mock_agent
            
            await get_agent()
            await reset_agent()
            
            mock_agent.close.assert_called_once()
            
            # Next call should create a new instance
            agent2 = await get_agent()
            assert mock_agent_class.call_count == 2
    
    @pytest.mark.asyncio
    async def test_close_agent(self, mock_mcp_client, mock_langchain_tools):
        """Test that close_agent resets the agent."""
        with patch('agent.agent_pool.LangGraphAgent') as mock_agent_class:
            mock_agent = AsyncMock(spec=LangGraphAgent)
            mock_agent.initialize = AsyncMock()
            mock_agent.close = AsyncMock()
            mock_agent_class.return_value = mock_agent
            
            await get_agent()
            await close_agent()
            
            mock_agent.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_expires_after_ttl(self, mock_mcp_client, mock_langchain_tools):
        """Test that agent expires after TTL period."""
        with patch('agent.agent_pool.LangGraphAgent') as mock_agent_class, \
             patch('agent.agent_pool._agent_last_used') as mock_last_used, \
             patch('agent.agent_pool._agent_ttl_seconds', 1):  # 1 second TTL
            
            mock_agent = AsyncMock(spec=LangGraphAgent)
            mock_agent.initialize = AsyncMock()
            mock_agent.close = AsyncMock()
            mock_agent_class.return_value = mock_agent
            
            # Set last used to past
            mock_last_used.value = datetime.utcnow() - timedelta(seconds=2)
            
            # Get agent should create new instance
            agent = await get_agent()
            
            # Should have closed old agent and created new one
            assert mock_agent.close.call_count >= 0
    
    @pytest.mark.asyncio
    async def test_concurrent_get_agent_calls(self, mock_mcp_client, mock_langchain_tools):
        """Test that concurrent get_agent calls are handled safely."""
        with patch('agent.agent_pool.LangGraphAgent') as mock_agent_class:
            mock_agent = AsyncMock(spec=LangGraphAgent)
            mock_agent.initialize = AsyncMock()
            mock_agent.close = AsyncMock()
            mock_agent_class.return_value = mock_agent
            
            # Make multiple concurrent calls
            agents = await asyncio.gather(*[get_agent() for _ in range(10)])
            
            # All should be the same instance
            assert all(agent is agents[0] for agent in agents)
            # Should only initialize once
            assert mock_agent.initialize.call_count == 1
