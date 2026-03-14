"""Tests for src/shared/db.py — Async PostgreSQL/PostGIS connection layer.

All tests mock asyncpg so no real database is needed.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.db import (
    DBHealthStatus,
    check_health,
    close_pool,
    create_pool,
    execute,
    fetch_all,
    fetch_one,
    fetch_val,
    find_in_polygon,
    find_within_radius,
    get_pool,
    point_to_wkt,
    polygon_to_wkt,
)


def _make_mock_pool(mock_conn):
    """Create a mock pool whose acquire() returns an async context manager."""
    mock_pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    mock_pool.acquire = _acquire
    mock_pool.close = AsyncMock()
    return mock_pool


# =============================================================================
# WKT Helpers
# =============================================================================


class TestPointToWkt:
    def test_basic_point(self):
        result = point_to_wkt(28.6139, 77.2090)
        assert result == "POINT(77.209 28.6139)"

    def test_negative_coordinates(self):
        result = point_to_wkt(-33.8688, 151.2093)
        assert result == "POINT(151.2093 -33.8688)"

    def test_zero_coordinates(self):
        result = point_to_wkt(0.0, 0.0)
        assert result == "POINT(0.0 0.0)"

    def test_wkt_format_is_lon_lat(self):
        """WKT uses longitude first, latitude second."""
        result = point_to_wkt(lat=20.0, lon=80.0)
        assert result == "POINT(80.0 20.0)"


class TestPolygonToWkt:
    def test_triangle(self):
        coords = [(28.0, 77.0), (28.5, 77.5), (28.0, 77.5)]
        result = polygon_to_wkt(coords)
        assert result == "POLYGON((77.0 28.0,77.5 28.5,77.5 28.0,77.0 28.0))"

    def test_already_closed_polygon(self):
        coords = [(28.0, 77.0), (28.5, 77.5), (28.0, 77.5), (28.0, 77.0)]
        result = polygon_to_wkt(coords)
        assert result == "POLYGON((77.0 28.0,77.5 28.5,77.5 28.0,77.0 28.0))"

    def test_quadrilateral(self):
        coords = [(10.0, 70.0), (10.0, 80.0), (20.0, 80.0), (20.0, 70.0)]
        result = polygon_to_wkt(coords)
        assert "POLYGON(" in result
        parts = result.replace("POLYGON((", "").replace("))", "").split(",")
        assert parts[0] == parts[-1]


# =============================================================================
# Pool Management
# =============================================================================


class TestCreatePool:
    @pytest.mark.asyncio
    @patch("src.shared.db.asyncpg.create_pool", new_callable=AsyncMock)
    @patch("src.shared.db.get_settings")
    async def test_creates_pool_with_correct_dsn(self, mock_settings, mock_create_pool):
        settings = MagicMock()
        settings.POSTGRES_HOST = "localhost"
        settings.POSTGRES_PORT = 5432
        settings.POSTGRES_USER = "crisis"
        settings.POSTGRES_PASSWORD = "crisis_dev"
        settings.POSTGRES_DB = "crisis_bench"
        mock_settings.return_value = settings

        mock_pool = MagicMock()
        mock_create_pool.return_value = mock_pool

        pool = await create_pool()

        mock_create_pool.assert_called_once()
        call_kwargs = mock_create_pool.call_args
        dsn = call_kwargs.kwargs.get("dsn") or call_kwargs.args[0]
        assert "crisis" in dsn
        assert "crisis_bench" in dsn
        assert "localhost" in dsn
        assert pool is mock_pool

    @pytest.mark.asyncio
    @patch("src.shared.db.asyncpg.create_pool", new_callable=AsyncMock)
    @patch("src.shared.db.get_settings")
    async def test_pool_config_params(self, mock_settings, mock_create_pool):
        settings = MagicMock()
        settings.POSTGRES_HOST = "localhost"
        settings.POSTGRES_PORT = 5432
        settings.POSTGRES_USER = "crisis"
        settings.POSTGRES_PASSWORD = "crisis_dev"
        settings.POSTGRES_DB = "crisis_bench"
        mock_settings.return_value = settings
        mock_create_pool.return_value = MagicMock()

        await create_pool()

        call_kwargs = mock_create_pool.call_args.kwargs
        assert call_kwargs["min_size"] == 2
        assert call_kwargs["max_size"] == 10
        assert call_kwargs["command_timeout"] == 60


class TestClosePool:
    @pytest.mark.asyncio
    async def test_closes_existing_pool(self):
        import src.shared.db as db_module

        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()
        db_module._pool = mock_pool

        await close_pool()

        mock_pool.close.assert_called_once()
        assert db_module._pool is None

    @pytest.mark.asyncio
    async def test_close_pool_when_none(self):
        """Closing when no pool exists should not raise."""
        import src.shared.db as db_module

        db_module._pool = None
        await close_pool()  # Should not raise


class TestGetPool:
    @pytest.mark.asyncio
    @patch("src.shared.db.create_pool", new_callable=AsyncMock)
    async def test_creates_pool_if_none(self, mock_create_pool):
        import src.shared.db as db_module

        db_module._pool = None
        mock_pool = MagicMock()
        mock_create_pool.return_value = mock_pool

        result = await get_pool()

        mock_create_pool.assert_called_once()
        assert result is mock_pool

    @pytest.mark.asyncio
    async def test_returns_existing_pool(self):
        import src.shared.db as db_module

        mock_pool = MagicMock()
        db_module._pool = mock_pool

        result = await get_pool()

        assert result is mock_pool


# =============================================================================
# Health Check
# =============================================================================


class TestCheckHealth:
    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_healthy_db(self, mock_get_pool):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[1, "3.4 USE_GEOS=1"])
        mock_pool = _make_mock_pool(mock_conn)
        mock_get_pool.return_value = mock_pool

        status = await check_health()

        assert isinstance(status, DBHealthStatus)
        assert status.connected is True
        assert status.postgis_version == "3.4 USE_GEOS=1"
        assert status.latency_ms >= 0

    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_unhealthy_db(self, mock_get_pool):
        mock_get_pool.side_effect = Exception("Connection refused")

        status = await check_health()

        assert status.connected is False
        assert status.postgis_version is None


# =============================================================================
# Query Helpers
# =============================================================================


class TestExecute:
    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_execute_runs_query(self, mock_get_pool):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_pool = _make_mock_pool(mock_conn)
        mock_get_pool.return_value = mock_pool

        result = await execute("INSERT INTO states (name) VALUES ($1)", "Maharashtra")

        mock_conn.execute.assert_called_once_with(
            "INSERT INTO states (name) VALUES ($1)", "Maharashtra"
        )
        assert result == "INSERT 0 1"


class TestFetchOne:
    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_fetch_one_returns_row(self, mock_get_pool):
        mock_row = {"id": 1, "name": "Maharashtra"}
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = _make_mock_pool(mock_conn)
        mock_get_pool.return_value = mock_pool

        result = await fetch_one("SELECT * FROM states WHERE id = $1", 1)

        assert result == mock_row


class TestFetchAll:
    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_fetch_all_returns_rows(self, mock_get_pool):
        mock_rows = [{"id": 1, "name": "Maharashtra"}, {"id": 2, "name": "Tamil Nadu"}]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_pool = _make_mock_pool(mock_conn)
        mock_get_pool.return_value = mock_pool

        result = await fetch_all("SELECT * FROM states")

        assert result == mock_rows
        assert len(result) == 2


class TestFetchVal:
    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_fetch_val_returns_single_value(self, mock_get_pool):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=42)
        mock_pool = _make_mock_pool(mock_conn)
        mock_get_pool.return_value = mock_pool

        result = await fetch_val("SELECT COUNT(*) FROM states")

        assert result == 42


# =============================================================================
# Spatial Query Helpers
# =============================================================================


class TestFindWithinRadius:
    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_generates_correct_spatial_query(self, mock_get_pool):
        mock_rows = [{"id": 1, "name": "Hospital A"}]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_pool = _make_mock_pool(mock_conn)
        mock_get_pool.return_value = mock_pool

        result = await find_within_radius(
            table="districts",
            location_col="geometry",
            lat=28.6139,
            lon=77.2090,
            radius_km=50.0,
        )

        call_args = mock_conn.fetch.call_args
        query = call_args.args[0]
        assert "ST_DWithin" in query
        assert "::geography" in query
        assert "districts" in query
        assert result == mock_rows

    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_radius_converted_to_meters(self, mock_get_pool):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = _make_mock_pool(mock_conn)
        mock_get_pool.return_value = mock_pool

        await find_within_radius("districts", "geometry", 28.0, 77.0, 10.0)

        call_args = mock_conn.fetch.call_args
        query_args = call_args.args[1:]
        assert 10000.0 in query_args


class TestFindInPolygon:
    @pytest.mark.asyncio
    @patch("src.shared.db.get_pool", new_callable=AsyncMock)
    async def test_generates_correct_contains_query(self, mock_get_pool):
        mock_rows = [{"id": 1}]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_pool = _make_mock_pool(mock_conn)
        mock_get_pool.return_value = mock_pool

        polygon_wkt = "POLYGON((77.0 28.0,77.5 28.5,77.5 28.0,77.0 28.0))"
        result = await find_in_polygon("districts", "geometry", polygon_wkt)

        call_args = mock_conn.fetch.call_args
        query = call_args.args[0]
        assert "ST_Contains" in query
        assert "districts" in query
        assert result == mock_rows


# =============================================================================
# Module-level cleanup fixture
# =============================================================================


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset the module-level pool between tests."""
    import src.shared.db as db_module

    original = db_module._pool
    db_module._pool = None
    yield
    db_module._pool = original
