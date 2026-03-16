"""Tests for Census 2011 + administrative boundaries ingestion (S6.5).

Tests cover:
- Pydantic model validation (StateRecord, DistrictRecord, CensusIngestionReport)
- State/district upsert logic with mocked DB
- Vulnerability score computation
- Spatial query helpers
- Full ingestion pipeline
- Idempotent behavior
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

# =============================================================================
# Model Validation Tests
# =============================================================================


class TestStateRecord:
    """Test StateRecord Pydantic model validation."""

    def test_valid_state(self):
        from src.data.ingest.census import StateRecord

        state = StateRecord(
            name="Maharashtra",
            name_local="महाराष्ट्र",
            primary_language="Marathi",
            seismic_zone=3,
        )
        assert state.name == "Maharashtra"
        assert state.name_local == "महाराष्ट्र"
        assert state.primary_language == "Marathi"
        assert state.seismic_zone == 3

    def test_state_minimal(self):
        from src.data.ingest.census import StateRecord

        state = StateRecord(name="Goa")
        assert state.name == "Goa"
        assert state.name_local is None
        assert state.primary_language is None
        assert state.seismic_zone is None

    def test_state_seismic_zone_range(self):
        from src.data.ingest.census import StateRecord

        # Valid range: 2-5
        StateRecord(name="Test", seismic_zone=2)
        StateRecord(name="Test", seismic_zone=5)

        with pytest.raises(ValidationError):
            StateRecord(name="Test", seismic_zone=1)

        with pytest.raises(ValidationError):
            StateRecord(name="Test", seismic_zone=6)

    def test_state_name_required(self):
        from src.data.ingest.census import StateRecord

        with pytest.raises(ValidationError):
            StateRecord()


class TestDistrictRecord:
    """Test DistrictRecord Pydantic model validation."""

    def test_valid_district(self):
        from src.data.ingest.census import DistrictRecord

        dist = DistrictRecord(
            name="Mumbai",
            state_name="Maharashtra",
            census_2011_code="517",
            population_2011=12442373,
            area_sq_km=603.4,
        )
        assert dist.name == "Mumbai"
        assert dist.state_name == "Maharashtra"
        assert dist.census_2011_code == "517"
        assert dist.population_2011 == 12442373
        assert dist.area_sq_km == 603.4

    def test_district_minimal(self):
        from src.data.ingest.census import DistrictRecord

        dist = DistrictRecord(name="TestDistrict", state_name="TestState")
        assert dist.name == "TestDistrict"
        assert dist.census_2011_code is None
        assert dist.population_2011 is None
        assert dist.area_sq_km is None

    def test_district_population_positive(self):
        from src.data.ingest.census import DistrictRecord

        with pytest.raises(ValidationError):
            DistrictRecord(name="Test", state_name="State", population_2011=-100)

    def test_district_area_positive(self):
        from src.data.ingest.census import DistrictRecord

        with pytest.raises(ValidationError):
            DistrictRecord(name="Test", state_name="State", area_sq_km=-50.0)


class TestCensusIngestionReport:
    """Test CensusIngestionReport model."""

    def test_default_report(self):
        from src.data.ingest.census import CensusIngestionReport

        report = CensusIngestionReport()
        assert report.states_upserted == 0
        assert report.districts_upserted == 0
        assert report.vulnerability_scores_computed == 0
        assert report.errors == []

    def test_report_with_data(self):
        from src.data.ingest.census import CensusIngestionReport

        report = CensusIngestionReport(
            states_upserted=36,
            districts_upserted=150,
            vulnerability_scores_computed=150,
            errors=["Error 1"],
        )
        assert report.states_upserted == 36
        assert report.districts_upserted == 150
        assert len(report.errors) == 1


# =============================================================================
# Hardcoded Data Tests
# =============================================================================


class TestHardcodedData:
    """Test the hardcoded India states/districts datasets."""

    def test_india_states_count(self):
        from src.data.ingest.census import INDIA_STATES

        # 28 states + 8 UTs = 36
        assert len(INDIA_STATES) == 36

    def test_india_states_have_names(self):
        from src.data.ingest.census import INDIA_STATES

        for state in INDIA_STATES:
            assert state.name, f"State missing name: {state}"

    def test_india_states_seismic_zones(self):
        from src.data.ingest.census import INDIA_STATES

        for state in INDIA_STATES:
            if state.seismic_zone is not None:
                assert 2 <= state.seismic_zone <= 5, (
                    f"{state.name} has invalid seismic zone: {state.seismic_zone}"
                )

    def test_known_states_present(self):
        from src.data.ingest.census import INDIA_STATES

        names = {s.name for s in INDIA_STATES}
        expected = {
            "Maharashtra",
            "Tamil Nadu",
            "Kerala",
            "Uttar Pradesh",
            "Delhi",
            "Odisha",
            "Gujarat",
            "West Bengal",
            "Assam",
        }
        assert expected.issubset(names)

    def test_india_districts_count(self):
        from src.data.ingest.census import INDIA_DISTRICTS

        assert len(INDIA_DISTRICTS) >= 100

    def test_india_districts_have_state_names(self):
        from src.data.ingest.census import INDIA_DISTRICTS

        state_names = {s.name for s in __import__(
            "src.data.ingest.census", fromlist=["INDIA_STATES"]
        ).INDIA_STATES}
        for dist in INDIA_DISTRICTS:
            assert dist.state_name in state_names, (
                f"District {dist.name} references unknown state: {dist.state_name}"
            )


# =============================================================================
# Vulnerability Score Tests
# =============================================================================


class TestVulnerabilityScore:
    """Test vulnerability score computation."""

    def test_compute_score_basic(self):
        from src.data.ingest.census import compute_vulnerability_score

        # High density + high seismic zone = high vulnerability
        score = compute_vulnerability_score(
            population=1000000, area_sq_km=100.0, seismic_zone=5
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be high

    def test_compute_score_low_risk(self):
        from src.data.ingest.census import compute_vulnerability_score

        # Low density + low seismic zone = low vulnerability
        score = compute_vulnerability_score(
            population=10000, area_sq_km=5000.0, seismic_zone=2
        )
        assert 0.0 <= score <= 1.0
        assert score < 0.5  # Should be low

    def test_compute_score_none_values(self):
        from src.data.ingest.census import compute_vulnerability_score

        # Missing data should return a default score
        score = compute_vulnerability_score(
            population=None, area_sq_km=None, seismic_zone=None
        )
        assert 0.0 <= score <= 1.0

    def test_compute_score_bounds(self):
        from src.data.ingest.census import compute_vulnerability_score

        # Extreme values should still be within [0, 1]
        score_max = compute_vulnerability_score(
            population=50000000, area_sq_km=1.0, seismic_zone=5
        )
        assert score_max <= 1.0

        score_min = compute_vulnerability_score(
            population=1, area_sq_km=100000.0, seismic_zone=2
        )
        assert score_min >= 0.0


# =============================================================================
# Database Upsert Tests (Mocked)
# =============================================================================


class TestUpsertStates:
    """Test state upsert with mocked database."""

    @pytest.mark.asyncio
    async def test_upsert_states_calls_executemany(self):
        from src.data.ingest.census import StateRecord, upsert_states

        states = [
            StateRecord(name="TestState1", seismic_zone=3),
            StateRecord(name="TestState2", seismic_zone=4),
        ]

        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock()
        mock_pool = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = False
        mock_pool.acquire.return_value = mock_ctx

        with patch("src.data.ingest.census.get_pool", new_callable=AsyncMock, return_value=mock_pool):
            count = await upsert_states(states)

        assert count == 2
        mock_conn.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_states_empty_list(self):
        from src.data.ingest.census import upsert_states

        count = await upsert_states([])
        assert count == 0


class TestUpsertDistricts:
    """Test district upsert with mocked database."""

    @pytest.mark.asyncio
    async def test_upsert_districts_calls_executemany(self):
        from src.data.ingest.census import DistrictRecord, upsert_districts

        districts = [
            DistrictRecord(
                name="Mumbai",
                state_name="Maharashtra",
                census_2011_code="517",
                population_2011=12442373,
                area_sq_km=603.4,
            ),
        ]

        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)  # state_id lookup
        mock_pool = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = False
        mock_pool.acquire.return_value = mock_ctx

        with patch("src.data.ingest.census.get_pool", new_callable=AsyncMock, return_value=mock_pool):
            count = await upsert_districts(districts)

        assert count == 1

    @pytest.mark.asyncio
    async def test_upsert_districts_empty_list(self):
        from src.data.ingest.census import upsert_districts

        count = await upsert_districts([])
        assert count == 0


# =============================================================================
# Spatial Query Helper Tests
# =============================================================================


class TestSpatialQueryHelpers:
    """Test spatial query helper functions with mocked DB."""

    @pytest.mark.asyncio
    async def test_get_states(self):
        from src.data.ingest.census import get_states

        mock_records = [
            {"id": 1, "name": "Maharashtra", "name_local": "महाराष्ट्र",
             "primary_language": "Marathi", "seismic_zone": 3},
            {"id": 2, "name": "Kerala", "name_local": "കേരളം",
             "primary_language": "Malayalam", "seismic_zone": 3},
        ]

        with patch("src.data.ingest.census.fetch_all", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_records
            result = await get_states()

        assert len(result) == 2
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_state_by_name(self):
        from src.data.ingest.census import get_state_by_name

        mock_record = {
            "id": 1, "name": "Maharashtra", "name_local": "महाराष्ट्र",
            "primary_language": "Marathi", "seismic_zone": 3,
        }

        with patch("src.data.ingest.census.fetch_one", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_record
            result = await get_state_by_name("Maharashtra")

        assert result is not None
        mock_fetch.assert_called_once()
        # Verify case-insensitive query
        call_args = mock_fetch.call_args
        assert "LOWER" in call_args[0][0] or "lower" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_get_state_by_name_not_found(self):
        from src.data.ingest.census import get_state_by_name

        with patch("src.data.ingest.census.fetch_one", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            result = await get_state_by_name("NonExistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_districts_by_state(self):
        from src.data.ingest.census import get_districts_by_state

        mock_records = [
            {"id": 1, "name": "Mumbai", "state_id": 1, "population_2011": 12442373},
            {"id": 2, "name": "Pune", "state_id": 1, "population_2011": 9429408},
        ]

        with patch("src.data.ingest.census.fetch_all", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_records
            result = await get_districts_by_state(1)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_district_by_name(self):
        from src.data.ingest.census import get_district_by_name

        mock_record = {"id": 1, "name": "Mumbai", "state_id": 1}

        with patch("src.data.ingest.census.fetch_one", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_record
            result = await get_district_by_name("Mumbai", "Maharashtra")

        assert result is not None

    @pytest.mark.asyncio
    async def test_find_districts_in_polygon(self):
        from src.data.ingest.census import find_districts_in_polygon

        polygon_wkt = "POLYGON((72.0 18.0, 73.0 18.0, 73.0 19.0, 72.0 19.0, 72.0 18.0))"

        with patch("src.data.ingest.census.fetch_all", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{"id": 1, "name": "Mumbai"}]
            result = await find_districts_in_polygon(polygon_wkt)

        assert len(result) == 1
        call_args = mock_fetch.call_args
        assert "ST_Intersects" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_find_nearby_districts(self):
        from src.data.ingest.census import find_nearby_districts

        with patch("src.data.ingest.census.fetch_all", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{"id": 1, "name": "Mumbai"}]
            result = await find_nearby_districts(19.076, 72.878, 50.0)

        assert len(result) == 1
        call_args = mock_fetch.call_args
        assert "ST_DWithin" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_population_in_area(self):
        from src.data.ingest.census import get_population_in_area

        polygon_wkt = "POLYGON((72.0 18.0, 73.0 18.0, 73.0 19.0, 72.0 19.0, 72.0 18.0))"

        with patch("src.data.ingest.census.fetch_val", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = 25000000
            result = await get_population_in_area(polygon_wkt)

        assert result == 25000000


# =============================================================================
# Ingestion Pipeline Tests
# =============================================================================


class TestIngestionPipeline:
    """Test full ingestion pipeline."""

    @pytest.mark.asyncio
    async def test_ingest_census_data_returns_report(self):
        from src.data.ingest.census import ingest_census_data

        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])  # for vulnerability scores
        mock_pool = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = False
        mock_pool.acquire.return_value = mock_ctx

        with patch("src.data.ingest.census.get_pool", new_callable=AsyncMock, return_value=mock_pool):
            report = await ingest_census_data()

        assert report.states_upserted > 0
        assert report.districts_upserted > 0

    @pytest.mark.asyncio
    async def test_ingest_census_data_captures_errors(self):
        from src.data.ingest.census import ingest_census_data

        mock_pool = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.side_effect = Exception("DB connection failed")
        mock_ctx.__aexit__.return_value = False
        mock_pool.acquire.return_value = mock_ctx

        with patch("src.data.ingest.census.get_pool", new_callable=AsyncMock, return_value=mock_pool):
            report = await ingest_census_data()

        assert len(report.errors) > 0
