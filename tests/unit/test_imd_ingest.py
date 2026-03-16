"""Tests for IMD historical gridded data ingestion (S6.4).

Tests cover: Pydantic models (IMDGridPoint, IMDDownloadConfig, IMDIngestionReport),
download wrapper, parse wrapper, grid point extraction (rainfall + temperature + NaN),
bulk insert, spatial/temporal queries, full pipeline, error handling.
All external services (imdlib, asyncpg, filesystem) are mocked.
"""

import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import xarray as xr

from src.data.ingest.imd import (
    IMDDownloadConfig,
    IMDGridPoint,
    IMDIngestionReport,
    bulk_insert_observations,
    download_imd_data,
    extract_grid_points,
    ingest_imd_variable,
    parse_imd_data,
    query_district_rainfall,
    query_rainfall_timeseries,
)
from src.shared.errors import DataError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary directory for downloaded data."""
    return tmp_path / "imd_data"


@pytest.fixture
def sample_rainfall_ds():
    """Create a mock xarray Dataset mimicking imdlib rainfall output.

    imdlib returns a Dataset with variable 'rain' indexed by (time, lat, lon).
    Grid: 0.25° resolution over a small India subset.
    """
    times = [datetime.datetime(2020, 6, 1), datetime.datetime(2020, 6, 2)]
    lats = [28.0, 28.25]
    lons = [77.0, 77.25]
    data = np.array([
        [[10.5, 20.3], [15.0, np.nan]],  # day 1
        [[0.0, 5.2], [np.nan, 12.1]],     # day 2
    ])
    ds = xr.Dataset(
        {"rain": (["time", "lat", "lon"], data)},
        coords={
            "time": times,
            "lat": lats,
            "lon": lons,
        },
    )
    return ds


@pytest.fixture
def sample_tmin_ds():
    """Create a mock xarray Dataset for minimum temperature."""
    times = [datetime.datetime(2020, 1, 1)]
    lats = [28.0]
    lons = [77.0]
    data = np.array([[[8.5]]])
    ds = xr.Dataset(
        {"tmin": (["time", "lat", "lon"], data)},
        coords={"time": times, "lat": lats, "lon": lons},
    )
    return ds


@pytest.fixture
def sample_tmax_ds():
    """Create a mock xarray Dataset for maximum temperature."""
    times = [datetime.datetime(2020, 1, 1)]
    lats = [28.0]
    lons = [77.0]
    data = np.array([[[35.2]]])
    ds = xr.Dataset(
        {"tmax": (["time", "lat", "lon"], data)},
        coords={"time": times, "lat": lats, "lon": lons},
    )
    return ds


@pytest.fixture
def mock_pool():
    """Mock asyncpg pool with connection context manager.

    Returns (get_pool_coro, conn) where get_pool_coro is an async function
    that returns the mock pool.
    """
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.executemany = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)

    # Make pool.acquire() work as async context manager
    acm = AsyncMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acm

    return pool, conn


# =============================================================================
# Test: Pydantic Models
# =============================================================================


class TestIMDGridPoint:
    """Tests for IMDGridPoint Pydantic model."""

    def test_valid_rainfall_point(self):
        point = IMDGridPoint(
            latitude=28.0,
            longitude=77.0,
            date=datetime.date(2020, 6, 1),
            rainfall_mm=10.5,
        )
        assert point.latitude == 28.0
        assert point.longitude == 77.0
        assert point.rainfall_mm == 10.5
        assert point.temperature_min_c is None
        assert point.temperature_max_c is None

    def test_valid_temperature_point(self):
        point = IMDGridPoint(
            latitude=28.0,
            longitude=77.0,
            date=datetime.date(2020, 1, 1),
            temperature_min_c=8.5,
            temperature_max_c=35.2,
        )
        assert point.temperature_min_c == 8.5
        assert point.temperature_max_c == 35.2
        assert point.rainfall_mm is None

    def test_latitude_range(self):
        """Latitude must be within India's approximate range."""
        with pytest.raises(Exception):
            IMDGridPoint(
                latitude=91.0,
                longitude=77.0,
                date=datetime.date(2020, 1, 1),
            )

    def test_longitude_range(self):
        """Longitude must be within valid range."""
        with pytest.raises(Exception):
            IMDGridPoint(
                latitude=28.0,
                longitude=181.0,
                date=datetime.date(2020, 1, 1),
            )


class TestIMDDownloadConfig:
    """Tests for IMDDownloadConfig Pydantic model."""

    def test_valid_config(self, tmp_data_dir):
        config = IMDDownloadConfig(
            variable="rain",
            start_year=2019,
            end_year=2020,
            output_dir=tmp_data_dir,
        )
        assert config.variable == "rain"
        assert config.start_year == 2019
        assert config.end_year == 2020

    def test_invalid_variable(self, tmp_data_dir):
        with pytest.raises(Exception):
            IMDDownloadConfig(
                variable="wind",
                start_year=2019,
                end_year=2020,
                output_dir=tmp_data_dir,
            )

    def test_end_year_before_start_year(self, tmp_data_dir):
        with pytest.raises(Exception):
            IMDDownloadConfig(
                variable="rain",
                start_year=2020,
                end_year=2019,
                output_dir=tmp_data_dir,
            )


class TestIMDIngestionReport:
    """Tests for IMDIngestionReport model."""

    def test_default_report(self):
        report = IMDIngestionReport(variable="rain", year_range=(2019, 2020))
        assert report.grid_points_processed == 0
        assert report.rows_inserted == 0
        assert report.errors == []


# =============================================================================
# Test: Download
# =============================================================================


class TestDownloadIMDData:
    """Tests for download_imd_data function."""

    @patch("src.data.ingest.imd.imd")
    def test_download_rainfall(self, mock_imdlib, tmp_data_dir):
        """Download rainfall data via imdlib."""
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        config = IMDDownloadConfig(
            variable="rain",
            start_year=2020,
            end_year=2020,
            output_dir=tmp_data_dir,
        )
        result = download_imd_data(config)
        mock_imdlib.get_data.assert_called_once_with(
            "rain", 2020, 2020, fn_format="yearwise", file_dir=str(tmp_data_dir)
        )
        assert isinstance(result, Path)

    @patch("src.data.ingest.imd.imd")
    def test_download_error_raises_data_error(self, mock_imdlib, tmp_data_dir):
        """imdlib download failure raises DataError."""
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        mock_imdlib.get_data.side_effect = Exception("Network error")
        config = IMDDownloadConfig(
            variable="rain",
            start_year=2020,
            end_year=2020,
            output_dir=tmp_data_dir,
        )
        with pytest.raises(DataError, match="Failed to download IMD data"):
            download_imd_data(config)


# =============================================================================
# Test: Parse
# =============================================================================


class TestParseIMDData:
    """Tests for parse_imd_data function."""

    @patch("src.data.ingest.imd.imd")
    def test_parse_rainfall(self, mock_imdlib, tmp_path):
        """Parse IMD binary file into xarray Dataset."""
        file_path = tmp_path / "rain_2020.grd"
        file_path.touch()
        expected_ds = xr.Dataset({"rain": (["time"], [1.0])})
        mock_imdlib.open_data.return_value = expected_ds

        result = parse_imd_data(file_path, "rain")
        assert isinstance(result, xr.Dataset)
        mock_imdlib.open_data.assert_called_once()

    @patch("src.data.ingest.imd.imd")
    def test_parse_error_raises_data_error(self, mock_imdlib, tmp_path):
        """Parsing failure raises DataError."""
        file_path = tmp_path / "bad_file.grd"
        file_path.touch()
        mock_imdlib.open_data.side_effect = Exception("Corrupt file")

        with pytest.raises(DataError, match="Failed to parse IMD data"):
            parse_imd_data(file_path, "rain")


# =============================================================================
# Test: Extract Grid Points
# =============================================================================


class TestExtractGridPoints:
    """Tests for extract_grid_points function."""

    def test_extract_rainfall_points(self, sample_rainfall_ds):
        """Extract rainfall grid points from xarray Dataset."""
        points = extract_grid_points(sample_rainfall_ds, "rain")
        # 2 days × 2 lats × 2 lons = 8 total, but 2 are NaN → 6 non-NaN
        non_nan = [p for p in points if p.rainfall_mm is not None]
        assert len(non_nan) == 6
        # All points should have the right fields
        for p in points:
            assert isinstance(p, IMDGridPoint)
            assert p.date is not None

    def test_extract_handles_nan_as_none(self, sample_rainfall_ds):
        """NaN values in the grid should become None in IMDGridPoint."""
        points = extract_grid_points(sample_rainfall_ds, "rain")
        nan_points = [p for p in points if p.rainfall_mm is None]
        assert len(nan_points) == 2  # Two NaN values in fixture

    def test_extract_temperature_min(self, sample_tmin_ds):
        """Extract minimum temperature grid points."""
        points = extract_grid_points(sample_tmin_ds, "tmin")
        assert len(points) == 1
        assert points[0].temperature_min_c == 8.5
        assert points[0].rainfall_mm is None

    def test_extract_temperature_max(self, sample_tmax_ds):
        """Extract maximum temperature grid points."""
        points = extract_grid_points(sample_tmax_ds, "tmax")
        assert len(points) == 1
        assert points[0].temperature_max_c == 35.2
        assert points[0].rainfall_mm is None


# =============================================================================
# Test: Bulk Insert
# =============================================================================


class TestBulkInsertObservations:
    """Tests for async bulk_insert_observations function."""

    @pytest.mark.asyncio
    async def test_bulk_insert(self, mock_pool):
        """Insert grid points into imd_observations table."""
        pool, conn = mock_pool
        points = [
            IMDGridPoint(
                latitude=28.0,
                longitude=77.0,
                date=datetime.date(2020, 6, 1),
                rainfall_mm=10.5,
            ),
            IMDGridPoint(
                latitude=28.25,
                longitude=77.0,
                date=datetime.date(2020, 6, 1),
                rainfall_mm=15.0,
            ),
        ]
        mock_get_pool = AsyncMock(return_value=pool)
        with patch("src.data.ingest.imd.get_pool", mock_get_pool):
            count = await bulk_insert_observations(points)
        assert count == 2
        conn.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_insert_empty_list(self, mock_pool):
        """Empty list returns 0 with no DB calls."""
        pool, conn = mock_pool
        with patch("src.data.ingest.imd.get_pool", AsyncMock(return_value=pool)):
            count = await bulk_insert_observations([])
        assert count == 0
        conn.executemany.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_insert_batching(self, mock_pool):
        """Large lists are inserted in batches."""
        pool, conn = mock_pool
        points = [
            IMDGridPoint(
                latitude=28.0,
                longitude=77.0 + i * 0.25,
                date=datetime.date(2020, 6, 1),
                rainfall_mm=float(i),
            )
            for i in range(12)
        ]
        with patch("src.data.ingest.imd.get_pool", AsyncMock(return_value=pool)):
            count = await bulk_insert_observations(points, batch_size=5)
        assert count == 12
        # 12 points / 5 batch_size = 3 calls
        assert conn.executemany.call_count == 3


# =============================================================================
# Test: Query Helpers
# =============================================================================


class TestQueryHelpers:
    """Tests for spatial + temporal query functions."""

    @pytest.mark.asyncio
    async def test_query_rainfall_timeseries(self, mock_pool):
        """Query rainfall near a point within date range."""
        pool, conn = mock_pool
        mock_row = {
            "time": datetime.datetime(2020, 6, 1),
            "rainfall_mm": 10.5,
            "station_id": "grid_28.0_77.0",
        }
        conn.fetch = AsyncMock(return_value=[mock_row])

        with patch("src.data.ingest.imd.get_pool", AsyncMock(return_value=pool)):
            results = await query_rainfall_timeseries(
                lat=28.0,
                lon=77.0,
                start_date=datetime.date(2020, 6, 1),
                end_date=datetime.date(2020, 6, 30),
            )
        assert len(results) == 1
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_district_rainfall(self, mock_pool):
        """Query district-aggregated rainfall via spatial join."""
        pool, conn = mock_pool
        conn.fetch = AsyncMock(return_value=[])

        with patch("src.data.ingest.imd.get_pool", AsyncMock(return_value=pool)):
            results = await query_district_rainfall(
                district_id=42,
                start_date=datetime.date(2020, 6, 1),
                end_date=datetime.date(2020, 6, 30),
            )
        assert results == []
        conn.fetch.assert_called_once()


# =============================================================================
# Test: Full Pipeline
# =============================================================================


class TestIngestPipeline:
    """Tests for the full ingest_imd_variable pipeline."""

    @pytest.mark.asyncio
    async def test_ingest_pipeline_full(self, sample_rainfall_ds, mock_pool, tmp_path):
        """Full pipeline: download → parse → extract → insert."""
        pool, conn = mock_pool
        tmp_dir = tmp_path / "imd"
        tmp_dir.mkdir()

        config = IMDDownloadConfig(
            variable="rain",
            start_year=2020,
            end_year=2020,
            output_dir=tmp_dir,
        )

        with (
            patch("src.data.ingest.imd.download_imd_data", return_value=tmp_dir),
            patch(
                "src.data.ingest.imd.parse_imd_data", return_value=sample_rainfall_ds
            ),
            patch("src.data.ingest.imd.get_pool", AsyncMock(return_value=pool)),
        ):
            report = await ingest_imd_variable(config)

        assert isinstance(report, IMDIngestionReport)
        assert report.variable == "rain"
        assert report.year_range == (2020, 2020)
        assert report.rows_inserted > 0
        assert report.errors == []

    @pytest.mark.asyncio
    async def test_ingest_pipeline_download_error(self, tmp_path):
        """Download failure produces DataError in report."""
        tmp_dir = tmp_path / "imd"
        tmp_dir.mkdir()
        config = IMDDownloadConfig(
            variable="rain",
            start_year=2020,
            end_year=2020,
            output_dir=tmp_dir,
        )

        with patch(
            "src.data.ingest.imd.download_imd_data",
            side_effect=DataError("Failed to download IMD data"),
        ):
            report = await ingest_imd_variable(config)

        assert len(report.errors) > 0
        assert report.rows_inserted == 0
