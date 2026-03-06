"""Tests for analytics aggregator."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))


class TestAnalyticsAggregator:
    """Test suite for AnalyticsAggregator."""
    
    @pytest.fixture
    def aggregator(self):
        """Create AnalyticsAggregator instance."""
        from analytics.aggregator import AnalyticsAggregator
        return AnalyticsAggregator()
    
    @pytest.mark.asyncio
    async def test_get_overview_stats(self, aggregator):
        """Test getting overview statistics."""
        with patch('analytics.aggregator.get_inference_logger') as mock_logger:
            mock_logger_instance = MagicMock()
            mock_logger_instance.get_logs = AsyncMock(return_value=[
                {
                    "status_code": 200,
                    "duration": 1.5,
                    "path": "/api/v1/chat",
                    "method": "POST",
                    "tool_calls": [{"tool_name": "test_tool"}],
                    "iterations": 2
                }
            ])
            mock_logger.return_value = mock_logger_instance
            
            stats = await aggregator.get_overview_stats()
            
            assert "total_requests" in stats
            assert "successful_requests" in stats
            assert "avg_duration" in stats
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_stats(self, aggregator):
        """Test getting tool usage statistics."""
        with patch('analytics.aggregator.get_inference_logger') as mock_logger:
            mock_logger_instance = MagicMock()
            mock_logger_instance.get_logs = AsyncMock(return_value=[
                {
                    "tool_calls": [{"tool_name": "test_tool"}]
                }
            ])
            mock_logger.return_value = mock_logger_instance
            
            stats = await aggregator.get_tool_usage_stats()
            
            assert "tools" in stats
            assert "total_tool_calls" in stats
