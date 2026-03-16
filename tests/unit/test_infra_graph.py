"""Tests for src/data/ingest/infra_graph.py — Neo4j infrastructure dependency graph.

All tests mock the Neo4j driver. No real Neo4j connection required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.errors import GraphDBError

# ---------------------------------------------------------------------------
# Async iterator helper for mocking Neo4j cursors
# ---------------------------------------------------------------------------


class AsyncIterator:
    """Wraps a list into an async iterator for mocking Neo4j result cursors."""

    def __init__(self, items):
        self._items = list(items)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item

    async def single(self):
        return self._items[0] if self._items else None


def make_cursor(records):
    """Create a mock cursor that supports async for and .single()."""
    return AsyncIterator(records)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings():
    """CrisisSettings with default Neo4j config."""
    settings = MagicMock()
    settings.NEO4J_URI = "bolt://localhost:7687"
    settings.NEO4J_USER = "neo4j"
    settings.NEO4J_PASSWORD = "crisis_dev"
    return settings


@pytest.fixture
def mock_driver():
    """Mock neo4j.AsyncGraphDatabase.driver."""
    driver = MagicMock()
    session = AsyncMock()
    # driver.session() must return an async context manager (not a coroutine)
    # MagicMock.__call__ returns the session directly; session has __aenter__/__aexit__
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = session
    driver.verify_connectivity = AsyncMock()
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def mock_session(mock_driver):
    """Return the session from mock_driver."""
    return mock_driver.session.return_value


# ---------------------------------------------------------------------------
# Import helpers (lazy import to avoid import-time Neo4j connection)
# ---------------------------------------------------------------------------


def _import_module():
    from src.data.ingest import infra_graph

    return infra_graph


# ---------------------------------------------------------------------------
# R1: Neo4j Connection Management
# ---------------------------------------------------------------------------


class TestNeo4jConnection:
    @pytest.mark.asyncio
    async def test_neo4j_health_check_success(self, mock_settings, mock_driver):
        mod = _import_module()
        with patch.object(mod, "_get_driver", return_value=mock_driver):
            mgr = mod.InfraGraphManager(settings=mock_settings)
            mgr._driver = mock_driver
            mock_driver.verify_connectivity = AsyncMock()
            result = await mgr.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_neo4j_health_check_failure(self, mock_settings, mock_driver):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver
        mock_driver.verify_connectivity = AsyncMock(side_effect=Exception("conn refused"))
        result = await mgr.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_neo4j_connect_raises_graphdberror(self, mock_settings):
        mod = _import_module()
        with patch.object(
            mod,
            "_get_driver",
            side_effect=Exception("connection refused"),
        ):
            mgr = mod.InfraGraphManager(settings=mock_settings)
            with pytest.raises(GraphDBError, match="Neo4j"):
                await mgr.connect()


# ---------------------------------------------------------------------------
# R2: Node Pydantic Models
# ---------------------------------------------------------------------------


class TestNodeModels:
    def test_power_grid_model(self):
        mod = _import_module()
        node = mod.PowerGridNode(
            name="Mumbai BEST",
            type="distribution",
            state="Maharashtra",
            capacity_mw=500.0,
            status="operational",
        )
        assert node.name == "Mumbai BEST"
        assert node.type == "distribution"

    def test_hospital_model(self):
        mod = _import_module()
        node = mod.HospitalNode(
            name="KEM Hospital",
            beds=1800,
            type="government",
            district="Mumbai City",
            state="Maharashtra",
            status="operational",
        )
        assert node.beds == 1800

    def test_telecom_tower_model(self):
        mod = _import_module()
        node = mod.TelecomTowerNode(
            name="Jio Tower Andheri",
            operator="Jio",
            backup_hours=8,
            type="4G",
            state="Maharashtra",
            status="operational",
        )
        assert node.backup_hours == 8

    def test_cascade_result_model(self):
        mod = _import_module()
        result = mod.CascadeResult(
            affected_node="KEM Hospital",
            affected_label="Hospital",
            impact_type="power_loss",
            estimated_recovery_hours=24.0,
            path=["Mumbai BEST PowerGrid", "KEM Hospital"],
        )
        assert result.impact_type == "power_loss"
        assert len(result.path) == 2


# ---------------------------------------------------------------------------
# R4: Schema Initialization
# ---------------------------------------------------------------------------


class TestSchemaInit:
    @pytest.mark.asyncio
    async def test_init_schema_creates_constraints(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver
        mock_session.run = AsyncMock()

        await mgr.init_schema()

        # Should have executed constraint creation queries
        assert mock_session.run.call_count > 0
        calls = [str(c) for c in mock_session.run.call_args_list]
        # Check that at least one constraint call was made
        constraint_calls = [c for c in calls if "CONSTRAINT" in c or "INDEX" in c]
        assert len(constraint_calls) > 0

    @pytest.mark.asyncio
    async def test_init_schema_idempotent(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver
        mock_session.run = AsyncMock()

        # Call twice — should not error
        await mgr.init_schema()
        await mgr.init_schema()


# ---------------------------------------------------------------------------
# R5: Seed Data
# ---------------------------------------------------------------------------


class TestSeedData:
    @pytest.mark.asyncio
    async def test_seed_city_creates_nodes(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver
        mock_session.run = AsyncMock()

        await mgr.seed_city("mumbai")

        # Should have executed MERGE queries for nodes
        assert mock_session.run.call_count > 0

    @pytest.mark.asyncio
    async def test_seed_city_creates_relationships(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver
        mock_session.run = AsyncMock()

        await mgr.seed_city("mumbai")

        # Check that relationship queries were issued
        calls_str = " ".join(str(c) for c in mock_session.run.call_args_list)
        assert "POWERS" in calls_str or "DEPENDS_ON" in calls_str or "MERGE" in calls_str

    @pytest.mark.asyncio
    async def test_seed_all_creates_all_cities(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver
        mock_session.run = AsyncMock()

        await mgr.seed_all()

        # Should have created nodes for all 5 cities
        assert mock_session.run.call_count > 10  # At minimum

    @pytest.mark.asyncio
    async def test_seed_city_invalid_name(self, mock_settings, mock_driver):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver

        with pytest.raises(ValueError, match="Unknown city"):
            await mgr.seed_city("invalid_city")

    def test_city_data_has_five_cities(self):
        mod = _import_module()
        assert len(mod.CITY_DATA) == 5
        expected = {"mumbai", "chennai", "kolkata", "bhubaneswar", "guwahati"}
        assert set(mod.CITY_DATA.keys()) == expected


# ---------------------------------------------------------------------------
# R6: Cascading Failure Analysis
# ---------------------------------------------------------------------------


class TestCascadingFailure:
    @pytest.mark.asyncio
    async def test_simulate_failure_power_grid(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver

        # Mock: power grid failure cascades to hospital and telecom
        mock_record1 = MagicMock()
        mock_record1.data.return_value = {
            "affected": {"name": "KEM Hospital", "status": "operational"},
            "labels": ["Hospital"],
            "path_nodes": ["Mumbai BEST", "KEM Hospital"],
        }
        mock_record2 = MagicMock()
        mock_record2.data.return_value = {
            "affected": {"name": "Jio Tower Andheri", "status": "operational"},
            "labels": ["TelecomTower"],
            "path_nodes": ["Mumbai BEST", "Jio Tower Andheri"],
        }

        mock_session.run = AsyncMock(return_value=make_cursor([mock_record1, mock_record2]))

        results = await mgr.get_downstream_impacts("PowerGrid", "Mumbai BEST", "Maharashtra")
        assert len(results) == 2
        affected_names = [r.affected_node for r in results]
        assert "KEM Hospital" in affected_names
        assert "Jio Tower Andheri" in affected_names

    @pytest.mark.asyncio
    async def test_simulate_failure_no_cascade(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver

        # No downstream impacts (leaf node)
        mock_session.run = AsyncMock(return_value=make_cursor([]))

        results = await mgr.get_downstream_impacts("Hospital", "KEM Hospital", "Maharashtra")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_upstream_dependencies(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver

        mock_record = MagicMock()
        mock_record.data.return_value = {
            "dep": {"name": "Mumbai BEST", "status": "operational"},
            "labels": ["PowerGrid"],
        }
        mock_session.run = AsyncMock(return_value=make_cursor([mock_record]))

        results = await mgr.get_upstream_dependencies("Hospital", "KEM Hospital", "Maharashtra")
        assert len(results) == 1
        assert results[0]["name"] == "Mumbai BEST"


# ---------------------------------------------------------------------------
# R7: Graph Query Utilities
# ---------------------------------------------------------------------------


class TestGraphQueries:
    @pytest.mark.asyncio
    async def test_get_infrastructure_by_district(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver

        mock_record = MagicMock()
        mock_record.data.return_value = {
            "n": {"name": "KEM Hospital", "beds": 1800},
            "labels": ["Hospital"],
        }
        mock_session.run = AsyncMock(return_value=make_cursor([mock_record]))

        results = await mgr.get_infrastructure_by_district("Mumbai City", "Maharashtra")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_infrastructure_by_state(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver

        mock_record = MagicMock()
        mock_record.data.return_value = {
            "n": {"name": "Mumbai BEST"},
            "labels": ["PowerGrid"],
        }
        mock_session.run = AsyncMock(return_value=make_cursor([mock_record]))

        results = await mgr.get_infrastructure_by_state("Maharashtra")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_infrastructure_status_summary(
        self, mock_settings, mock_driver, mock_session
    ):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver

        mock_record = MagicMock()
        mock_record.data.return_value = {
            "label": "PowerGrid",
            "status": "operational",
            "count": 5,
        }
        mock_session.run = AsyncMock(return_value=make_cursor([mock_record]))

        summary = await mgr.get_infrastructure_status_summary()
        assert len(summary) >= 1
        assert summary[0]["label"] == "PowerGrid"

    @pytest.mark.asyncio
    async def test_update_node_status(self, mock_settings, mock_driver, mock_session):
        mod = _import_module()
        mgr = mod.InfraGraphManager(settings=mock_settings)
        mgr._driver = mock_driver
        mock_session.run = AsyncMock()

        await mgr.update_node_status("PowerGrid", "Mumbai BEST", "Maharashtra", "damaged")
        mock_session.run.assert_called_once()
        call_args = str(mock_session.run.call_args)
        assert "damaged" in call_args
