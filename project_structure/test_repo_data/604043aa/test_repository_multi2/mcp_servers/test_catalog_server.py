"""Tests for catalog server."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))


class TestCatalogServer:
    """Test suite for catalog server."""
    
    @pytest.fixture
    def mock_catalog_manager(self):
        """Create mock catalog manager."""
        manager = MagicMock()
        manager.list_tables = AsyncMock(return_value=["table1", "table2"])
        manager.describe_table = AsyncMock(return_value={
            "columns": [{"name": "id", "type": "INTEGER"}]
        })
        manager.get_table_row_count = AsyncMock(return_value=100)
        return manager
    
    @pytest.mark.asyncio
    async def test_list_tables_tool(self, mock_catalog_manager):
        """Test list_tables tool."""
        with patch('mcp_servers.catalog_server.tools.CatalogManager', return_value=mock_catalog_manager):
            from mcp_servers.catalog_server.tools import list_tables
            
            result = await list_tables()
            
            assert "tables" in result or "status" in result
            mock_catalog_manager.list_tables.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_describe_table_tool(self, mock_catalog_manager):
        """Test describe_table tool."""
        with patch('mcp_servers.catalog_server.tools.CatalogManager', return_value=mock_catalog_manager):
            from mcp_servers.catalog_server.tools import describe_table
            
            result = await describe_table(table_name="table1")
            
            assert "columns" in result or "status" in result
            mock_catalog_manager.describe_table.assert_called_once_with("table1")
    
    @pytest.mark.asyncio
    async def test_get_table_row_count_tool(self, mock_catalog_manager):
        """Test get_table_row_count tool."""
        with patch('mcp_servers.catalog_server.tools.CatalogManager', return_value=mock_catalog_manager):
            from mcp_servers.catalog_server.tools import get_table_row_count
            
            result = await get_table_row_count(table_name="table1")
            
            assert "row_count" in result or "status" in result
            mock_catalog_manager.get_table_row_count.assert_called_once_with("table1")
