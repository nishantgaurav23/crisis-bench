# Spec S2.7 — Urgency Classifier

**Status**: spec-written
**Location**: `src/routing/urgency_classifier.py`
**Depends On**: S2.6 (LLM Router)
**Phase**: 2 — Shared Infrastructure

---

## 1. Purpose

Maps disaster data to an urgency level (1–5) which determines the LLM tier used by the router. This is the bridge between raw disaster signals (IMD warnings, earthquake magnitude, flood levels, cyclone classification) and the LLM Router's tier system. Without it, every call would need a manually-assigned tier.

## 2. Requirements

### FR-002.5: Urgency Scoring
- Assign urgency scores (1–5) based on:
  - **IMD warning color codes**: Green (1) → Yellow (2) → Orange (3–4) → Red (5)
  - **Earthquake magnitude** (Richter): <4.0 (1) → 4.0-4.9 (2) → 5.0-5.9 (3) → 6.0-6.9 (4) → ≥7.0 (5)
  - **IMD cyclone classification**: D/DD (2) → CS (3) → SCS/VSCS (4) → ESCS/SuCS (5)
  - **CWC river level status**: normal (1) → warning (3) → danger (4) → extreme danger (5)
  - **Disaster type defaults**: each `IndiaDisasterType` has a base urgency
  - **Disaster phase escalation**: active_response adds +1, pre_event is base
  - **Population factor**: high population (>1M affected) adds +1

### Tier Mapping
| Urgency | LLM Tier | When |
|---------|----------|------|
| 5 | critical | Red alert, ≥7.0 earthquake, ESCS/SuCS cyclone |
| 4 | critical | Orange alert (high), 6.0-6.9 earthquake, VSCS |
| 3 | standard | Orange alert (low), 5.0-5.9 earthquake, CS |
| 2 | routine | Yellow alert, 4.0-4.9 earthquake, D/DD |
| 1 | routine | Green alert, minor events |

## 3. Interface

```python
class UrgencyClassifier:
    """Classifies disaster urgency (1-5) and maps to LLM tier."""

    def classify(self, data: DisasterData) -> UrgencyResult:
        """Classify urgency from disaster data. Pure function, no I/O."""
        ...

    def urgency_to_tier(self, urgency: int) -> LLMTier:
        """Map urgency score to LLM routing tier."""
        ...
```

### Input Model: `DisasterData`
```python
class DisasterData(BaseModel):
    disaster_type: IndiaDisasterType
    phase: DisasterPhase = DisasterPhase.PRE_EVENT
    imd_color_code: IMDColorCode | None = None
    cyclone_class: IMDCycloneClass | None = None
    earthquake_magnitude: float | None = None
    river_level_status: RiverLevelStatus | None = None
    affected_population: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Output Model: `UrgencyResult`
```python
class UrgencyResult(BaseModel):
    urgency: int = Field(..., ge=1, le=5)
    tier: LLMTier
    factors: list[str]  # Human-readable explanation of contributing factors
    raw_scores: dict[str, int]  # Individual signal scores before aggregation
```

## 4. Design Decisions

- **Pure function, no async**: Classification is deterministic math — no I/O, no LLM calls. Sync is simpler.
- **Max-of-signals aggregation**: Take the maximum of all available signal scores. A Red IMD alert with a 4.0 earthquake = urgency 5 (Red dominates).
- **Phase escalation capped at 5**: active_response adds +1 but never exceeds 5.
- **Population factor**: >1M affected adds +1, capped at 5.
- **No LLM calls**: This is a rule-based classifier. LLM-based classification would be circular (need to classify urgency to pick the LLM tier to classify urgency).

## 5. Enums to Add

```python
class IMDColorCode(str, Enum):
    GREEN = "green"    # No warning
    YELLOW = "yellow"  # Watch
    ORANGE = "orange"  # Alert
    RED = "red"        # Warning (severe)

class RiverLevelStatus(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    DANGER = "danger"
    EXTREME_DANGER = "extreme_danger"
```

## 6. TDD Notes

### Test Categories
1. **IMD color code mapping**: Each color → correct urgency
2. **Earthquake magnitude mapping**: Magnitude ranges → correct urgency
3. **Cyclone classification mapping**: Each IMD class → correct urgency
4. **River level mapping**: Each status → correct urgency
5. **Multi-signal aggregation**: Multiple signals → max wins
6. **Phase escalation**: active_response adds +1
7. **Population factor**: >1M adds +1
8. **Tier mapping**: urgency 1-5 → correct LLMTier
9. **Edge cases**: no signals (use disaster type default), all None, boundary values
10. **Pydantic validation**: Invalid urgency values rejected

### Test File
`tests/unit/test_urgency_classifier.py`
