"""PredictiveRisk agent — forecasting, cascading failures, risk maps (S7.4).

Forecasts disaster evolution using IMD data, predicts India-specific cascading
failures, generates probabilistic risk maps, and retrieves historical analogies
via RAG over ChromaDB.

Runs on the **standard** tier (DeepSeek Chat, $0.28/M tokens) for reasoning tasks.

LangGraph nodes:
    ingest_data -> retrieve_historical -> forecast_risk -> predict_cascading
    -> generate_risk_map -> produce_report

Usage::

    agent = PredictiveRisk()
    await agent.start()
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.base import AgentState, BaseAgent
from src.data.ingest.embeddings import EmbeddingPipeline, SimilarityResult
from src.protocols.a2a.schemas import A2AAgentCard
from src.routing.llm_router import LLMTier
from src.shared.models import AgentType
from src.shared.telemetry import get_logger

logger = get_logger("agent.predictive_risk")

# =============================================================================
# IMD Cyclone Classification
# =============================================================================

_CYCLONE_THRESHOLDS: list[tuple[float, str]] = [
    (120, "SuCS"),   # Super Cyclonic Storm
    (90, "ESCS"),    # Extremely Severe Cyclonic Storm
    (64, "VSCS"),    # Very Severe Cyclonic Storm
    (48, "SCS"),     # Severe Cyclonic Storm
    (34, "CS"),      # Cyclonic Storm
    (28, "DD"),      # Deep Depression
    (17, "D"),       # Depression
]


def classify_cyclone(wind_speed_kt: float) -> str:
    """Map wind speed (knots) to IMD cyclone classification.

    IMD Scale:
        LOW  — < 17 kt (not classified)
        D    — 17-27 kt (Depression)
        DD   — 28-33 kt (Deep Depression)
        CS   — 34-47 kt (Cyclonic Storm)
        SCS  — 48-63 kt (Severe Cyclonic Storm)
        VSCS — 64-89 kt (Very Severe Cyclonic Storm)
        ESCS — 90-119 kt (Extremely Severe Cyclonic Storm)
        SuCS — >=120 kt (Super Cyclonic Storm)
    """
    for threshold, classification in _CYCLONE_THRESHOLDS:
        if wind_speed_kt >= threshold:
            return classification
    return "LOW"


# =============================================================================
# Cascading Failure Chains
# =============================================================================

_CASCADE_CHAINS: dict[str, list[str]] = {
    "cyclone": [
        "Cyclone landfall",
        "Storm surge and coastal flooding",
        "Dam/reservoir overtopping",
        "Downstream river flooding",
        "Power grid failure",
        "Telecom tower backup exhaustion (4-8h)",
        "Communication blackout",
        "Water treatment plant disruption",
    ],
    "flood": [
        "Riverine/urban flooding",
        "Power grid substation inundation",
        "Telecom infrastructure failure",
        "Road and rail network disruption",
        "Water supply contamination",
        "Hospital access cutoff",
    ],
    "monsoon_flood": [
        "Extreme rainfall (>200mm/24h)",
        "Urban waterlogging and river flooding",
        "Power grid failure from substation inundation",
        "Telecom backup exhaustion",
        "Road network disruption",
        "Water treatment plant failure",
        "Hospital and shelter access cutoff",
    ],
    "earthquake": [
        "Seismic ground shaking",
        "Building and infrastructure collapse",
        "Gas pipeline rupture and fire risk",
        "Power grid damage",
        "Water main breaks",
        "Road and bridge damage",
        "Aftershock-triggered landslides",
    ],
    "landslide": [
        "Slope failure and debris flow",
        "Road and rail blockage",
        "River damming (landslide dam)",
        "Dam breach flooding downstream",
        "Isolation of hill communities",
    ],
    "heatwave": [
        "Extreme temperature sustained",
        "Power grid overload from AC demand",
        "Rolling blackouts",
        "Water scarcity",
        "Heat-related medical emergencies",
    ],
    "drought": [
        "Prolonged rainfall deficit",
        "Groundwater depletion",
        "Crop failure",
        "Rural-to-urban migration pressure",
        "Water rationing in urban areas",
    ],
}

_GENERIC_CHAIN = [
    "Initial disaster impact",
    "Infrastructure damage",
    "Supply chain disruption",
    "Secondary effects on population",
]


def get_cascade_chain(disaster_type: str) -> list[str]:
    """Return expected cascading failure chain for a disaster type.

    Falls back to a generic chain for unknown disaster types.
    """
    return _CASCADE_CHAINS.get(disaster_type, _GENERIC_CHAIN)


# =============================================================================
# Predictive Risk State
# =============================================================================


class PredictiveRiskState(AgentState):
    """Extended state for PredictiveRisk agent."""

    weather_data: list[dict]
    historical_analogies: list[dict]
    forecast: dict
    cascading_failures: list[dict]
    risk_map: dict
    cyclone_tracking: dict
    time_horizons: list[str]


# =============================================================================
# PredictiveRisk Agent
# =============================================================================


class PredictiveRisk(BaseAgent):
    """Forecasting and risk prediction agent for Indian disaster scenarios.

    Predicts disaster evolution, cascading failures, generates risk maps,
    and retrieves historical analogies via RAG.
    """

    def __init__(self, *, settings=None) -> None:
        from src.shared.config import get_settings

        super().__init__(
            agent_id="predictive_risk",
            agent_type=AgentType.PREDICTIVE_RISK,
            llm_tier=LLMTier.STANDARD,
            settings=settings or get_settings(),
        )
        self._embedding_pipeline: EmbeddingPipeline | None = None

    def _get_embedding_pipeline(self) -> EmbeddingPipeline:
        if self._embedding_pipeline is None:
            self._embedding_pipeline = EmbeddingPipeline(settings=self._settings)
        return self._embedding_pipeline

    def get_system_prompt(self) -> str:
        return (
            "You are the PredictiveRisk agent for India's CRISIS-BENCH disaster "
            "response system. Your role is to forecast disaster evolution and predict "
            "cascading failures specific to Indian infrastructure.\n\n"
            "Your capabilities:\n"
            "1. Multi-horizon forecasting (1h, 6h, 24h, 72h) aligned with IMD bulletin cycles\n"
            "2. India-specific cascading failure prediction (cyclone → storm surge → "
            "dam overtopping → downstream flooding → infrastructure failure)\n"
            "3. Probabilistic risk map generation using Bhuvan boundaries + Census data\n"
            "4. Historical analogy retrieval from Indian disaster database\n"
            "5. IMD cyclone classification tracking (D → DD → CS → SCS → VSCS → ESCS → SuCS)\n\n"
            "Data sources:\n"
            "- IMD (India Meteorological Department) gridded data and real-time observations\n"
            "- NDMA SACHET CAP alerts\n"
            "- Census 2011 vulnerability data\n"
            "- Historical disaster database (ChromaDB RAG)\n\n"
            "Always output structured JSON. Prioritize official IMD data. "
            "Include confidence levels and uncertainty ranges in all forecasts."
        )

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="PredictiveRisk",
            description=(
                "Forecasting agent: disaster evolution prediction, cascading failure "
                "analysis, probabilistic risk maps, historical analogies"
            ),
            capabilities=[
                "forecasting",
                "cascading_failure_prediction",
                "risk_mapping",
                "historical_analogy",
                "cyclone_tracking",
            ],
            llm_tier=self.llm_tier,
        )

    def build_graph(self) -> StateGraph:
        graph = StateGraph(PredictiveRiskState)

        graph.add_node("ingest_data", self._ingest_data)
        graph.add_node("retrieve_historical", self._retrieve_historical)
        graph.add_node("forecast_risk", self._forecast_risk)
        graph.add_node("predict_cascading", self._predict_cascading)
        graph.add_node("generate_risk_map", self._generate_risk_map)
        graph.add_node("produce_report", self._produce_report)

        graph.set_entry_point("ingest_data")
        graph.add_edge("ingest_data", "retrieve_historical")
        graph.add_edge("retrieve_historical", "forecast_risk")
        graph.add_edge("forecast_risk", "predict_cascading")
        graph.add_edge("predict_cascading", "generate_risk_map")
        graph.add_edge("generate_risk_map", "produce_report")
        graph.add_edge("produce_report", END)

        return graph

    # -----------------------------------------------------------------
    # Graph Nodes
    # -----------------------------------------------------------------

    async def _ingest_data(self, state: PredictiveRiskState) -> dict[str, Any]:
        """Extract weather data, disaster context, and cyclone info from task."""
        task = state.get("task", {})
        weather_data = task.get("weather_data", [])
        cyclone_data = task.get("cyclone_data")
        disaster_type = task.get("disaster_type", "unknown")

        cyclone_tracking: dict[str, Any] = {}
        if cyclone_data:
            wind_speed = cyclone_data.get("wind_speed_kt", 0)
            cyclone_tracking = {
                "name": cyclone_data.get("name", "Unknown"),
                "current_classification": classify_cyclone(wind_speed),
                "wind_speed_kt": wind_speed,
                "latitude": cyclone_data.get("latitude"),
                "longitude": cyclone_data.get("longitude"),
                "movement_direction": cyclone_data.get("movement_direction"),
                "landfall_expected": cyclone_data.get("landfall_expected", False),
            }

        time_horizons = ["1h", "6h", "24h", "72h"]

        logger.info(
            "data_ingested",
            weather_count=len(weather_data),
            disaster_type=disaster_type,
            has_cyclone=bool(cyclone_data),
            trace_id=state.get("trace_id", ""),
        )

        return {
            "weather_data": weather_data,
            "cyclone_tracking": cyclone_tracking,
            "time_horizons": time_horizons,
            "metadata": {
                **state.get("metadata", {}),
                "disaster_type": disaster_type,
                "affected_state": task.get("affected_state", ""),
                "affected_districts": task.get("affected_districts", []),
            },
        }

    async def _retrieve_historical(self, state: PredictiveRiskState) -> dict[str, Any]:
        """Retrieve historical analogies from ChromaDB via RAG."""
        metadata = state.get("metadata", {})
        disaster_type = metadata.get("disaster_type", "disaster")
        affected_state = metadata.get("affected_state", "India")

        query = f"{disaster_type} in {affected_state}"

        try:
            pipeline = self._get_embedding_pipeline()
            results: list[SimilarityResult] = await pipeline.query_similar(
                "historical_events",
                query,
                top_k=5,
            )
            analogies = [
                {
                    "text": r.text,
                    "score": r.score,
                    "metadata": r.metadata,
                    "document_id": r.document_id,
                }
                for r in results
            ]
        except Exception as exc:
            logger.warning(
                "historical_retrieval_failed",
                error=str(exc),
                trace_id=state.get("trace_id", ""),
            )
            analogies = []

        logger.info(
            "historical_retrieved",
            count=len(analogies),
            trace_id=state.get("trace_id", ""),
        )

        return {"historical_analogies": analogies}

    async def _forecast_risk(self, state: PredictiveRiskState) -> dict[str, Any]:
        """Generate multi-horizon risk forecast via LLM."""
        weather_data = state.get("weather_data", [])
        analogies = state.get("historical_analogies", [])
        metadata = state.get("metadata", {})
        cyclone_tracking = state.get("cyclone_tracking", {})

        analogy_text = ""
        if analogies:
            analogy_text = "\n".join(
                f"- {a.get('text', '')[:200]} (similarity: {a.get('score', 0):.2f})"
                for a in analogies[:3]
            )

        prompt = (
            "Generate a multi-horizon disaster forecast for the following scenario. "
            "Output ONLY valid JSON with keys: disaster_type, time_horizons "
            "(1h/6h/24h/72h each with risk_level and rainfall_forecast_mm), "
            "cyclone_progression (list or null), confidence (0-1).\n\n"
            f"Disaster type: {metadata.get('disaster_type', 'unknown')}\n"
            f"Affected area: {metadata.get('affected_state', 'India')}, "
            f"districts: {metadata.get('affected_districts', [])}\n"
            f"Current weather data: {json.dumps(weather_data[:5])}\n"
        )
        if cyclone_tracking:
            prompt += f"Cyclone tracking: {json.dumps(cyclone_tracking)}\n"
        if analogy_text:
            prompt += f"\nHistorical analogies:\n{analogy_text}\n"

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            forecast = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            forecast = {
                "disaster_type": metadata.get("disaster_type", "unknown"),
                "time_horizons": {
                    h: {"risk_level": "unknown", "rainfall_forecast_mm": 0}
                    for h in ["1h", "6h", "24h", "72h"]
                },
                "cyclone_progression": None,
                "confidence": 0.2,
            }

        return {"forecast": forecast}

    async def _predict_cascading(self, state: PredictiveRiskState) -> dict[str, Any]:
        """Predict cascading failure chains via LLM."""
        metadata = state.get("metadata", {})
        disaster_type = metadata.get("disaster_type", "unknown")
        forecast = state.get("forecast", {})
        weather_data = state.get("weather_data", [])

        expected_chain = get_cascade_chain(disaster_type)

        prompt = (
            "Predict cascading failures for this disaster scenario. "
            "Output ONLY valid JSON with key 'chains' containing a list of objects "
            "with keys: trigger, sequence (list of {event, probability, eta_hours}).\n\n"
            f"Disaster type: {disaster_type}\n"
            f"Expected cascade pattern: {json.dumps(expected_chain)}\n"
            f"Current forecast: {json.dumps(forecast)}\n"
            f"Weather data: {json.dumps(weather_data[:3])}\n"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            result = json.loads(resp.content)
            chains = result.get("chains", [])
        except (json.JSONDecodeError, TypeError):
            chains = []

        return {"cascading_failures": chains}

    async def _generate_risk_map(self, state: PredictiveRiskState) -> dict[str, Any]:
        """Generate probabilistic GeoJSON risk map via LLM."""
        metadata = state.get("metadata", {})
        forecast = state.get("forecast", {})
        weather_data = state.get("weather_data", [])
        cascading = state.get("cascading_failures", [])

        prompt = (
            "Generate a GeoJSON FeatureCollection risk map for the current disaster. "
            "Each Feature should represent an affected area with properties including "
            "name, risk_level (low/medium/high/critical), population_at_risk, "
            "vulnerability_index (0-1). Output ONLY valid GeoJSON.\n\n"
            f"Affected area: {metadata.get('affected_state', 'India')}, "
            f"districts: {metadata.get('affected_districts', [])}\n"
            f"Forecast: {json.dumps(forecast)}\n"
            f"Weather: {json.dumps(weather_data[:3])}\n"
            f"Cascading failures: {json.dumps(cascading[:3])}\n"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            risk_map = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            risk_map = {"type": "FeatureCollection", "features": []}

        return {"risk_map": risk_map}

    async def _produce_report(self, state: PredictiveRiskState) -> dict[str, Any]:
        """Compile final predictive risk report."""
        forecast = state.get("forecast", {})
        cascading = state.get("cascading_failures", [])
        risk_map = state.get("risk_map", {})
        analogies = state.get("historical_analogies", [])
        weather_data = state.get("weather_data", [])
        cyclone_tracking = state.get("cyclone_tracking", {})

        # Confidence based on data quality
        data_score = 0.0
        if weather_data:
            data_score += 0.3
        if analogies:
            avg_similarity = sum(a.get("score", 0) for a in analogies) / max(len(analogies), 1)
            data_score += 0.2 * avg_similarity
        if forecast.get("confidence"):
            data_score += 0.3 * forecast["confidence"]
        if cascading:
            data_score += 0.1
        if risk_map.get("features"):
            data_score += 0.1

        confidence = min(0.95, max(0.1, data_score))

        report = {
            "type": "predictive_risk_report",
            "forecast": forecast,
            "cascading_failures": cascading,
            "risk_map": risk_map,
            "historical_analogies": analogies,
            "cyclone_tracking": cyclone_tracking,
            "confidence": confidence,
        }

        logger.info(
            "report_produced",
            confidence=round(confidence, 2),
            cascade_count=len(cascading),
            analogy_count=len(analogies),
            trace_id=state.get("trace_id", ""),
        )

        return {
            "confidence": confidence,
            "artifacts": [report],
            "reasoning": json.dumps(forecast),
        }


__all__ = [
    "PredictiveRisk",
    "PredictiveRiskState",
    "classify_cyclone",
    "get_cascade_chain",
]
