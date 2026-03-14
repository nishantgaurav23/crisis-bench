# CRISIS-BENCH (India)

Multi-agent disaster response coordination system (7 LLM agents + Orchestrator) with a self-evolving 100-scenario India-specific benchmark. Hybrid LLM strategy: Chinese APIs (DeepSeek/Qwen at $0.04-$0.50/M tokens) as primary + Ollama local as fallback. Total cost: $3-8/month.

## Key Rules

- **NEVER** write code without a spec — always run `/create-spec` first
- **NEVER** skip TDD — write tests FIRST, then implement (Red → Green → Refactor)
- **NEVER** hardcode API keys or secrets — all config via `.env` files (see `.env.example`)
- **NEVER** hit real external APIs in tests — mock all external services
- **NEVER** depend on paid services for core functionality — system must work on free tiers only (Groq + Gemini Flash + Ollama)
- **ALWAYS** use `async def` / `await` — the entire system is async
- **ALWAYS** update `roadmap.md` status after completing a spec
- **ALWAYS** run `/explain-spec` after completing a spec to document its purpose and connections
- **ALWAYS** validate Pydantic models at system boundaries
- **ALWAYS** use `ruff` for linting (line-length: 100)
- **ALWAYS** route LLM calls through the LLM Router — never call providers directly
- **ALWAYS** design for graceful degradation (DeepSeek API → Qwen → Groq free → Ollama local)
- **ALWAYS** use India-specific data sources (IMD, SACHET, Bhuvan) as primary; international sources supplement

## Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Backend | Python 3.11+ / FastAPI / uvicorn | Free |
| Agent Framework | LangGraph 0.2+ | Free (MIT) |
| Agent Protocols | Google A2A (agent-to-agent), Anthropic MCP (agent-to-tool) | Free |
| LLM (Critical) | DeepSeek V3.2 Reasoner API | $0.50/$2.18 per M tokens |
| LLM (Standard) | DeepSeek V3.2 Chat API | $0.28/$0.42 per M tokens |
| LLM (Routine) | Qwen3.5-Flash via Alibaba | ~$0.04/$0.40 per M tokens |
| LLM (Vision) | Qwen3-VL-Flash via Alibaba | ~$0.10/M tokens |
| LLM (Free overflow) | Groq (Llama-3.1-70B) | $0 (30 req/min) |
| LLM (Free overflow 2) | Gemini 2.0 Flash via Google | $0 (15 req/min) |
| LLM (Local fallback) | Ollama: Qwen2.5-7B-Q4 | $0 |
| Embeddings | nomic-embed-text via Ollama (768 dims) | $0 |
| Translation | Bhashini API (free) + IndicTrans2 (local) | $0 |
| Crisis NLP | CrisisBERT + IndicBERT (local) | $0 |
| Event Bus | Redis Streams (same instance as cache) | Free (BSD) |
| Vector DB | ChromaDB (Docker, self-hosted) | Free (Apache 2.0) |
| Graph DB | Neo4j Community Edition (Docker) | Free (GPLv3) |
| Spatial DB | PostgreSQL 16 + PostGIS 3.4 (Docker) | Free |
| Cache | Redis 7.x (same instance as event bus) | Free (BSD) |
| Dashboard | Next.js 14+ / TypeScript | Free (MIT) |
| Mapping | Leaflet + OpenStreetMap tiles | Free |
| Optimization | Google OR-Tools + PuLP | Free (Apache 2.0) |
| Deployment | Docker Compose (local + Oracle Cloud Always Free) | $0 |
| CI/CD | GitHub Actions (free for public repos) | Free |
| Monitoring | Prometheus + Grafana (Docker) | Free (Apache 2.0) |
| LLM Observability | Langfuse self-hosted (Docker) | Free (MIT) |
| Testing | pytest + pytest-asyncio + Hypothesis | Free |
| Linting | ruff (line-length: 100) | Free |

## Project Structure

```
crisis-bench/
├── roadmap.md                    # Master development plan (source of truth)
├── design.md                     # Architecture document (v3)
├── requirements.md               # Requirements specification (v3)
├── research_brief.md             # Research context and positioning
├── pyproject.toml
├── docker-compose.yml            # ONE COMMAND TO START EVERYTHING
├── docker-compose.cpu.yml        # CPU-only override (no GPU)
├── Makefile                      # make setup, make run, make benchmark
├── .env.example                  # Template for API keys + config
├── .claude/
│   ├── CLAUDE.md                 # This file
│   └── commands/                 # Spec-driven dev commands
├── docker/                       # Dockerfiles
│   ├── Dockerfile.agent
│   ├── Dockerfile.mcp
│   ├── Dockerfile.benchmark
│   └── Dockerfile.api
├── specs/                        # Spec folders (55 specs across 9 phases)
│   └── spec-S{x}.{y}-{slug}/
│       ├── spec.md               # Requirements + TDD notes
│       ├── checklist.md          # Implementation tracker
│       └── explanation.md        # Post-completion: why, what, how, connections
├── src/
│   ├── agents/                   # 7 specialist agents + base
│   │   ├── base.py               # BaseAgent (LangGraph + LLM Router + Langfuse)
│   │   ├── orchestrator.py       # Tier: critical (DeepSeek Reasoner)
│   │   ├── situation_sense.py    # Tier: routine (Qwen Flash) + vision
│   │   ├── predictive_risk.py    # Tier: standard (DeepSeek Chat)
│   │   ├── resource_allocation.py # Tier: standard (DeepSeek Chat) + OR-Tools
│   │   ├── community_comms.py    # Tier: routine (Qwen Flash) + Bhashini
│   │   ├── infra_status.py       # Tier: routine (Qwen Flash) + Neo4j
│   │   └── historical_memory.py  # Tier: standard (DeepSeek Chat) + RAG
│   ├── protocols/
│   │   ├── a2a/                  # A2A over Redis Streams
│   │   │   ├── schemas.py
│   │   │   ├── server.py
│   │   │   └── client.py
│   │   └── mcp/                  # MCP servers for Indian data APIs
│   │       ├── base.py           # MCP server base framework
│   │       ├── imd_server.py     # IMD Weather (India)
│   │       ├── sachet_server.py  # NDMA SACHET CAP Feed
│   │       ├── usgs_server.py    # USGS Earthquakes
│   │       ├── osm_server.py     # OpenStreetMap Overpass
│   │       ├── bhuvan_server.py  # ISRO Bhuvan Satellite
│   │       └── firms_server.py   # NASA FIRMS Fire
│   ├── benchmark/
│   │   ├── models.py             # Scenario data models
│   │   ├── scenario_manager.py
│   │   ├── scenario_runner.py    # Simulated clock
│   │   ├── evaluation_engine.py  # LLM-as-judge (DeepSeek Reasoner)
│   │   ├── self_evolving.py
│   │   └── metrics/
│   │       ├── situational.py    # Situational Accuracy
│   │       ├── timeliness.py     # Decision Timeliness
│   │       ├── resource.py       # Resource Efficiency
│   │       ├── coordination.py   # Coordination Quality
│   │       ├── communication.py  # Communication Appropriateness
│   │       └── aggregate.py      # Aggregate DRS
│   ├── data/
│   │   ├── ingest/               # IMD, NDMA, Census, Bhuvan, OSM
│   │   │   ├── embeddings.py     # ChromaDB setup + embedding pipeline
│   │   │   ├── ndma_pdfs.py      # NDMA guidelines ingestion
│   │   │   ├── infra_graph.py    # Neo4j infrastructure graph
│   │   │   ├── imd.py            # IMD historical gridded data
│   │   │   └── census.py         # Census 2011 + admin boundaries
│   │   ├── synthetic/            # Scenario + social media generators
│   │   │   ├── scenario_gen.py
│   │   │   └── social_media_gen.py
│   │   └── processing/           # NLP + satellite processing
│   ├── routing/
│   │   ├── llm_router.py         # 5-tier routing across 8 providers
│   │   ├── urgency_classifier.py # Maps disaster data to LLM tier
│   │   └── cost_tracker.py       # Per-provider cost tracking
│   ├── caching/
│   │   ├── plan_cache.py         # ChromaDB-based plan caching
│   │   └── plan_adapter.py       # Adapt cached plans to new scenarios
│   ├── api/
│   │   ├── main.py               # FastAPI (localhost:8000)
│   │   ├── routes/               # REST endpoints
│   │   └── websocket.py          # Real-time updates to dashboard
│   └── shared/
│       ├── config.py             # Pydantic Settings (reads .env)
│       ├── redis_utils.py        # Redis Streams + cache
│       ├── db.py                 # PostgreSQL/PostGIS async connection
│       ├── errors.py             # CrisisError hierarchy
│       ├── telemetry.py          # structlog + Prometheus + Langfuse
│       └── models.py             # Pydantic domain schemas
├── dashboard/                    # Next.js (localhost:3000)
│   └── src/components/
│       ├── GeoMap.tsx            # Leaflet + OpenStreetMap (India-centered)
│       ├── AgentFlow.tsx         # Agent status + communication flow
│       ├── MetricsPanel.tsx      # Token usage, cost, latency
│       └── Timeline.tsx          # Event timeline
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/dashboards/
├── scripts/
│   ├── init_db.sql              # PostgreSQL/PostGIS schema
│   ├── setup.sh                 # Full setup script
│   ├── ingest_data.py
│   ├── generate_scenarios.py
│   └── run_benchmark.py
├── tests/
│   ├── unit/                    # test_{module}.py files
│   ├── integration/             # End-to-end agent pipeline tests
│   └── conftest.py              # Shared fixtures
├── data/                        # .gitignored (large files, ~17GB)
└── .github/workflows/
    ├── ci.yml                   # Lint + test on PR
    └── benchmark_regression.yml # Benchmark score regression detection
```

## Spec Folder Convention

```
specs/spec-S{phase}.{number}-{slug}/
  spec.md        <- Requirements, outcomes, TDD notes
  checklist.md   <- Phase-by-phase implementation tracker
  explanation.md <- Post-completion: why, what, how, connections
```

## Spec-Driven Development Commands

| Command | Input | Action |
|---------|-------|--------|
| `/create-spec` | spec ID + slug | Create spec.md + checklist.md from roadmap |
| `/implement-spec` | spec ID | TDD implementation (Red -> Green -> Refactor) |
| `/verify-spec` | spec ID | Post-implementation audit (tests, lint, outcomes) |
| `/check-spec-deps` | spec ID | Verify all prerequisite specs are done |
| `/start-spec-dev` | spec ID | Full workflow: check deps -> create spec -> implement -> verify -> explain |
| `/explain-spec` | spec ID | Generate explanation.md: why, what, how, connections |

## Status Flow

```
pending -> spec-written -> done
```

## Code Standards

### Async
- All I/O functions must be `async def`
- Use `asyncio.gather()` for parallel operations
- Never use blocking calls in async context

### LLM Calls
- All LLM calls go through `LLMRouter.call(tier, messages)` — never call providers directly
- Use `AsyncOpenAI` with provider-specific `base_url` + `api_key`
- Tiers: critical (DeepSeek Reasoner), standard (DeepSeek Chat), routine (Qwen Flash), vision (Qwen VL), free (Groq/Ollama)
- Embeddings: `nomic-embed-text` via Ollama (local, free)
- Fallback chain: paid API -> free API -> local Ollama (automatic)
- Log all LLM calls via Langfuse (self-hosted)
- Track cost per call in cost_tracker

### Validation
- Pydantic `BaseModel` for all data schemas
- Validate at API boundaries, trust internal code
- Use `Field(...)` with descriptions for API-facing models

### Error Handling
- Custom exception hierarchy rooted at `CrisisError`
- Structured error responses with trace IDs
- Circuit breaker pattern for inter-agent calls (60s default timeout)
- Graceful degradation when provider fails (automatic failover)

### Logging
- JSON structured logging via `structlog`
- Required fields: `timestamp`, `agent_id`, `trace_id`, `severity`, `message`
- Never log PII or full LLM responses (use content hashes)

### Testing
- pytest + pytest-asyncio for all tests
- Hypothesis for property-based tests on A2A serialization
- Mock all external APIs (IMD, USGS, SACHET, Bhuvan, FIRMS, LLM providers)
- Target >80% code coverage per spec
- Test files: `tests/unit/test_{module}.py`

### Dependencies
- Pin all dependencies in `pyproject.toml`
- Use `uv` for dependency management
- Separate dev/test dependencies
- All deps must be free / open-source (no commercial licenses)

## Docker Services (all via docker-compose.yml)

| Service | Port | Image |
|---------|------|-------|
| PostgreSQL/PostGIS | 5432 | postgis/postgis:16-3.4 |
| Redis | 6379 | redis:7-alpine |
| Neo4j Community | 7474, 7687 | neo4j:5-community |
| ChromaDB | 8100 | chromadb/chroma:latest |
| Langfuse | 4000 | langfuse/langfuse:2 |
| Prometheus | 9090 | prom/prometheus:latest |
| Grafana | 4001 | grafana/grafana:latest |
| API Gateway | 8000 | custom (Dockerfile.api) |
| Dashboard | 3000 | custom (dashboard/Dockerfile) |
| Ollama | 11434 | **runs on host** (not Docker, for GPU access) |

## LLM Router Tiers

| Tier | Primary Provider | Fallback Chain | Use Case |
|------|-----------------|----------------|----------|
| critical | DeepSeek Reasoner ($0.50/M) | Kimi K2.5 -> Groq free -> Ollama | Evacuation decisions, cascading failure analysis |
| standard | DeepSeek Chat ($0.28/M) | Qwen Flash -> Groq free -> Ollama | Situation reports, infrastructure analysis |
| routine | Qwen Flash ($0.04/M) | Groq free -> Gemini free -> Ollama | Classification, summarization, monitoring |
| vision | Qwen VL Flash ($0.10/M) | Ollama LLaVA | Satellite imagery analysis |

## Indian Data Sources (MCP Servers)

| MCP Server | API | Auth | Data |
|-----------|-----|------|------|
| mcp-imd | IMD Weather APIs | IP whitelist (free) | District warnings, rainfall, cyclone, AWS |
| mcp-sachet | NDMA SACHET CAP Feed | None (public RSS) | All-hazard alerts from 7 agencies + 36 states |
| mcp-usgs | USGS FDSNWS | None | Earthquakes covering India region |
| mcp-osm | OpenStreetMap Overpass | None | Infrastructure, hospitals, roads, shelters |
| mcp-bhuvan | ISRO Bhuvan REST + OGC | Free registration | Satellite layers, village geocoding, flood maps |
| mcp-firms | NASA FIRMS | Free API key | Active fire detection, thermal anomalies |
