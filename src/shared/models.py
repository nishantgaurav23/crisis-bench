"""Pydantic domain models for CRISIS-BENCH.

Shared data schemas used across agents, API, benchmark, and data layers.
All models use ConfigDict(from_attributes=True) for ORM compatibility.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

# =============================================================================
# Enums
# =============================================================================


class IndiaDisasterType(str, Enum):
    """Matches PostgreSQL india_disaster_type enum."""

    MONSOON_FLOOD = "monsoon_flood"
    CYCLONE = "cyclone"
    URBAN_WATERLOGGING = "urban_waterlogging"
    EARTHQUAKE = "earthquake"
    HEATWAVE = "heatwave"
    LANDSLIDE = "landslide"
    INDUSTRIAL_ACCIDENT = "industrial_accident"
    TSUNAMI = "tsunami"
    DROUGHT = "drought"
    GLACIAL_LAKE_OUTBURST = "glacial_lake_outburst"


class DisasterPhase(str, Enum):
    """Disaster lifecycle phases."""

    PRE_EVENT = "pre_event"
    ACTIVE_RESPONSE = "active_response"
    RECOVERY = "recovery"
    POST_EVENT = "post_event"


class AgentType(str, Enum):
    """The 7 specialist agents."""

    ORCHESTRATOR = "orchestrator"
    SITUATION_SENSE = "situation_sense"
    PREDICTIVE_RISK = "predictive_risk"
    RESOURCE_ALLOCATION = "resource_allocation"
    COMMUNITY_COMMS = "community_comms"
    INFRA_STATUS = "infra_status"
    HISTORICAL_MEMORY = "historical_memory"


class LLMTier(str, Enum):
    """LLM routing tiers."""

    CRITICAL = "critical"
    STANDARD = "standard"
    ROUTINE = "routine"
    VISION = "vision"
    FREE = "free"


class TaskStatus(str, Enum):
    """Task lifecycle statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IMDCycloneClass(str, Enum):
    """IMD tropical cyclone classification for North Indian Ocean."""

    D = "D"  # Depression
    DD = "DD"  # Deep Depression
    CS = "CS"  # Cyclonic Storm
    SCS = "SCS"  # Severe Cyclonic Storm
    VSCS = "VSCS"  # Very Severe Cyclonic Storm
    ESCS = "ESCS"  # Extremely Severe Cyclonic Storm
    SuCS = "SuCS"  # Super Cyclonic Storm


class AlertChannel(str, Enum):
    """Indian communication channels for emergency alerts."""

    WHATSAPP = "whatsapp"
    SMS = "sms"
    SOCIAL_MEDIA = "social_media"
    MEDIA_BRIEFING = "media_briefing"
    TTS_AUDIO = "tts_audio"


# =============================================================================
# Geo Models
# =============================================================================


class GeoPoint(BaseModel):
    """WGS84 coordinate point (SRID 4326)."""

    model_config = ConfigDict(from_attributes=True)

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class GeoPolygon(BaseModel):
    """Polygon defined by a list of GeoPoint coordinates."""

    model_config = ConfigDict(from_attributes=True)

    coordinates: list[GeoPoint] = Field(..., min_length=3)


# =============================================================================
# Core Domain Models
# =============================================================================


class State(BaseModel):
    """Indian administrative state/UT."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_local: str | None = None
    primary_language: str | None = None
    seismic_zone: int | None = Field(default=None, ge=2, le=6)


class District(BaseModel):
    """Indian administrative district."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    state_id: int
    name: str
    census_2011_code: str | None = None
    population_2011: int | None = None
    area_sq_km: float | None = None
    vulnerability_score: float | None = None


class Disaster(BaseModel):
    """Central disaster entity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: IndiaDisasterType
    imd_classification: str | None = None
    severity: int = Field(..., ge=1, le=5)
    affected_state_ids: list[int] = Field(default_factory=list)
    affected_district_ids: list[int] = Field(default_factory=list)
    location: GeoPoint | None = None
    affected_area: GeoPolygon | None = None
    start_time: datetime
    phase: DisasterPhase = DisasterPhase.PRE_EVENT
    sachet_alert_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class IMDObservation(BaseModel):
    """IMD weather observation time-series entry."""

    model_config = ConfigDict(from_attributes=True)

    time: datetime
    station_id: str
    district_id: int | None = None
    location: GeoPoint | None = None
    temperature_c: float | None = None
    rainfall_mm: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmph: float | None = None
    wind_direction: str | None = None
    pressure_hpa: float | None = None
    source: str = "imd_api"


class CWCRiverLevel(BaseModel):
    """CWC river gauge measurement."""

    model_config = ConfigDict(from_attributes=True)

    time: datetime
    station_id: str
    river_name: str | None = None
    state: str | None = None
    location: GeoPoint | None = None
    water_level_m: float | None = None
    danger_level_m: float | None = None
    warning_level_m: float | None = None
    discharge_cumecs: float | None = None
    source: str = "cwc_guardian"


# =============================================================================
# Agent Models
# =============================================================================


class AgentCard(BaseModel):
    """Describes an agent's identity and capabilities."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    agent_type: AgentType
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    status: str = "idle"
    llm_tier: LLMTier = LLMTier.ROUTINE


class AgentDecision(BaseModel):
    """Tracks an individual agent decision."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    disaster_id: uuid.UUID | None = None
    agent_id: str
    task_id: uuid.UUID
    decision_type: str
    decision_payload: dict[str, Any]
    confidence: float | None = None
    reasoning: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class TaskRequest(BaseModel):
    """Inter-agent task delegation request."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_agent: str
    target_agent: str
    disaster_id: uuid.UUID | None = None
    task_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=3, ge=1, le=5)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    deadline: datetime | None = None


class TaskResult(BaseModel):
    """Result returned by an agent for a task."""

    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    agent_id: str
    status: TaskStatus
    result_payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    error_message: str | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


# =============================================================================
# Resource Models
# =============================================================================


class Resource(BaseModel):
    """Generic resource tracked for allocation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    resource_type: str
    name: str
    location: GeoPoint
    capacity: int
    available: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class Shelter(BaseModel):
    """Evacuation shelter."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    location: GeoPoint
    capacity: int
    current_occupancy: int = 0
    district_id: int | None = None
    amenities: list[str] = Field(default_factory=list)


class NDRFBattalion(BaseModel):
    """NDRF battalion deployment tracking."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    base_location: GeoPoint
    strength: int
    deployed_to: str | None = None
    status: str = "standby"


# =============================================================================
# Alert / Communication Models
# =============================================================================


class Alert(BaseModel):
    """Emergency alert for public communication."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    disaster_id: uuid.UUID | None = None
    severity: int = Field(..., ge=1, le=5)
    title: str
    message: str
    language: str
    channel: AlertChannel
    target_audience: str | None = None
    source_authority: str | None = None
    issued_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    expires_at: datetime | None = None


class SACHETAlert(BaseModel):
    """NDMA SACHET CAP feed alert."""

    model_config = ConfigDict(from_attributes=True)

    cap_id: str
    sender: str
    event_type: str
    severity: str
    urgency: str
    certainty: str
    headline: str
    description: str
    area_desc: str
    polygon: GeoPolygon | None = None
    onset: datetime
    expires: datetime


# =============================================================================
# Benchmark Models
# =============================================================================


class BenchmarkScenario(BaseModel):
    """A single benchmark disaster scenario."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    category: str
    complexity: str = Field(..., pattern=r"^(low|medium|high)$")
    affected_states: list[str] = Field(default_factory=list)
    primary_language: str | None = None
    initial_state: dict[str, Any]
    event_sequence: list[dict[str, Any]]
    ground_truth_decisions: dict[str, Any]
    evaluation_rubric: dict[str, Any]
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class EvaluationRun(BaseModel):
    """Results of a single benchmark evaluation run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    scenario_id: uuid.UUID
    agent_config: dict[str, Any]
    situational_accuracy: float | None = None
    decision_timeliness: float | None = None
    resource_efficiency: float | None = None
    coordination_quality: float | None = None
    communication_score: float | None = None
    aggregate_drs: float | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    primary_provider: str | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class EvaluationMetrics(BaseModel):
    """Evaluation metrics with computed aggregate DRS."""

    model_config = ConfigDict(from_attributes=True)

    situational_accuracy: float = Field(..., ge=0.0, le=1.0)
    decision_timeliness: float = Field(..., ge=0.0, le=1.0)
    resource_efficiency: float = Field(..., ge=0.0, le=1.0)
    coordination_quality: float = Field(..., ge=0.0, le=1.0)
    communication_score: float = Field(..., ge=0.0, le=1.0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def aggregate_drs(self) -> float:
        """Weighted average of all 5 dimensions.

        Default weights: SA=0.25, DT=0.20, RE=0.20, CQ=0.15, CA=0.20
        """
        return (
            self.situational_accuracy * 0.25
            + self.decision_timeliness * 0.20
            + self.resource_efficiency * 0.20
            + self.coordination_quality * 0.15
            + self.communication_score * 0.20
        )


# =============================================================================
# LLM Router Models
# =============================================================================


class LLMRequest(BaseModel):
    """Request to the LLM Router."""

    model_config = ConfigDict(from_attributes=True)

    tier: LLMTier
    messages: list[dict[str, str]]
    kwargs: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Response from the LLM Router."""

    model_config = ConfigDict(from_attributes=True)

    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "IndiaDisasterType",
    "DisasterPhase",
    "AgentType",
    "LLMTier",
    "TaskStatus",
    "IMDCycloneClass",
    "AlertChannel",
    # Geo
    "GeoPoint",
    "GeoPolygon",
    # Core
    "State",
    "District",
    "Disaster",
    "IMDObservation",
    "CWCRiverLevel",
    # Agent
    "AgentCard",
    "AgentDecision",
    "TaskRequest",
    "TaskResult",
    # Resource
    "Resource",
    "Shelter",
    "NDRFBattalion",
    # Alert
    "Alert",
    "SACHETAlert",
    # Benchmark
    "BenchmarkScenario",
    "EvaluationRun",
    "EvaluationMetrics",
    # LLM
    "LLMRequest",
    "LLMResponse",
]
