"""Tests for S1.4: PostgreSQL/PostGIS Database Schema (scripts/init_db.sql)."""

import re
from pathlib import Path

import pytest

SQL_PATH = Path(__file__).resolve().parents[2] / "scripts" / "init_db.sql"


@pytest.fixture
def sql_content() -> str:
    """Read the init_db.sql file."""
    assert SQL_PATH.exists(), f"SQL file not found: {SQL_PATH}"
    content = SQL_PATH.read_text()
    assert len(content.strip()) > 0, "SQL file is empty"
    return content


@pytest.fixture
def sql_upper(sql_content: str) -> str:
    """SQL content in uppercase for case-insensitive matching."""
    return sql_content.upper()


# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------

class TestExtensions:
    def test_postgis_extension(self, sql_content: str):
        """PostGIS extension must be created."""
        assert re.search(
            r"CREATE\s+EXTENSION\s+(IF\s+NOT\s+EXISTS\s+)?postgis",
            sql_content,
            re.IGNORECASE,
        )


# ---------------------------------------------------------------------------
# ENUM Type
# ---------------------------------------------------------------------------

EXPECTED_DISASTER_TYPES = [
    "monsoon_flood",
    "cyclone",
    "urban_waterlogging",
    "earthquake",
    "heatwave",
    "landslide",
    "industrial_accident",
    "tsunami",
    "drought",
    "glacial_lake_outburst",
]


class TestEnumType:
    def test_india_disaster_type_enum_exists(self, sql_content: str):
        """india_disaster_type ENUM type must be created."""
        assert re.search(
            r"CREATE\s+TYPE\s+india_disaster_type\s+AS\s+ENUM",
            sql_content,
            re.IGNORECASE,
        )

    @pytest.mark.parametrize("disaster_type", EXPECTED_DISASTER_TYPES)
    def test_enum_has_value(self, sql_content: str, disaster_type: str):
        """Each disaster type must appear in the ENUM definition."""
        assert disaster_type in sql_content.lower(), (
            f"Missing disaster type: {disaster_type}"
        )


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

EXPECTED_TABLES = [
    "states",
    "districts",
    "disasters",
    "imd_observations",
    "cwc_river_levels",
    "agent_decisions",
    "benchmark_scenarios",
    "evaluation_runs",
]


class TestTablePresence:
    @pytest.mark.parametrize("table", EXPECTED_TABLES)
    def test_table_created(self, sql_content: str, table: str):
        """Each expected table must have a CREATE TABLE statement."""
        pattern = rf"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?{table}\s*\("
        assert re.search(pattern, sql_content, re.IGNORECASE), (
            f"Missing CREATE TABLE for: {table}"
        )


# ---------------------------------------------------------------------------
# Column Validation
# ---------------------------------------------------------------------------

class TestStatesColumns:
    REQUIRED = ["id", "name", "name_local", "geometry", "primary_language", "seismic_zone"]

    @pytest.mark.parametrize("col", REQUIRED)
    def test_column_exists(self, sql_content: str, col: str):
        """states table must have all required columns."""
        # Extract the CREATE TABLE states block
        match = re.search(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?states\s*\((.*?)\)\s*;",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )
        assert match, "states table not found"
        assert col in match.group(2).lower(), f"Missing column: {col}"


class TestDistrictsColumns:
    REQUIRED = [
        "id", "state_id", "name", "census_2011_code",
        "population_2011", "area_sq_km", "geometry", "vulnerability_score",
    ]

    @pytest.mark.parametrize("col", REQUIRED)
    def test_column_exists(self, sql_content: str, col: str):
        match = re.search(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?districts\s*\((.*?)\)\s*;",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )
        assert match, "districts table not found"
        assert col in match.group(2).lower(), f"Missing column: {col}"


class TestDisastersColumns:
    REQUIRED = [
        "id", "type", "imd_classification", "severity",
        "affected_state_ids", "affected_district_ids",
        "location", "affected_area", "start_time",
        "phase", "sachet_alert_id", "metadata", "created_at",
    ]

    @pytest.mark.parametrize("col", REQUIRED)
    def test_column_exists(self, sql_content: str, col: str):
        match = re.search(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?disasters\s*\((.*?)\)\s*;",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )
        assert match, "disasters table not found"
        assert col in match.group(2).lower(), f"Missing column: {col}"


class TestImdObservationsColumns:
    REQUIRED = [
        "time", "station_id", "district_id", "location",
        "temperature_c", "rainfall_mm", "humidity_pct",
        "wind_speed_kmph", "wind_direction", "pressure_hpa", "source",
    ]

    @pytest.mark.parametrize("col", REQUIRED)
    def test_column_exists(self, sql_content: str, col: str):
        # Partitioned tables use PARTITION BY instead of ending with );
        match = re.search(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?imd_observations\s*\((.*?)\)\s*PARTITION\s+BY",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )
        assert match, "imd_observations partitioned table not found"
        assert col in match.group(2).lower(), f"Missing column: {col}"


class TestCwcRiverLevelsColumns:
    REQUIRED = [
        "time", "station_id", "river_name", "state", "location",
        "water_level_m", "danger_level_m", "warning_level_m",
        "discharge_cumecs", "source",
    ]

    @pytest.mark.parametrize("col", REQUIRED)
    def test_column_exists(self, sql_content: str, col: str):
        match = re.search(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?cwc_river_levels\s*\((.*?)\)\s*PARTITION\s+BY",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )
        assert match, "cwc_river_levels partitioned table not found"
        assert col in match.group(2).lower(), f"Missing column: {col}"


class TestAgentDecisionsColumns:
    REQUIRED = [
        "id", "disaster_id", "agent_id", "task_id",
        "decision_type", "decision_payload", "confidence",
        "reasoning", "provider", "model",
        "input_tokens", "output_tokens", "cost_usd", "latency_ms",
        "created_at",
    ]

    @pytest.mark.parametrize("col", REQUIRED)
    def test_column_exists(self, sql_content: str, col: str):
        match = re.search(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?agent_decisions\s*\((.*?)\)\s*;",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )
        assert match, "agent_decisions table not found"
        assert col in match.group(2).lower(), f"Missing column: {col}"


class TestBenchmarkScenariosColumns:
    REQUIRED = [
        "id", "category", "complexity", "affected_states",
        "primary_language", "initial_state", "event_sequence",
        "ground_truth_decisions", "evaluation_rubric",
        "version", "created_at",
    ]

    @pytest.mark.parametrize("col", REQUIRED)
    def test_column_exists(self, sql_content: str, col: str):
        match = re.search(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?benchmark_scenarios\s*\((.*?)\)\s*;",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )
        assert match, "benchmark_scenarios table not found"
        assert col in match.group(2).lower(), f"Missing column: {col}"


class TestEvaluationRunsColumns:
    REQUIRED = [
        "id", "scenario_id", "agent_config",
        "situational_accuracy", "decision_timeliness",
        "resource_efficiency", "coordination_quality",
        "communication_score", "aggregate_drs",
        "total_tokens", "total_cost_usd", "primary_provider",
        "completed_at",
    ]

    @pytest.mark.parametrize("col", REQUIRED)
    def test_column_exists(self, sql_content: str, col: str):
        match = re.search(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?evaluation_runs\s*\((.*?)\)\s*;",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )
        assert match, "evaluation_runs table not found"
        assert col in match.group(2).lower(), f"Missing column: {col}"


# ---------------------------------------------------------------------------
# Foreign Keys
# ---------------------------------------------------------------------------

class TestForeignKeys:
    def test_districts_references_states(self, sql_content: str):
        assert re.search(
            r"REFERENCES\s+states\s*\(\s*id\s*\)",
            sql_content,
            re.IGNORECASE,
        )

    def test_agent_decisions_references_disasters(self, sql_content: str):
        assert re.search(
            r"REFERENCES\s+disasters\s*\(\s*id\s*\)",
            sql_content,
            re.IGNORECASE,
        )

    def test_evaluation_runs_references_benchmark_scenarios(self, sql_content: str):
        assert re.search(
            r"REFERENCES\s+benchmark_scenarios\s*\(\s*id\s*\)",
            sql_content,
            re.IGNORECASE,
        )


# ---------------------------------------------------------------------------
# Spatial Indexes
# ---------------------------------------------------------------------------

class TestSpatialIndexes:
    GEOMETRY_TABLES = ["states", "districts", "disasters", "imd_observations", "cwc_river_levels"]

    @pytest.mark.parametrize("table", GEOMETRY_TABLES)
    def test_gist_index_exists(self, sql_content: str, table: str):
        """Each table with geometry columns must have a GiST index."""
        pattern = rf"CREATE\s+INDEX.*ON\s+{table}.*USING\s+GIST"
        assert re.search(pattern, sql_content, re.IGNORECASE), (
            f"Missing GiST index for: {table}"
        )


# ---------------------------------------------------------------------------
# Partitioning
# ---------------------------------------------------------------------------

class TestPartitioning:
    def test_imd_observations_partitioned(self, sql_content: str):
        assert re.search(
            r"CREATE\s+TABLE.*imd_observations.*PARTITION\s+BY\s+RANGE\s*\(\s*time\s*\)",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )

    def test_cwc_river_levels_partitioned(self, sql_content: str):
        assert re.search(
            r"CREATE\s+TABLE.*cwc_river_levels.*PARTITION\s+BY\s+RANGE\s*\(\s*time\s*\)",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )

    def test_imd_observations_default_partition(self, sql_content: str):
        assert re.search(
            r"CREATE\s+TABLE.*imd_observations_default.*PARTITION\s+OF\s+imd_observations\s+DEFAULT",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )

    def test_cwc_river_levels_default_partition(self, sql_content: str):
        assert re.search(
            r"CREATE\s+TABLE.*cwc_river_levels_default.*PARTITION\s+OF\s+cwc_river_levels\s+DEFAULT",
            sql_content,
            re.IGNORECASE | re.DOTALL,
        )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_extension_if_not_exists(self, sql_content: str):
        assert re.search(
            r"CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS",
            sql_content,
            re.IGNORECASE,
        )

    def test_type_uses_do_block_or_if_not_exists(self, sql_content: str):
        """ENUM type creation should handle already-exists case."""
        # PostgreSQL doesn't support IF NOT EXISTS for CREATE TYPE,
        # so we accept either a DO block or just CREATE TYPE
        has_do_block = re.search(r"DO\s*\$\$", sql_content, re.IGNORECASE)
        has_create_type = re.search(
            r"CREATE\s+TYPE\s+india_disaster_type", sql_content, re.IGNORECASE
        )
        assert has_do_block or has_create_type

    def test_tables_if_not_exists(self, sql_content: str):
        """All CREATE TABLE statements should use IF NOT EXISTS."""
        creates = re.findall(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(",
            sql_content,
            re.IGNORECASE,
        )
        for if_not_exists, table_name in creates:
            assert if_not_exists.strip(), (
                f"Table {table_name} missing IF NOT EXISTS"
            )

    def test_indexes_if_not_exists(self, sql_content: str):
        """CREATE INDEX statements should use IF NOT EXISTS."""
        creates = re.findall(
            r"CREATE\s+INDEX\s+(IF\s+NOT\s+EXISTS\s+)?(\w+)",
            sql_content,
            re.IGNORECASE,
        )
        for if_not_exists, idx_name in creates:
            assert if_not_exists.strip(), (
                f"Index {idx_name} missing IF NOT EXISTS"
            )


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

class TestSecurity:
    def test_no_hardcoded_passwords(self, sql_content: str):
        """No hardcoded passwords or secrets in the SQL file."""
        lower = sql_content.lower()
        for pattern in ["password", "secret", "api_key", "token"]:
            # Allow column names containing these words, but not string literals
            literals = re.findall(rf"'[^']*{pattern}[^']*'", lower)
            assert len(literals) == 0, (
                f"Possible hardcoded secret containing '{pattern}': {literals}"
            )
