"""Tests for inference logger."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))


class TestInferenceLogger:
    """Test suite for inference logger."""
    
    @pytest.fixture
    def logger(self):
        """Create inference logger instance."""
        from inference_logging.logger import InferenceLogger
        return InferenceLogger(db_path=":memory:")  # Use in-memory database for tests
    
    @pytest.mark.asyncio
    async def test_log_request(self, logger):
        """Test logging a request."""
        await logger.log_request(
            request_id="test_123",
            method="POST",
            path="/api/v1/chat",
            status_code=200,
            duration=1.5
        )
        
        # Verify log was created
        log = await logger.get_log("test_123")
        assert log is not None
        assert log["request_id"] == "test_123"
        assert log["status_code"] == 200
    
    @pytest.mark.asyncio
    async def test_get_logs(self, logger):
        """Test getting logs."""
        # Create some test logs
        for i in range(5):
            await logger.log_request(
                request_id=f"test_{i}",
                method="POST",
                path="/api/v1/chat",
                status_code=200,
                duration=1.0 + i
            )
        
        logs = await logger.get_logs(limit=10, offset=0)
        
        assert len(logs) == 5
        assert all(log["request_id"].startswith("test_") for log in logs)
    
    @pytest.mark.asyncio
    async def test_get_log_not_found(self, logger):
        """Test getting non-existent log."""
        log = await logger.get_log("nonexistent")
        assert log is None
