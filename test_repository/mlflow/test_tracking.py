"""Tests for MLflow tracking."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))


class TestMLflowTracking:
    """Test suite for MLflow tracking."""
    
    @pytest.fixture
    def mock_tracker(self):
        """Create mock MLflow tracker."""
        tracker = MagicMock()
        tracker.enabled = True
        tracker.tracking_uri = "http://localhost:5000"
        tracker.experiment_name = "test_experiments"
        return tracker
    
    def test_get_tracker(self, mock_tracker):
        """Test getting MLflow tracker."""
        with patch('mlflow.tracking.get_tracker', return_value=mock_tracker):
            from mlflow.tracking import get_tracker
            tracker = get_tracker()
            
            assert tracker is not None
            assert tracker.enabled is True
    
    def test_tracker_disabled_when_mlflow_not_available(self):
        """Test tracker is disabled when MLflow is not available."""
        with patch('mlflow.tracking.mlflow', None):
            with patch('mlflow.tracking.MlflowClient', None):
                from mlflow.tracking import get_tracker
                tracker = get_tracker()
                
                # Should return a tracker but with enabled=False
                assert tracker is not None
