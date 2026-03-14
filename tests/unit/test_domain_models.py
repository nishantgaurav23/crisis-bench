"""Tests for src/shared/models.py — Pydantic domain models.

TDD Red Phase: All tests written before implementation.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

# =============================================================================
# Enum Tests
# =============================================================================


class TestIndiaDisasterType:
    """IndiaDisasterType enum matches DB india_disaster_type."""

    def test_all_values_present(self):
        from src.shared.models import IndiaDisasterType

        expected = {
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
        }
        actual = {e.value for e in IndiaDisasterType}
        assert actual == expected

    def test_count(self):
        from src.shared.models import IndiaDisasterType

        assert len(IndiaDisasterType) == 10


class TestDisasterPhase:
    """DisasterPhase enum covers full lifecycle."""

    def test_all_values(self):
        from src.shared.models import DisasterPhase

        expected = {"pre_event", "active_response", "recovery", "post_event"}
        actual = {e.value for e in DisasterPhase}
        assert actual == expected


class TestAgentType:
    """AgentType enum covers all 7 agents."""

    def test_all_agents(self):
        from src.shared.models import AgentType

        expected = {
            "orchestrator",
            "situation_sense",
            "predictive_risk",
            "resource_allocation",
            "community_comms",
            "infra_status",
            "historical_memory",
        }
        actual = {e.value for e in AgentType}
        assert actual == expected

    def test_count(self):
        from src.shared.models import AgentType

        assert len(AgentType) == 7


class TestLLMTier:
    """LLMTier enum covers all routing tiers."""

    def test_all_tiers(self):
        from src.shared.models import LLMTier

        expected = {"critical", "standard", "routine", "vision", "free"}
        actual = {e.value for e in LLMTier}
        assert actual == expected


class TestTaskStatus:
    """TaskStatus enum covers task lifecycle."""

    def test_all_statuses(self):
        from src.shared.models import TaskStatus

        expected = {"pending", "in_progress", "completed", "failed", "cancelled"}
        actual = {e.value for e in TaskStatus}
        assert actual == expected


class TestIMDCycloneClass:
    """IMDCycloneClass enum follows IMD cyclone classification."""

    def test_all_classes(self):
        from src.shared.models import IMDCycloneClass

        expected = {"D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"}
        actual = {e.value for e in IMDCycloneClass}
        assert actual == expected

    def test_count(self):
        from src.shared.models import IMDCycloneClass

        assert len(IMDCycloneClass) == 7


class TestAlertChannel:
    """AlertChannel enum covers Indian communication channels."""

    def test_all_channels(self):
        from src.shared.models import AlertChannel

        expected = {"whatsapp", "sms", "social_media", "media_briefing", "tts_audio"}
        actual = {e.value for e in AlertChannel}
        assert actual == expected


# =============================================================================
# GeoPoint / GeoPolygon Tests
# =============================================================================


class TestGeoPoint:
    """GeoPoint validates WGS84 coordinates."""

    def test_valid_point(self):
        from src.shared.models import GeoPoint

        p = GeoPoint(latitude=28.6139, longitude=77.2090)
        assert p.latitude == 28.6139
        assert p.longitude == 77.2090

    def test_latitude_too_high(self):
        from src.shared.models import GeoPoint

        with pytest.raises(ValidationError):
            GeoPoint(latitude=91.0, longitude=77.0)

    def test_latitude_too_low(self):
        from src.shared.models import GeoPoint

        with pytest.raises(ValidationError):
            GeoPoint(latitude=-91.0, longitude=77.0)

    def test_longitude_too_high(self):
        from src.shared.models import GeoPoint

        with pytest.raises(ValidationError):
            GeoPoint(latitude=28.0, longitude=181.0)

    def test_longitude_too_low(self):
        from src.shared.models import GeoPoint

        with pytest.raises(ValidationError):
            GeoPoint(latitude=28.0, longitude=-181.0)

    def test_boundary_values(self):
        from src.shared.models import GeoPoint

        p = GeoPoint(latitude=90.0, longitude=180.0)
        assert p.latitude == 90.0
        assert p.longitude == 180.0

        p2 = GeoPoint(latitude=-90.0, longitude=-180.0)
        assert p2.latitude == -90.0
        assert p2.longitude == -180.0

    def test_json_round_trip(self):
        from src.shared.models import GeoPoint

        p = GeoPoint(latitude=20.5937, longitude=78.9629)
        data = p.model_dump()
        p2 = GeoPoint(**data)
        assert p == p2


class TestGeoPolygon:
    """GeoPolygon holds a list of GeoPoint coordinates."""

    def test_valid_polygon(self):
        from src.shared.models import GeoPoint, GeoPolygon

        coords = [
            GeoPoint(latitude=20.0, longitude=78.0),
            GeoPoint(latitude=21.0, longitude=78.0),
            GeoPoint(latitude=21.0, longitude=79.0),
            GeoPoint(latitude=20.0, longitude=78.0),
        ]
        poly = GeoPolygon(coordinates=coords)
        assert len(poly.coordinates) == 4

    def test_minimum_three_points(self):
        from src.shared.models import GeoPoint, GeoPolygon

        coords = [
            GeoPoint(latitude=20.0, longitude=78.0),
            GeoPoint(latitude=21.0, longitude=78.0),
            GeoPoint(latitude=21.0, longitude=79.0),
        ]
        poly = GeoPolygon(coordinates=coords)
        assert len(poly.coordinates) == 3

    def test_fewer_than_three_points_rejected(self):
        from src.shared.models import GeoPoint, GeoPolygon

        with pytest.raises(ValidationError):
            GeoPolygon(
                coordinates=[
                    GeoPoint(latitude=20.0, longitude=78.0),
                    GeoPoint(latitude=21.0, longitude=78.0),
                ]
            )


# =============================================================================
# Core Domain Model Tests
# =============================================================================


class TestState:
    """State model for Indian administrative states."""

    def test_valid_state(self):
        from src.shared.models import State

        s = State(
            id=1,
            name="Maharashtra",
            name_local="महाराष्ट्र",
            primary_language="Marathi",
            seismic_zone=3,
        )
        assert s.name == "Maharashtra"
        assert s.seismic_zone == 3

    def test_optional_fields_default_none(self):
        from src.shared.models import State

        s = State(id=1, name="Odisha")
        assert s.name_local is None
        assert s.primary_language is None
        assert s.seismic_zone is None

    def test_seismic_zone_valid_range(self):
        from src.shared.models import State

        # Valid: 2-6
        s = State(id=1, name="Test", seismic_zone=2)
        assert s.seismic_zone == 2
        s = State(id=2, name="Test", seismic_zone=6)
        assert s.seismic_zone == 6

    def test_seismic_zone_out_of_range(self):
        from src.shared.models import State

        with pytest.raises(ValidationError):
            State(id=1, name="Test", seismic_zone=1)
        with pytest.raises(ValidationError):
            State(id=2, name="Test", seismic_zone=7)


class TestDistrict:
    """District model for Indian administrative districts."""

    def test_valid_district(self):
        from src.shared.models import District

        d = District(
            id=1,
            state_id=1,
            name="Mumbai Suburban",
            census_2011_code="2722",
            population_2011=9356962,
            area_sq_km=446.0,
            vulnerability_score=0.75,
        )
        assert d.name == "Mumbai Suburban"
        assert d.population_2011 == 9356962

    def test_optional_fields_default_none(self):
        from src.shared.models import District

        d = District(id=1, state_id=1, name="Puri")
        assert d.census_2011_code is None
        assert d.population_2011 is None
        assert d.area_sq_km is None
        assert d.vulnerability_score is None


class TestDisaster:
    """Disaster model — the central entity."""

    def test_valid_disaster(self):
        from src.shared.models import Disaster, GeoPoint, IndiaDisasterType

        d = Disaster(
            type=IndiaDisasterType.CYCLONE,
            severity=4,
            start_time=datetime(2024, 10, 25, 6, 0, tzinfo=UTC),
            location=GeoPoint(latitude=19.0, longitude=85.0),
        )
        assert d.type == IndiaDisasterType.CYCLONE
        assert d.severity == 4
        assert d.id is not None  # auto-generated UUID

    def test_severity_out_of_range(self):
        from src.shared.models import Disaster, IndiaDisasterType

        with pytest.raises(ValidationError):
            Disaster(
                type=IndiaDisasterType.EARTHQUAKE,
                severity=0,
                start_time=datetime.now(tz=UTC),
            )
        with pytest.raises(ValidationError):
            Disaster(
                type=IndiaDisasterType.EARTHQUAKE,
                severity=6,
                start_time=datetime.now(tz=UTC),
            )

    def test_defaults(self):
        from src.shared.models import Disaster, DisasterPhase, IndiaDisasterType

        d = Disaster(
            type=IndiaDisasterType.MONSOON_FLOOD,
            severity=3,
            start_time=datetime.now(tz=UTC),
        )
        assert d.phase == DisasterPhase.PRE_EVENT
        assert d.affected_state_ids == []
        assert d.affected_district_ids == []
        assert d.metadata == {}
        assert d.location is None
        assert d.affected_area is None
        assert d.sachet_alert_id is None
        assert d.imd_classification is None

    def test_json_round_trip(self):
        from src.shared.models import Disaster, GeoPoint, IndiaDisasterType

        d = Disaster(
            type=IndiaDisasterType.CYCLONE,
            severity=4,
            start_time=datetime(2024, 10, 25, 6, 0, tzinfo=UTC),
            location=GeoPoint(latitude=19.0, longitude=85.0),
            imd_classification="VSCS",
            affected_state_ids=[1, 2],
        )
        json_str = d.model_dump_json()
        d2 = Disaster.model_validate_json(json_str)
        assert d.type == d2.type
        assert d.severity == d2.severity
        assert d.location == d2.location


class TestIMDObservation:
    """IMDObservation for weather time-series data."""

    def test_valid_observation(self):
        from src.shared.models import GeoPoint, IMDObservation

        obs = IMDObservation(
            time=datetime.now(tz=UTC),
            station_id="42182",
            location=GeoPoint(latitude=19.09, longitude=72.85),
            temperature_c=32.5,
            rainfall_mm=45.0,
            humidity_pct=85.0,
            wind_speed_kmph=60.0,
            wind_direction="NW",
            pressure_hpa=1005.0,
        )
        assert obs.station_id == "42182"
        assert obs.source == "imd_api"

    def test_optional_fields(self):
        from src.shared.models import IMDObservation

        obs = IMDObservation(time=datetime.now(tz=UTC), station_id="42182")
        assert obs.temperature_c is None
        assert obs.rainfall_mm is None
        assert obs.district_id is None


class TestCWCRiverLevel:
    """CWCRiverLevel for river gauge data."""

    def test_valid_river_level(self):
        from src.shared.models import CWCRiverLevel, GeoPoint

        rl = CWCRiverLevel(
            time=datetime.now(tz=UTC),
            station_id="MAHANADI_01",
            river_name="Mahanadi",
            state="Odisha",
            location=GeoPoint(latitude=20.46, longitude=85.88),
            water_level_m=12.5,
            danger_level_m=14.0,
            warning_level_m=13.0,
            discharge_cumecs=5000.0,
        )
        assert rl.river_name == "Mahanadi"
        assert rl.source == "cwc_guardian"


# =============================================================================
# Agent Model Tests
# =============================================================================


class TestAgentCard:
    """AgentCard describes an agent's capabilities."""

    def test_valid_agent_card(self):
        from src.shared.models import AgentCard, AgentType, LLMTier

        card = AgentCard(
            agent_id="situation-sense-01",
            agent_type=AgentType.SITUATION_SENSE,
            name="SituationSense Agent",
            description="Multi-source data fusion and situational awareness",
            capabilities=["data_fusion", "urgency_scoring", "misinformation_detection"],
            llm_tier=LLMTier.ROUTINE,
        )
        assert card.agent_type == AgentType.SITUATION_SENSE
        assert len(card.capabilities) == 3
        assert card.status == "idle"  # default


class TestAgentDecision:
    """AgentDecision tracks individual agent decisions."""

    def test_valid_decision(self):
        from src.shared.models import AgentDecision

        d = AgentDecision(
            disaster_id=uuid.uuid4(),
            agent_id="orchestrator-01",
            task_id=uuid.uuid4(),
            decision_type="evacuation_order",
            decision_payload={"districts": [1, 2], "urgency": "immediate"},
            confidence=0.85,
            reasoning="IMD Red alert + CWC danger level exceeded",
            provider="DeepSeek Reasoner",
            model="deepseek-reasoner",
            input_tokens=1500,
            output_tokens=800,
            cost_usd=0.002,
            latency_ms=3500,
        )
        assert d.confidence == 0.85
        assert d.id is not None

    def test_optional_fields(self):
        from src.shared.models import AgentDecision

        d = AgentDecision(
            agent_id="test",
            task_id=uuid.uuid4(),
            decision_type="test",
            decision_payload={},
        )
        assert d.disaster_id is None
        assert d.confidence is None
        assert d.provider is None
        assert d.cost_usd is None


class TestTaskRequest:
    """TaskRequest for inter-agent task delegation."""

    def test_valid_task(self):
        from src.shared.models import TaskRequest, TaskStatus

        t = TaskRequest(
            source_agent="orchestrator-01",
            target_agent="situation-sense-01",
            task_type="assess_situation",
            payload={"disaster_id": str(uuid.uuid4())},
            priority=4,
        )
        assert t.status == TaskStatus.PENDING
        assert t.id is not None
        assert t.priority == 4

    def test_priority_range(self):
        from src.shared.models import TaskRequest

        with pytest.raises(ValidationError):
            TaskRequest(
                source_agent="a",
                target_agent="b",
                task_type="test",
                payload={},
                priority=0,
            )
        with pytest.raises(ValidationError):
            TaskRequest(
                source_agent="a",
                target_agent="b",
                task_type="test",
                payload={},
                priority=6,
            )


class TestTaskResult:
    """TaskResult returned by agents."""

    def test_valid_result(self):
        from src.shared.models import TaskResult, TaskStatus

        r = TaskResult(
            task_id=uuid.uuid4(),
            agent_id="situation-sense-01",
            status=TaskStatus.COMPLETED,
            result_payload={"urgency": 4, "summary": "Critical flood detected"},
            confidence=0.9,
        )
        assert r.status == TaskStatus.COMPLETED
        assert r.confidence == 0.9


# =============================================================================
# Resource Model Tests
# =============================================================================


class TestResource:
    """Generic resource model."""

    def test_valid_resource(self):
        from src.shared.models import GeoPoint, Resource

        r = Resource(
            resource_type="medical_team",
            name="NDRF Team 3",
            location=GeoPoint(latitude=20.0, longitude=85.0),
            capacity=45,
            available=30,
        )
        assert r.capacity == 45
        assert r.id is not None


class TestShelter:
    """Shelter model for evacuation shelters."""

    def test_valid_shelter(self):
        from src.shared.models import GeoPoint, Shelter

        s = Shelter(
            name="Puri Cyclone Shelter #12",
            location=GeoPoint(latitude=19.8, longitude=85.83),
            capacity=500,
            current_occupancy=120,
            district_id=42,
            amenities=["water", "medical", "power_backup"],
        )
        assert s.current_occupancy == 120
        assert len(s.amenities) == 3

    def test_defaults(self):
        from src.shared.models import GeoPoint, Shelter

        s = Shelter(
            name="Test",
            location=GeoPoint(latitude=20.0, longitude=85.0),
            capacity=100,
        )
        assert s.current_occupancy == 0
        assert s.amenities == []
        assert s.district_id is None


class TestNDRFBattalion:
    """NDRFBattalion for NDRF deployment tracking."""

    def test_valid_battalion(self):
        from src.shared.models import GeoPoint, NDRFBattalion

        b = NDRFBattalion(
            name="12 Bn NDRF",
            base_location=GeoPoint(latitude=20.27, longitude=85.84),
            strength=1076,
        )
        assert b.strength == 1076
        assert b.deployed_to is None
        assert b.status == "standby"


# =============================================================================
# Alert / Communication Model Tests
# =============================================================================


class TestAlert:
    """Alert model for emergency alerts."""

    def test_valid_alert(self):
        from src.shared.models import Alert, AlertChannel

        a = Alert(
            disaster_id=uuid.uuid4(),
            severity=4,
            title="Cyclone Warning",
            message="Very Severe Cyclonic Storm approaching Odisha coast",
            language="en",
            channel=AlertChannel.WHATSAPP,
            target_audience="general_public",
            source_authority="IMD",
        )
        assert a.severity == 4
        assert a.channel == AlertChannel.WHATSAPP
        assert a.id is not None

    def test_severity_range(self):
        from src.shared.models import Alert, AlertChannel

        with pytest.raises(ValidationError):
            Alert(
                severity=0,
                title="Test",
                message="Test",
                language="en",
                channel=AlertChannel.SMS,
            )
        with pytest.raises(ValidationError):
            Alert(
                severity=6,
                title="Test",
                message="Test",
                language="en",
                channel=AlertChannel.SMS,
            )


class TestSACHETAlert:
    """SACHETAlert for NDMA CAP feed alerts."""

    def test_valid_sachet_alert(self):
        from src.shared.models import SACHETAlert

        a = SACHETAlert(
            cap_id="urn:oid:2.49.0.0.356.0.1234",
            sender="IMD",
            event_type="cyclone",
            severity="Extreme",
            urgency="Immediate",
            certainty="Observed",
            headline="Cyclone Warning for Odisha Coast",
            description="VSCS approaching Puri district",
            area_desc="Odisha, Puri district",
            onset=datetime(2024, 10, 25, 6, 0, tzinfo=UTC),
            expires=datetime(2024, 10, 27, 6, 0, tzinfo=UTC),
        )
        assert a.sender == "IMD"
        assert a.polygon is None  # optional


# =============================================================================
# Benchmark Model Tests
# =============================================================================


class TestBenchmarkScenario:
    """BenchmarkScenario for benchmark system."""

    def test_valid_scenario(self):
        from src.shared.models import BenchmarkScenario

        s = BenchmarkScenario(
            category="cyclone",
            complexity="high",
            affected_states=["Odisha", "West Bengal"],
            primary_language="Odia",
            initial_state={"wind_speed_kmph": 180},
            event_sequence=[{"t": 0, "event": "landfall"}],
            ground_truth_decisions={"evacuate": True},
            evaluation_rubric={"timeliness_weight": 0.3},
        )
        assert s.category == "cyclone"
        assert len(s.affected_states) == 2
        assert s.version == 1

    def test_complexity_validation(self):
        from src.shared.models import BenchmarkScenario

        with pytest.raises(ValidationError):
            BenchmarkScenario(
                category="cyclone",
                complexity="extreme",  # invalid
                initial_state={},
                event_sequence=[],
                ground_truth_decisions={},
                evaluation_rubric={},
            )


class TestEvaluationRun:
    """EvaluationRun tracks a single benchmark run."""

    def test_valid_run(self):
        from src.shared.models import EvaluationRun

        r = EvaluationRun(
            scenario_id=uuid.uuid4(),
            agent_config={"primary_provider": "deepseek"},
            situational_accuracy=0.85,
            decision_timeliness=0.90,
            resource_efficiency=0.75,
            coordination_quality=0.80,
            communication_score=0.88,
            aggregate_drs=0.836,
            total_tokens=15000,
            total_cost_usd=0.04,
            primary_provider="deepseek",
        )
        assert r.aggregate_drs == 0.836
        assert r.id is not None


class TestEvaluationMetrics:
    """EvaluationMetrics with computed aggregate score."""

    def test_valid_metrics(self):
        from src.shared.models import EvaluationMetrics

        m = EvaluationMetrics(
            situational_accuracy=0.85,
            decision_timeliness=0.90,
            resource_efficiency=0.75,
            coordination_quality=0.80,
            communication_score=0.88,
        )
        # aggregate_drs is computed as weighted average
        assert 0.0 <= m.aggregate_drs <= 1.0

    def test_scores_out_of_range(self):
        from src.shared.models import EvaluationMetrics

        with pytest.raises(ValidationError):
            EvaluationMetrics(
                situational_accuracy=1.5,  # out of range
                decision_timeliness=0.9,
                resource_efficiency=0.7,
                coordination_quality=0.8,
                communication_score=0.8,
            )


# =============================================================================
# LLM Router Model Tests
# =============================================================================


class TestLLMRequest:
    """LLMRequest for LLM Router calls."""

    def test_valid_request(self):
        from src.shared.models import LLMRequest, LLMTier

        req = LLMRequest(
            tier=LLMTier.CRITICAL,
            messages=[
                {"role": "system", "content": "You are a disaster response expert."},
                {"role": "user", "content": "Assess the cyclone threat."},
            ],
        )
        assert req.tier == LLMTier.CRITICAL
        assert len(req.messages) == 2
        assert req.kwargs == {}


class TestLLMResponse:
    """LLMResponse from LLM Router."""

    def test_valid_response(self):
        from src.shared.models import LLMResponse

        resp = LLMResponse(
            content="The cyclone is category 4...",
            provider="DeepSeek Reasoner",
            model="deepseek-reasoner",
            input_tokens=500,
            output_tokens=300,
            cost_usd=0.0012,
            latency_ms=3200,
        )
        assert resp.provider == "DeepSeek Reasoner"
        assert resp.cost_usd == 0.0012


# =============================================================================
# from_attributes Tests
# =============================================================================


class TestFromAttributes:
    """Test that models can be constructed from ORM-like objects."""

    def test_geopoint_from_attributes(self):
        from src.shared.models import GeoPoint

        obj = SimpleNamespace(latitude=20.0, longitude=78.0)
        p = GeoPoint.model_validate(obj, from_attributes=True)
        assert p.latitude == 20.0

    def test_disaster_from_attributes(self):
        from src.shared.models import Disaster, IndiaDisasterType

        obj = SimpleNamespace(
            id=uuid.uuid4(),
            type="cyclone",
            imd_classification="VSCS",
            severity=4,
            affected_state_ids=[1, 2],
            affected_district_ids=[10, 20],
            location=None,
            affected_area=None,
            start_time=datetime.now(tz=UTC),
            phase="pre_event",
            sachet_alert_id=None,
            metadata={},
            created_at=datetime.now(tz=UTC),
        )
        d = Disaster.model_validate(obj, from_attributes=True)
        assert d.type == IndiaDisasterType.CYCLONE
        assert d.severity == 4
