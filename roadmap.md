# CRISIS-BENCH: Master Development Roadmap

**Version**: 3.0 (India-First, Open-Source + Budget Chinese API Edition)
**Author**: Nishant Gaurav
**Created**: 2026-03-14
**Methodology**: Spec-Driven Development with TDD (Red → Green → Refactor)

---

## Tech Stack Rationale

| Layer | Choice | Why This? | Alternatives Considered | Trade-off |
|-------|--------|-----------|------------------------|-----------|
| **Backend** | Python 3.11+ / FastAPI | Async-native, Pydantic integration, fastest Python web framework | Django (too heavy), Flask (no async) | Smaller ecosystem than Django but perfect for async microservices |
| **Agent Framework** | LangGraph 0.2+ | State machine + cycles for multi-agent; MIT licensed | CrewAI (less control), AutoGen (MSFT lock-in), raw asyncio (too low-level) | Steeper learning curve but most flexible for complex agent graphs |
| **LLM (Critical)** | DeepSeek V3.2 Reasoner API ($0.50/M) | 10x cheaper than GPT-4o, OpenAI-compatible, 90% cache discount | GPT-4o ($5/M), Claude ($3/M) | Chinese API = potential latency from India, but 10x cost savings |
| **LLM (Standard)** | DeepSeek V3.2 Chat ($0.28/M) | Best quality/cost ratio for reasoning tasks | Qwen3-Max ($0.20-1.20/M), Kimi K2.5 ($0.45/M) | Slightly more expensive than Qwen but better reasoning |
| **LLM (Routine)** | Qwen3.5-Flash ($0.04/M) | Cheapest non-free option, excellent for classification | Gemini Flash ($0.10/M), local Ollama ($0) | API dependency, but 10x better quality than local 7B |
| **LLM (Free fallback)** | Groq Llama-70B (30 rpm) | Full 70B quality at zero cost | Gemini free (15 rpm), Ollama local | Rate limited, but free 70B is unbeatable for overflow |
| **LLM (Local)** | Ollama Qwen2.5-7B | Offline capability, no API dependency | llama.cpp (lower-level), vLLM (needs GPU) | Slow on CPU (~8 tok/s) but always available |
| **LLM (Vision)** | Qwen3-VL-Flash ($0.10/M) | Only vision model at <$0.50/M | GPT-4V ($10/M), local LLaVA | API-dependent for vision, but 100x cheaper |
| **Event Bus** | Redis Streams | Same instance for cache + pub/sub, simple | Kafka (overkill for single machine), RabbitMQ (extra service) | No persistence guarantees like Kafka, but perfect for single-machine |
| **Vector DB** | ChromaDB | Simplest self-hosted, adequate for ~50K chunks | Qdrant (heavier), Pinecone (paid), Weaviate (complex) | Limited scalability, but sufficient for our dataset |
| **Graph DB** | Neo4j Community | Cypher queries for infrastructure graphs, free | ArangoDB (multi-model), NetworkX (in-memory only) | GPLv3 license, but Community Edition is free |
| **Spatial DB** | PostgreSQL 16 + PostGIS 3.4 | Industry standard for geospatial, free | MongoDB geospatial (less capable), SpatiaLite (limited) | Heavier setup, but most capable spatial queries |
| **Mapping** | Leaflet + OpenStreetMap | No API key needed, excellent India coverage | Mapbox (paid after quota), Google Maps (expensive) | Less polished than Mapbox, but completely free |
| **Agent Protocol (A2A)** | Google A2A over Redis Streams | Standard agent-to-agent protocol | Custom protocol (maintenance burden) | Newer standard, less community tooling |
| **Agent Protocol (MCP)** | Anthropic MCP | Standard agent-to-tool protocol | Custom REST wrappers (no standard) | Still evolving, but best available standard |
| **Translation** | Bhashini API + IndicTrans2 | Free govt API for 22 Indian languages + MIT local model | Google Translate ($20/M chars), Azure Translate | Bhashini quality varies, but free + covers all 22 scheduled languages |
| **Crisis NLP** | CrisisBERT + IndicBERT | Pre-trained for crisis tweets, Indian language support | Fine-tuned BERT (training cost), GPT classification (expensive) | Domain-specific = better accuracy for crisis text |
| **Optimization** | Google OR-Tools + PuLP | Free LP/MIP solver, Apache 2.0 | Gurobi (commercial), CPLEX (commercial) | Slower than commercial solvers, but free and adequate |
| **Monitoring** | Prometheus + Grafana | Industry standard, both free | DataDog (expensive), New Relic (expensive) | Self-hosted = maintenance burden, but $0 cost |
| **LLM Observability** | Langfuse self-hosted | Full LLM tracing, MIT licensed | LangSmith (LangChain lock-in), Helicone (paid) | Self-hosted = maintenance, but full data ownership |

---

## Cost Estimate

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| Docker services (local) | $0 | All self-hosted |
| Ollama local inference | $0 | Embeddings + fallback |
| DeepSeek API (dev) | $2-5 | Primary reasoning |
| Qwen API (routine + vision) | $1-3 | Flash + VL |
| Groq API | $0 | Free tier overflow |
| Bhashini API | $0 | Free govt API |
| Oracle Cloud (demo) | $0 | Always Free tier |
| GitHub Actions | $0 | Public repo |
| **Total** | **$3-8/month** | Full benchmark: $3-8 one-time |

---

## Phases Overview

| Phase | Name | Specs | Key Output | Weeks |
|-------|------|-------|------------|-------|
| **1** | Project Bootstrap | S1.1 – S1.5 | Project skeleton, Docker, config, DB schema, Makefile | 1 |
| **2** | Shared Infrastructure | S2.1 – S2.8 | Models, DB connections, Redis, LLM Router, telemetry | 1-2 |
| **3** | API + Dashboard MVP | S3.1 – S3.7 | FastAPI gateway, WebSocket, Next.js with India map | 2-3 |
| **4** | Communication Protocols | S4.1 – S4.4 | A2A schemas/server/client, MCP base framework | 3-4 |
| **5** | MCP Data Servers | S5.1 – S5.6 | IMD, SACHET, USGS, OSM, Bhuvan, FIRMS servers | 4-5 |
| **6** | Data Pipeline | S6.1 – S6.7 | ChromaDB embeddings, Neo4j graph, data ingestion, synthetic gen | 5-6 |
| **7** | Agent System | S7.1 – S7.9 | All 7 agents + orchestrator + integration test | 6-8 |
| **8** | Benchmark System | S8.1 – S8.11 | 100 scenarios, 5 evaluation metrics, self-evolving gen | 8-10 |
| **9** | Optimization & Polish | S9.1 – S9.6 | Plan caching, full dashboard, observability, CI/CD, deploy | 10-12 |

---

## Phase 1: Project Bootstrap

> **Goal**: A working project skeleton where `docker-compose up` starts all infrastructure services.
> **Learning**: Python project setup, Docker Compose orchestration, environment configuration.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S1.1 | `specs/spec-S1.1-project-structure/` | — | `pyproject.toml`, `.gitignore`, `.env.example` | Project structure + dependency declaration | Pin all deps, uv for management, ruff config | done |
| S1.2 | `specs/spec-S1.2-docker-compose/` | S1.1 | `docker-compose.yml`, `docker-compose.cpu.yml` | Docker Compose for all services | PostgreSQL+PostGIS, Redis, Neo4j, ChromaDB, Langfuse, Prometheus, Grafana | done |
| S1.3 | `specs/spec-S1.3-env-config/` | S1.1 | `src/shared/config.py` | Pydantic Settings config | Reads .env, validates all config, typed access | done |
| S1.4 | `specs/spec-S1.4-db-schema/` | S1.2 | `scripts/init_db.sql` | PostgreSQL/PostGIS schema | Indian admin boundaries, disasters, IMD observations, CWC river levels, agent decisions, benchmark tables | done |
| S1.5 | `specs/spec-S1.5-makefile/` | S1.2 | `Makefile` | Make targets | setup, run, test, lint, benchmark, clean | done |

### Interview Q&A — Phase 1

**Q: Why use `pyproject.toml` instead of `setup.py` + `requirements.txt`?**
A: `pyproject.toml` (PEP 621) is the modern Python standard. It combines project metadata, dependencies, tool configs (ruff, pytest) in one file. `setup.py` is legacy — it executes arbitrary code during install (security risk). `requirements.txt` lacks metadata and version pinning semantics.

**Q: Why Docker Compose instead of Kubernetes?**
A: For a single-machine development setup, Kubernetes is massive overkill — it adds a control plane, etcd, kubelet, container runtime abstraction. Docker Compose gives declarative multi-service orchestration with one YAML file. We can migrate to K8s later if needed, but the 80/20 rule says Compose handles our use case perfectly.

**Q: Why PostGIS instead of just PostgreSQL with lat/lng columns?**
A: PostGIS adds spatial indexing (R-tree via GiST), spatial queries (`ST_Contains`, `ST_Distance`, `ST_Within`), geometry types, and coordinate reference systems. Without it, "find all shelters within 5km of this flood zone" requires loading all shelters into memory and computing haversine distances. PostGIS does it in a single indexed SQL query.

**Q: Why Pydantic Settings instead of `os.getenv()` calls everywhere?**
A: Type safety + validation at startup. If `REDIS_URL` is missing or `POSTGRES_PORT` is not an integer, Pydantic fails fast at import time with a clear error — not at 3am when the Redis connection first fires. It also provides IDE autocomplete and a single source of truth for all config.

---

## Phase 2: Shared Infrastructure

> **Goal**: All building blocks that every other module depends on — models, DB connections, Redis, LLM routing, error handling, telemetry.
> **Learning**: Async database patterns, Redis Streams, LLM routing/failover, structured logging, circuit breakers.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S2.1 | `specs/spec-S2.1-domain-models/` | S1.3 | `src/shared/models.py` | Pydantic domain models | Disaster, Agent, Task, Alert, Resource, BenchmarkScenario, EvaluationRun models | done |
| S2.2 | `specs/spec-S2.2-db-connection/` | S1.3, S1.4 | `src/shared/db.py` | Async PostgreSQL/PostGIS connection | asyncpg pool, health check, spatial queries helper | done |
| S2.3 | `specs/spec-S2.3-redis-utils/` | S1.3 | `src/shared/redis_utils.py` | Redis Streams + cache utilities | Publish/subscribe, consumer groups, cache get/set with TTL | done |
| S2.4 | `specs/spec-S2.4-error-handling/` | — | `src/shared/errors.py` | CrisisError exception hierarchy | Base error, AgentError, RouterError, DataError, TimeoutError with trace IDs | pending |
| S2.5 | `specs/spec-S2.5-telemetry/` | S1.3 | `src/shared/telemetry.py` | Structured logging + metrics | structlog JSON, Prometheus counters/histograms, Langfuse trace stubs | pending |
| S2.6 | `specs/spec-S2.6-llm-router/` | S1.3, S2.4, S2.5 | `src/routing/llm_router.py` | LLM Router — 5-tier multi-provider routing | DeepSeek/Qwen/Kimi/Groq/Ollama failover, cost tracking, rate limiting | pending |
| S2.7 | `specs/spec-S2.7-urgency-classifier/` | S2.6 | `src/routing/urgency_classifier.py` | Urgency classification (1-5) | Maps disaster data to LLM tier, uses IMD warning color codes | pending |
| S2.8 | `specs/spec-S2.8-cost-tracker/` | S2.6 | `src/routing/cost_tracker.py` | Per-provider cost tracking | Tracks tokens, cost, latency per provider; budget alerts | pending |

### Interview Q&A — Phase 2

**Q: Why use `asyncpg` instead of SQLAlchemy?**
A: `asyncpg` is a pure-async PostgreSQL driver — 3-5x faster than SQLAlchemy's async mode because it speaks the PostgreSQL binary protocol directly (no ORM overhead). For a real-time disaster system, every millisecond matters. We use raw SQL with parameterized queries — we don't need an ORM for this use case.

**Q: Explain the LLM Router pattern. Why not just call one API?**
A: The LLM Router is essentially a **strategy pattern with failover chain**. Different tasks have different quality/cost/latency requirements. A critical evacuation decision needs DeepSeek Reasoner ($0.50/M) — it's worth the cost for chain-of-thought reasoning. But classifying a social media post? Qwen Flash at $0.04/M or free Groq is sufficient. The router also handles: (1) automatic failover when a provider is down, (2) rate limit backoff, (3) cost tracking per call. Every agent calls `router.call(tier, messages)` — zero coupling to any specific provider.

**Q: What is a circuit breaker and why use it here?**
A: A circuit breaker prevents cascading failures. If Agent A calls Agent B and B is hung, without a circuit breaker A also hangs, then anything calling A hangs — domino effect. The circuit breaker tracks failures: after N failures in M seconds, it "opens" (rejects calls immediately) for a cooldown period, then "half-opens" (allows one test call). In our system: 60s timeout, 3 failures → circuit opens for 30s. This prevents one slow LLM provider from blocking the entire agent pipeline.

**Q: Why Redis Streams instead of Redis Pub/Sub?**
A: Redis Pub/Sub is fire-and-forget — if a subscriber is down when a message is published, it's lost forever. Redis Streams add: (1) message persistence (messages stay until acknowledged), (2) consumer groups (multiple consumers can share work), (3) message replay (re-read from any point), (4) at-least-once delivery with `XACK`. For disaster response, losing a critical alert because an agent was restarting is unacceptable.

**Q: Why structlog instead of Python's logging module?**
A: `structlog` produces structured JSON logs — each log entry is a JSON object with typed fields (`timestamp`, `agent_id`, `trace_id`, `severity`). Standard Python logging produces unstructured text strings that are painful to parse programmatically. With JSON logs, you can pipe directly to Grafana/Loki/ELK for dashboards, alerts, and search. In production, structured logs are the difference between "grep for errors" and "query for all errors from agent X in the last 5 minutes with trace ID Y."

---

## Phase 3: API + Dashboard MVP

> **Goal**: A working FastAPI gateway and Next.js dashboard with an India-centered map. Start testing visually as development continues.
> **Learning**: FastAPI patterns, WebSocket real-time updates, Next.js, Leaflet mapping, OpenStreetMap.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S3.1 | `specs/spec-S3.1-api-gateway/` | S1.3, S2.1, S2.4 | `src/api/main.py`, `src/api/routes/` | FastAPI gateway | Health, disaster CRUD, agent status endpoints, CORS | pending |
| S3.2 | `specs/spec-S3.2-websocket/` | S3.1, S2.3 | `src/api/websocket.py` | WebSocket server | Real-time agent updates, disaster events to dashboard | pending |
| S3.3 | `specs/spec-S3.3-dashboard-setup/` | — | `dashboard/` | Next.js 14 project setup | TypeScript, Tailwind CSS, project scaffold, Dockerfile | pending |
| S3.4 | `specs/spec-S3.4-geo-map/` | S3.3 | `dashboard/src/components/GeoMap.tsx` | India-centered Leaflet map | State/district boundaries, disaster markers, flood zones | pending |
| S3.5 | `specs/spec-S3.5-agent-panel/` | S3.3 | `dashboard/src/components/AgentFlow.tsx` | Agent status + communication flow | 7 agents displayed, message flow visualization, mock data initially | pending |
| S3.6 | `specs/spec-S3.6-metrics-panel/` | S3.3 | `dashboard/src/components/MetricsPanel.tsx` | Token usage + cost tracking panel | Per-provider breakdown, budget gauge, latency charts | pending |
| S3.7 | `specs/spec-S3.7-timeline/` | S3.3 | `dashboard/src/components/Timeline.tsx` | Event timeline component | Chronological agent decisions, disaster phase transitions | pending |

### Interview Q&A — Phase 3

**Q: Why FastAPI over Django REST Framework?**
A: FastAPI is async-native (built on Starlette + uvicorn), has automatic OpenAPI docs, and uses Pydantic for request/response validation. Django REST is synchronous by default — you'd need `django-channels` for WebSocket and `asgiref` wrappers for async views. For a real-time system pushing WebSocket updates every 60 seconds, FastAPI's native async is the natural choice. Trade-off: Django has admin panel, ORM migrations, and a larger ecosystem — but we don't need those.

**Q: Why WebSocket instead of Server-Sent Events (SSE)?**
A: WebSocket is bidirectional — the dashboard can send commands back (e.g., "pause scenario", "override agent decision"). SSE is server → client only. Also, WebSocket has better browser support for reconnection patterns and binary data. Trade-off: SSE is simpler and works through HTTP proxies more easily, but we need the bidirectional capability.

**Q: Why Leaflet + OpenStreetMap instead of Google Maps or Mapbox?**
A: Zero cost, zero API key, zero rate limits. OpenStreetMap has excellent India coverage (metro areas are very detailed, rural is improving). Google Maps charges after 28K loads/month. Mapbox charges after 50K loads/month. For a self-hosted open-source project, free tiles with no API key is non-negotiable. Trade-off: OSM tiles are less polished than Mapbox's vector tiles, but Leaflet + OpenStreetMap is the standard for open-source mapping.

**Q: Why build the dashboard early (Phase 3) instead of at the end?**
A: Visual feedback accelerates development. When you can see agent status, disaster locations, and message flows on a map, you catch integration bugs faster than reading JSON logs. The dashboard also serves as a **living specification** — stakeholders (or interviewers) can see progress immediately. Building it last means you debug everything blind for 8 weeks.

---

## Phase 4: Communication Protocols

> **Goal**: A2A (agent-to-agent) and MCP (agent-to-tool) protocol implementations over Redis Streams.
> **Learning**: Protocol design, message serialization, pub/sub patterns, consumer groups.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S4.1 | `specs/spec-S4.1-a2a-schemas/` | S2.1, S2.4 | `src/protocols/a2a/schemas.py` | A2A message schemas | Task, TaskResult, AgentCard, Artifact models per A2A spec | pending |
| S4.2 | `specs/spec-S4.2-a2a-server/` | S4.1, S2.3 | `src/protocols/a2a/server.py` | A2A server (Redis Streams publisher) | Publish tasks, broadcast updates, consumer group management | pending |
| S4.3 | `specs/spec-S4.3-a2a-client/` | S4.1, S2.3 | `src/protocols/a2a/client.py` | A2A client (Redis Streams subscriber) | Subscribe to tasks, send responses, acknowledgment | pending |
| S4.4 | `specs/spec-S4.4-mcp-base/` | S1.3 | `src/protocols/mcp/base.py` | MCP server base framework | Common MCP server setup, tool registration, error handling | pending |

### Interview Q&A — Phase 4

**Q: What is the A2A (Agent-to-Agent) protocol?**
A: A2A is Google's open standard for agent interoperability. It defines: (1) AgentCard — a JSON manifest describing an agent's capabilities, (2) Task — a unit of work with input/output artifacts, (3) Streaming — real-time updates during task execution. Think of it like HTTP but for agents — a common language so agents from different frameworks can communicate. We implement it over Redis Streams instead of HTTP because all agents are on the same machine.

**Q: What is MCP (Model Context Protocol)?**
A: MCP is Anthropic's protocol for connecting LLMs to external tools/data sources. An MCP server exposes "tools" (functions the LLM can call) and "resources" (data the LLM can read). In our system, each MCP server wraps an external API (IMD weather, USGS earthquakes, etc.) and exposes it as tools the agents can invoke. The agent's LLM decides which tool to call based on the task — the MCP server handles the actual API call.

**Q: Why implement A2A over Redis Streams instead of HTTP?**
A: All agents run on the same machine. HTTP would add unnecessary serialization, TCP handshake, and port management overhead. Redis Streams gives us: (1) sub-millisecond message delivery on localhost, (2) built-in message persistence and replay, (3) consumer groups for load balancing, (4) the same Redis instance we already use for caching. Trade-off: not compatible with remote A2A servers, but we can add an HTTP transport later.

---

## Phase 5: MCP Data Servers

> **Goal**: MCP servers wrapping all Indian government and public data APIs.
> **Learning**: External API integration, XML/JSON parsing, rate limiting, MCP protocol implementation.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S5.1 | `specs/spec-S5.1-mcp-imd/` | S4.4 | `src/protocols/mcp/imd_server.py` | IMD Weather MCP server | District warnings, rainfall, cyclone info, AWS data | pending |
| S5.2 | `specs/spec-S5.2-mcp-sachet/` | S4.4 | `src/protocols/mcp/sachet_server.py` | SACHET CAP Feed MCP server | Parse CAP XML, filter by state/hazard type, 7 agency alerts | pending |
| S5.3 | `specs/spec-S5.3-mcp-usgs/` | S4.4 | `src/protocols/mcp/usgs_server.py` | USGS Earthquake MCP server | FDSNWS API, India region filter, magnitude/depth queries | pending |
| S5.4 | `specs/spec-S5.4-mcp-osm/` | S4.4 | `src/protocols/mcp/osm_server.py` | OpenStreetMap Overpass MCP server | Infrastructure queries, hospital/shelter/road data for India | pending |
| S5.5 | `specs/spec-S5.5-mcp-bhuvan/` | S4.4 | `src/protocols/mcp/bhuvan_server.py` | ISRO Bhuvan MCP server | Village geocoding, satellite layers, LULC, NDEM flood maps | pending |
| S5.6 | `specs/spec-S5.6-mcp-firms/` | S4.4 | `src/protocols/mcp/firms_server.py` | NASA FIRMS Fire MCP server | Active fire data, India region, thermal anomalies | pending |

### Interview Q&A — Phase 5

**Q: What is the SACHET CAP feed and why is it the "single most important integration point"?**
A: SACHET is NDMA's Common Alerting Protocol feed (`sachet.ndma.gov.in/CapFeed`). It aggregates warnings from 7 national agencies (IMD, CWC, INCOIS, NCS, GSI, DGRE, FSI) + all 36 state disaster authorities into a single RSS feed using the international CAP v1.2 XML standard. Instead of integrating with each agency separately, we parse one feed and get all Indian hazard alerts. It has delivered 68.99 billion SMS alerts — this is the production alert system for India.

**Q: How do you handle the fact that CWC has no public API?**
A: The GUARDIAN framework (published in Nature Scientific Data, 2024) demonstrated how to extract sub-daily river discharge data from CWC's portal for 210+ stations. We follow the same approach — web scraping with polite rate limiting, data normalization, and storage in PostgreSQL with PostGIS. The processed data is available at indiariverflow.com. This is a common pattern in government data integration — screen scraping behind a clean API interface.

**Q: Why wrap external APIs in MCP servers instead of calling them directly from agents?**
A: Separation of concerns. (1) Each MCP server handles auth, rate limiting, error handling, and response normalization for its API — agents don't need to know about IP whitelisting for IMD or token refresh for Bhuvan. (2) We can mock the entire MCP server in tests without mocking HTTP calls. (3) The MCP protocol provides a standard tool interface — the agent's LLM can discover available tools at runtime. (4) We can swap the underlying API without changing agent code.

---

## Phase 6: Data Pipeline

> **Goal**: Embed NDMA guidelines into ChromaDB, build Neo4j infrastructure graph, ingest historical data, generate synthetic scenarios.
> **Learning**: RAG pipeline, vector embeddings, graph databases, synthetic data generation, PDF processing.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S6.1 | `specs/spec-S6.1-chromadb-setup/` | S1.3 | `src/data/ingest/embeddings.py` | ChromaDB connection + embedding pipeline | Collection creation, nomic-embed-text via Ollama, chunking strategy | pending |
| S6.2 | `specs/spec-S6.2-ndma-ingestion/` | S6.1 | `src/data/ingest/ndma_pdfs.py` | NDMA guidelines + SOPs ingestion | PDF parsing, chunking, embedding 30+ documents into ChromaDB | pending |
| S6.3 | `specs/spec-S6.3-neo4j-graph/` | S1.3 | `src/data/ingest/infra_graph.py` | Neo4j infrastructure dependency graph | Power → telecom → water → hospital dependency chains for major Indian cities | pending |
| S6.4 | `specs/spec-S6.4-imd-historical/` | S2.2 | `src/data/ingest/imd.py` | IMD gridded data ingestion | imdlib download, NetCDF → PostgreSQL, rainfall + temperature time-series | pending |
| S6.5 | `specs/spec-S6.5-admin-boundaries/` | S2.2 | `src/data/ingest/census.py` | Census 2011 + administrative boundaries | States, districts, population, geometry into PostGIS | pending |
| S6.6 | `specs/spec-S6.6-scenario-generator/` | S2.6, S6.2, S6.5 | `src/data/synthetic/scenario_gen.py` | Synthetic scenario generator | LLM-powered scenario creation from historical templates, 7 disaster categories | pending |
| S6.7 | `specs/spec-S6.7-social-media-gen/` | S2.6 | `src/data/synthetic/social_media_gen.py` | Synthetic social media generator | Hindi/English/regional crisis tweets, 40/30/30 language mix | pending |

### Interview Q&A — Phase 6

**Q: Explain your RAG (Retrieval-Augmented Generation) pipeline.**
A: RAG = retrieve relevant documents, then generate answers grounded in those documents. Our pipeline: (1) **Chunk** — split NDMA PDFs into 512-token overlapping chunks, (2) **Embed** — convert chunks to 768-dim vectors using `nomic-embed-text` via Ollama (free, local), (3) **Store** — persist vectors + text in ChromaDB, (4) **Retrieve** — at query time, embed the query, find top-K similar chunks via cosine similarity, (5) **Generate** — pass retrieved chunks as context to the LLM with the original query. This grounds the LLM's response in actual NDMA guidelines rather than hallucinated procedures.

**Q: Why nomic-embed-text instead of OpenAI's ada-002?**
A: (1) Free — runs locally via Ollama, zero API cost. (2) 768 dimensions (vs ada's 1536) — smaller vectors = faster similarity search + less storage. (3) Quality — nomic-embed-text scores competitively on MTEB benchmarks, especially for retrieval tasks. (4) Privacy — document embeddings never leave the machine. Trade-off: slightly lower quality than ada-002 on some benchmarks, but the cost difference ($0 vs $0.10/M tokens) makes it the obvious choice.

**Q: How does the infrastructure dependency graph in Neo4j work?**
A: We model infrastructure as a directed acyclic graph where edges represent dependencies. Example: `Hospital -[:DEPENDS_ON]-> PowerGrid -[:POWERS]-> TelecomTower`. When a cyclone knocks out a power grid, we traverse the graph to find all downstream impacts: which hospitals lose power, which telecom towers exhaust backup batteries (cascading timeline), which water treatment plants stop. Cypher query: `MATCH (p:PowerGrid {status:'down'})-[:POWERS*]->(n) RETURN n` finds all affected nodes in one query. This is why a graph DB beats relational — multi-hop dependency traversal is O(path_length) in Neo4j vs O(n*joins) in SQL.

---

## Phase 7: Agent System

> **Goal**: All 7 specialist agents + orchestrator implemented as LangGraph state machines, communicating via A2A over Redis Streams.
> **Learning**: LangGraph state machines, multi-agent orchestration, prompt engineering, agent specialization.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S7.1 | `specs/spec-S7.1-base-agent/` | S2.6, S4.2, S4.3, S2.5 | `src/agents/base.py` | BaseAgent (LangGraph + LLM Router) | State machine, A2A integration, Langfuse tracing, health check | pending |
| S7.2 | `specs/spec-S7.2-orchestrator/` | S7.1 | `src/agents/orchestrator.py` | Orchestrator agent | Mission decomposition, agent activation, synthesis, budget management, loop detection | pending |
| S7.3 | `specs/spec-S7.3-situation-sense/` | S7.1, S5.1, S5.2 | `src/agents/situation_sense.py` | SituationSense agent | Multi-source data fusion, GeoJSON updates, urgency scoring, misinformation detection | pending |
| S7.4 | `specs/spec-S7.4-predictive-risk/` | S7.1, S6.1, S6.4 | `src/agents/predictive_risk.py` | PredictiveRisk agent | Forecasting, cascading failures, risk maps, historical analogies, IMD classification tracking | pending |
| S7.5 | `specs/spec-S7.5-resource-allocation/` | S7.1, S6.5 | `src/agents/resource_allocation.py` | ResourceAllocation agent | OR-Tools optimization, NDRF/SDRF deployment, shelter matching, rolling re-optimization | pending |
| S7.6 | `specs/spec-S7.6-community-comms/` | S7.1 | `src/agents/community_comms.py` | CommunityComms agent | Multilingual alerts (9 languages), channel formatting, misinformation countering, Bhashini TTS | pending |
| S7.7 | `specs/spec-S7.7-infra-status/` | S7.1, S6.3 | `src/agents/infra_status.py` | InfraStatus agent | Infrastructure tracking, cascading failure prediction, restoration timelines, priority framework | pending |
| S7.8 | `specs/spec-S7.8-historical-memory/` | S7.1, S6.1, S6.2 | `src/agents/historical_memory.py` | HistoricalMemory agent | RAG over NDMA docs, historical disaster retrieval, post-event learning ingestion | pending |
| S7.9 | `specs/spec-S7.9-agent-integration/` | S7.2-S7.8, S3.2 | `tests/integration/test_agent_pipeline.py` | End-to-end agent pipeline integration test | SACHET alert → all agents → bilingual briefing within 45s, WebSocket dashboard update | pending |

### Interview Q&A — Phase 7

**Q: Why LangGraph instead of a simple async task queue?**
A: LangGraph models each agent as a **state machine with typed state**. This gives us: (1) Explicit states and transitions — you can visualize the agent's decision flow, (2) Conditional edges — route to different nodes based on state (e.g., urgency > 4 → escalate), (3) Cycles — agents can loop back for iterative refinement (with our 120s loop detection), (4) Persistence — state can be checkpointed to PostgreSQL for crash recovery, (5) Human-in-the-loop — insert approval gates at any transition. A simple task queue gives you "fire and forget" — LangGraph gives you a debuggable, observable decision pipeline.

**Q: How does the Orchestrator prevent infinite loops between agents?**
A: Three mechanisms: (1) **120-second global timeout** — if a task isn't resolved in 120s, the Orchestrator kills it and escalates. (2) **Message deduplication** — each A2A message has a unique ID; if an agent receives a message it already processed, it drops it. (3) **Depth counter** — each task carries a depth counter that increments on delegation; at depth > 5, the Orchestrator refuses further delegation and synthesizes whatever partial results exist.

**Q: How does the ResourceAllocation agent use OR-Tools?**
A: OR-Tools solves constrained optimization problems. Example: "Given 12 NDRF battalions, 50 shelters with varying capacity, 200K displaced people in 30 districts, and damaged roads making some routes unavailable — minimize total evacuation time while ensuring no shelter exceeds 90% capacity." This is a Vehicle Routing Problem (VRP) variant. We formulate it as a MIP (Mixed Integer Program) in OR-Tools, with constraints for shelter capacity, travel time, road damage, and resource availability. The LLM generates the constraint formulation from natural language; OR-Tools solves the math.

**Q: Why separate agents instead of one monolithic LLM with a long prompt?**
A: (1) **Specialization** — each agent has a focused system prompt and domain knowledge. A 7-agent system with 500-token prompts each is cheaper and more effective than one agent with a 3500-token prompt. (2) **Parallel execution** — SituationSense and InfraStatus can run concurrently while ResourceAllocation waits for their outputs. (3) **Independent scaling** — if PredictiveRisk needs a stronger model, we upgrade just that agent's tier. (4) **Fault isolation** — if CommunityComms crashes, other agents continue. (5) **Testability** — each agent can be unit tested in isolation.

---

## Phase 8: Benchmark System

> **Goal**: 100 India-specific disaster scenarios, 5 evaluation dimensions, self-evolving generator, baseline results.
> **Learning**: Benchmark design, LLM-as-judge evaluation, metrics engineering, contamination detection.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S8.1 | `specs/spec-S8.1-scenario-models/` | S2.1, S2.2 | `src/benchmark/models.py` | Scenario data models + storage | BenchmarkScenario, EventSequence, GroundTruth Pydantic models + DB CRUD | pending |
| S8.2 | `specs/spec-S8.2-scenario-manager/` | S8.1 | `src/benchmark/scenario_manager.py` | Scenario manager | CRUD, category filtering, complexity levels, version tracking | pending |
| S8.3 | `specs/spec-S8.3-scenario-runner/` | S8.2, S7.9 | `src/benchmark/scenario_runner.py` | Scenario runner with simulated clock | Deterministic replay, configurable acceleration (5x), event injection | pending |
| S8.4 | `specs/spec-S8.4-evaluation-engine/` | S8.3, S2.6 | `src/benchmark/evaluation_engine.py` | Evaluation engine (LLM-as-judge) | DeepSeek Reasoner as judge, structured scoring rubric, multi-dimensional | pending |
| S8.5 | `specs/spec-S8.5-metric-situational/` | S8.4 | `src/benchmark/metrics/situational.py` | Metric: Situational Accuracy | Precision/recall/F1 against IMD/CWC ground truth bulletins | pending |
| S8.6 | `specs/spec-S8.6-metric-timeliness/` | S8.4 | `src/benchmark/metrics/timeliness.py` | Metric: Decision Timeliness | Measured against NDMA SOP time windows | pending |
| S8.7 | `specs/spec-S8.7-metric-resource/` | S8.4 | `src/benchmark/metrics/resource.py` | Metric: Resource Efficiency | Optimality gap vs OR-Tools baseline | pending |
| S8.8 | `specs/spec-S8.8-metric-coordination/` | S8.4 | `src/benchmark/metrics/coordination.py` | Metric: Coordination Quality | Inter-agent information sharing, milestone KPIs | pending |
| S8.9 | `specs/spec-S8.9-metric-communication/` | S8.4 | `src/benchmark/metrics/communication.py` | Metric: Communication Appropriateness | LLM-as-judge for multilingual quality + NDMA guideline adherence | pending |
| S8.10 | `specs/spec-S8.10-aggregate-drs/` | S8.5-S8.9 | `src/benchmark/metrics/aggregate.py` | Aggregate Disaster Response Score (DRS) | Weighted combination, configurable weights, pass@k reliability | pending |
| S8.11 | `specs/spec-S8.11-self-evolving/` | S8.2, S6.6 | `src/benchmark/self_evolving.py` | Self-evolving benchmark generator | Auto-generate from historical data, contamination detection, perturbation ops | pending |

### Interview Q&A — Phase 8

**Q: What is "LLM-as-judge" evaluation and why use it?**
A: LLM-as-judge uses a strong LLM (DeepSeek Reasoner) to evaluate the outputs of other LLMs against a rubric. For example: "Given this cyclone scenario and NDMA guidelines, rate this evacuation plan on a 1-5 scale for timeliness, completeness, and feasibility." It's like having an automated domain expert reviewer. Why? (1) Human evaluation of 100 scenarios × 5 dimensions is ~500 evaluations — impractical for a solo developer. (2) LLM judges show 80-90% agreement with human judges on structured rubrics. (3) It's reproducible — same rubric, same scores every time. Trade-off: the judge is only as good as its rubric; poorly written rubrics give meaningless scores.

**Q: What is contamination detection and why does it matter for benchmarks?**
A: Data contamination = the model being evaluated has seen the benchmark data during training. If GPT-5 was trained on our scenarios, it would score artificially high — not because it's good at disaster response, but because it memorized the answers. We detect contamination by: (1) monitoring for sudden performance jumps (>15% improvement without model changes), (2) checking if the model can reproduce exact scenario text (memorization signal), (3) comparing performance on original vs. perturbed scenarios (a contaminated model does well on originals but poorly on perturbed versions). When detected, we regenerate those scenarios.

**Q: What are perturbation operations (from COLING 2025)?**
A: Perturbation ops create scenario variants by systematically modifying parameters while preserving the scenario's core challenge. Examples: (1) **Geographic swap** — move a cyclone from Odisha to Tamil Nadu (changes language, demographics, infrastructure), (2) **Temporal shift** — same flood but at midnight vs. noon (changes evacuation feasibility), (3) **Resource constraint** — reduce available NDRF battalions by 50%, (4) **Cascading injection** — add a secondary disaster (earthquake during flood), (5) **Communication degradation** — simulate telecom failure in affected area. This prevents overfitting to specific scenarios and tests generalization.

---

## Phase 9: Optimization & Polish

> **Goal**: Performance optimization, full dashboard integration, observability, CI/CD, deployment.
> **Learning**: Caching strategies, Grafana dashboarding, CI/CD pipelines, cloud deployment.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|------------|----------|---------|-------|--------|
| S9.1 | `specs/spec-S9.1-plan-caching/` | S6.1, S7.9 | `src/caching/plan_cache.py`, `src/caching/plan_adapter.py` | Agentic Plan Caching | ChromaDB similarity search for recurring scenarios, >20% latency reduction | pending |
| S9.2 | `specs/spec-S9.2-dashboard-integration/` | S3.4-S3.7, S7.9, S8.4 | `dashboard/src/`, `src/api/routes/` | Dashboard full data integration | Live agent data → map, real benchmark metrics, scenario replay UI | pending |
| S9.3 | `specs/spec-S9.3-langfuse-integration/` | S2.5, S7.1 | `src/shared/telemetry.py` | Langfuse full integration | All LLM calls traced, cost attribution, prompt versioning | pending |
| S9.4 | `specs/spec-S9.4-grafana-dashboards/` | S2.5 | `monitoring/` | Prometheus + Grafana dashboards | tokens_per_agent, cost_per_provider, latency, cache_hit_rate, budget alerts | pending |
| S9.5 | `specs/spec-S9.5-ci-cd/` | S1.5 | `.github/workflows/` | GitHub Actions CI/CD | Lint, test, benchmark regression on PR, Docker build | pending |
| S9.6 | `specs/spec-S9.6-deployment/` | S1.2 | `docker/`, scripts | Oracle Cloud Always Free deployment | ARM64 Docker images, setup script, health monitoring | pending |

### Interview Q&A — Phase 9

**Q: What is Agentic Plan Caching and how does it reduce latency?**
A: When a cyclone scenario hits Odisha, the system generates an evacuation plan using expensive LLM reasoning. Plan Caching stores this plan in ChromaDB with its embedding. Next time a similar cyclone scenario occurs, we first search ChromaDB for similar past plans (cosine similarity > 0.85). If found, we **adapt** the cached plan instead of generating from scratch — the LLM only needs to modify the delta (different wind speed, different districts affected). This reduces the number of LLM calls from ~15 (full planning) to ~3 (adaptation), cutting latency by 20-40%.

**Q: Why Oracle Cloud Always Free instead of AWS/GCP free tier?**
A: Oracle's Always Free tier is genuinely permanent — 4 ARM Ampere cores, 24GB RAM, 200GB storage, 10TB outbound data/month. AWS free tier expires after 12 months (then you start paying). GCP gives $300 credits for 90 days. For a demo deployment that needs to stay up indefinitely, Oracle's "always free" is the only truly $0 option with enough resources to run our Docker stack.

---

## Master Spec Index

| Spec | Feature | Phase | Depends On | Status |
|------|---------|-------|------------|--------|
| S1.1 | Project structure + dependencies | 1 | — | done |
| S1.2 | Docker Compose | 1 | S1.1 | done |
| S1.3 | Environment config (Pydantic Settings) | 1 | S1.1 | done |
| S1.4 | Database schema (PostGIS) | 1 | S1.2 | done |
| S1.5 | Makefile | 1 | S1.2 | done |
| S2.1 | Pydantic domain models | 2 | S1.3 | done |
| S2.2 | PostgreSQL/PostGIS async connection | 2 | S1.3, S1.4 | done |
| S2.3 | Redis Streams + cache utilities | 2 | S1.3 | done |
| S2.4 | CrisisError exception hierarchy | 2 | — | pending |
| S2.5 | Telemetry (structlog + Prometheus + Langfuse) | 2 | S1.3 | pending |
| S2.6 | LLM Router (5-tier multi-provider) | 2 | S1.3, S2.4, S2.5 | pending |
| S2.7 | Urgency classifier | 2 | S2.6 | pending |
| S2.8 | Cost tracker | 2 | S2.6 | pending |
| S3.1 | FastAPI gateway | 3 | S1.3, S2.1, S2.4 | pending |
| S3.2 | WebSocket server | 3 | S3.1, S2.3 | pending |
| S3.3 | Next.js dashboard setup | 3 | — | pending |
| S3.4 | India-centered Leaflet map | 3 | S3.3 | pending |
| S3.5 | Agent status panel | 3 | S3.3 | pending |
| S3.6 | Metrics panel (cost/tokens) | 3 | S3.3 | pending |
| S3.7 | Timeline component | 3 | S3.3 | pending |
| S4.1 | A2A message schemas | 4 | S2.1, S2.4 | pending |
| S4.2 | A2A server (Redis Streams) | 4 | S4.1, S2.3 | pending |
| S4.3 | A2A client (Redis Streams) | 4 | S4.1, S2.3 | pending |
| S4.4 | MCP server base framework | 4 | S1.3 | pending |
| S5.1 | MCP: IMD Weather | 5 | S4.4 | pending |
| S5.2 | MCP: SACHET CAP Feed | 5 | S4.4 | pending |
| S5.3 | MCP: USGS Earthquakes | 5 | S4.4 | pending |
| S5.4 | MCP: OSM Overpass | 5 | S4.4 | pending |
| S5.5 | MCP: ISRO Bhuvan | 5 | S4.4 | pending |
| S5.6 | MCP: NASA FIRMS Fire | 5 | S4.4 | pending |
| S6.1 | ChromaDB setup + embedding pipeline | 6 | S1.3 | pending |
| S6.2 | NDMA guidelines ingestion | 6 | S6.1 | pending |
| S6.3 | Neo4j infrastructure graph | 6 | S1.3 | pending |
| S6.4 | IMD historical data ingestion | 6 | S2.2 | pending |
| S6.5 | Census + admin boundaries | 6 | S2.2 | pending |
| S6.6 | Synthetic scenario generator | 6 | S2.6, S6.2, S6.5 | pending |
| S6.7 | Synthetic social media generator | 6 | S2.6 | pending |
| S7.1 | Base agent (LangGraph + LLM Router) | 7 | S2.6, S4.2, S4.3, S2.5 | pending |
| S7.2 | Orchestrator agent | 7 | S7.1 | pending |
| S7.3 | SituationSense agent | 7 | S7.1, S5.1, S5.2 | pending |
| S7.4 | PredictiveRisk agent | 7 | S7.1, S6.1, S6.4 | pending |
| S7.5 | ResourceAllocation agent | 7 | S7.1, S6.5 | pending |
| S7.6 | CommunityComms agent | 7 | S7.1 | pending |
| S7.7 | InfraStatus agent | 7 | S7.1, S6.3 | pending |
| S7.8 | HistoricalMemory agent | 7 | S7.1, S6.1, S6.2 | pending |
| S7.9 | Agent integration test | 7 | S7.2-S7.8, S3.2 | pending |
| S8.1 | Benchmark scenario models | 8 | S2.1, S2.2 | pending |
| S8.2 | Scenario manager | 8 | S8.1 | pending |
| S8.3 | Scenario runner (simulated clock) | 8 | S8.2, S7.9 | pending |
| S8.4 | Evaluation engine (LLM-as-judge) | 8 | S8.3, S2.6 | pending |
| S8.5 | Metric: Situational Accuracy | 8 | S8.4 | pending |
| S8.6 | Metric: Decision Timeliness | 8 | S8.4 | pending |
| S8.7 | Metric: Resource Efficiency | 8 | S8.4 | pending |
| S8.8 | Metric: Coordination Quality | 8 | S8.4 | pending |
| S8.9 | Metric: Communication Appropriateness | 8 | S8.4 | pending |
| S8.10 | Aggregate DRS scoring | 8 | S8.5-S8.9 | pending |
| S8.11 | Self-evolving generator | 8 | S8.2, S6.6 | pending |
| S9.1 | Agentic Plan Caching | 9 | S6.1, S7.9 | pending |
| S9.2 | Dashboard full integration | 9 | S3.4-S3.7, S7.9, S8.4 | pending |
| S9.3 | Langfuse full integration | 9 | S2.5, S7.1 | pending |
| S9.4 | Grafana dashboards | 9 | S2.5 | pending |
| S9.5 | CI/CD (GitHub Actions) | 9 | S1.5 | pending |
| S9.6 | Oracle Cloud deployment | 9 | S1.2 | pending |

**Total: 55 specs across 9 phases**

---

## Key Concepts Reference

### For Learning / Interviews

| Concept | Where Used | What It Is |
|---------|-----------|------------|
| **Spec-Driven Development** | Entire project | Write requirements (spec) before code. Every feature has a spec.md defining what to build, why, and how to test it. Prevents scope creep and ensures testability. |
| **TDD (Test-Driven Development)** | Every spec | Red → Green → Refactor. Write failing tests first, then write minimum code to pass. Guarantees test coverage and catches regressions. |
| **Multi-Agent Systems** | Phase 7 | Multiple specialized AI agents collaborating on a task, each with different capabilities and LLM tiers. Agents communicate via protocols (A2A). |
| **LangGraph State Machines** | Phase 7 | Each agent is a graph of nodes (functions) and edges (transitions). State flows through the graph, enabling loops, conditionals, and persistence. |
| **RAG (Retrieval-Augmented Generation)** | Phase 6, 7 | Ground LLM responses in real documents by retrieving relevant chunks before generating. Prevents hallucination of disaster procedures. |
| **MCP (Model Context Protocol)** | Phase 4, 5 | Standard protocol for LLMs to interact with external tools/data. Each MCP server wraps an API and exposes it as callable tools. |
| **A2A (Agent-to-Agent Protocol)** | Phase 4, 7 | Standard for agent interoperability. Defines task delegation, result streaming, and capability discovery between agents. |
| **Circuit Breaker Pattern** | Phase 2 | Prevents cascading failures by "opening" a circuit after repeated failures, rejecting calls during cooldown, then gradually recovering. |
| **CQRS-like Separation** | Phase 2, 3 | Redis Streams for writes (events), PostgreSQL for reads (queries). Event-driven architecture where agents publish decisions as events. |
| **Docker Compose Orchestration** | Phase 1 | Declarative multi-service deployment. One `docker-compose.yml` defines all 15+ services, their dependencies, networks, and volumes. |
| **PostGIS Spatial Queries** | Phase 1, 6 | SQL queries with geometric operations: "find all shelters within 5km of this flood polygon" — indexed for performance. |
| **Graph DB Traversals** | Phase 6, 7 | Cypher queries for multi-hop dependency analysis: "what infrastructure fails if this power grid goes down?" — O(path_length) vs O(n*joins). |
| **LLM-as-Judge** | Phase 8 | Using a strong LLM to evaluate other LLMs' outputs against structured rubrics. Scalable alternative to human evaluation. |
| **Contamination Detection** | Phase 8 | Detecting when a model has seen benchmark data during training, invalidating its scores. Critical for benchmark integrity. |
| **Agentic Plan Caching** | Phase 9 | Storing past agent plans in a vector DB, retrieving similar plans for new scenarios, adapting instead of regenerating. 20-40% latency reduction. |
| **Graceful Degradation** | Entire project | System continues functioning with reduced quality when components fail: GPU → smaller model → free API → CPU. No single point of failure. |
| **OpenAI-Compatible APIs** | Phase 2 | All LLM providers (DeepSeek, Qwen, Kimi, Groq, Ollama) use the same `base_url + api_key` pattern. Switching providers = changing 2 env vars. |
| **CAP (Common Alerting Protocol)** | Phase 5 | International standard (OASIS) for emergency alerts. XML format with severity, urgency, certainty, and geographic area. Used by SACHET/NDMA. |
