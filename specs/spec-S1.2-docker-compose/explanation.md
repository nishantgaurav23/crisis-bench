# Spec S1.2: Docker Compose — Explanation

## Why This Spec Exists

Every service in CRISIS-BENCH — PostgreSQL/PostGIS for spatial data, Redis for event streaming, Neo4j for infrastructure graphs, ChromaDB for vector search, Langfuse for LLM observability, Prometheus + Grafana for monitoring — needs to be running before any real development can happen. This spec ensures a single `docker-compose up -d` command brings up the entire infrastructure stack, with health checks guaranteeing each service is ready before dependent specs (S1.4, S2.2, S2.3, etc.) can integrate with them.

## What It Does

1. **`docker-compose.yml`** — Defines 7 services on a shared `crisis-net` bridge network:
   - **PostgreSQL + PostGIS** (port `${POSTGRES_PORT:-5434}`): Primary relational + spatial database. Hosts both the `crisis_bench` app database and a `langfuse` database (created by an init script) so Langfuse doesn't need its own PostgreSQL instance. Port is configurable via env var to avoid conflicts with other local PostgreSQL instances.
   - **Redis 7** (port `${REDIS_PORT:-6381}`): Dual-purpose — Redis Streams for the A2A event bus + standard cache. AOF persistence enabled so stream messages survive restarts. Port is configurable via env var to avoid conflicts with other local Redis instances.
   - **Neo4j Community** (ports 7474/7687): Graph database for infrastructure dependency modeling. APOC plugin enabled for advanced graph algorithms.
   - **ChromaDB** (port 8100): Vector database for RAG embeddings. Telemetry disabled.
   - **Langfuse** (port 4000): Self-hosted LLM observability. Depends on PostgreSQL being healthy before starting.
   - **Prometheus** (port 9090): Metrics scraping. Config mounted read-only from `monitoring/prometheus.yml`.
   - **Grafana** (port 4001): Dashboards. Depends on Prometheus being available.

2. **`docker-compose.cpu.yml`** — A minimal override for CPU-only environments. Used via `-f docker-compose.yml -f docker-compose.cpu.yml`.

3. **`scripts/init_langfuse_db.sh`** — Auto-creates the `langfuse` database on first PostgreSQL startup, mounted into `docker-entrypoint-initdb.d/`.

4. **`monitoring/prometheus.yml`** — Minimal scrape config targeting the API gateway (will exist after S3.1).

## How It Works

Docker Compose reads the YAML, creates named volumes for data persistence, spins up containers on the `crisis-net` bridge network, and uses health checks + `depends_on` conditions to order startup. Langfuse waits for PostgreSQL's `pg_isready` check to pass before starting. All secrets flow from the `.env` file — nothing is hardcoded.

**Key design decisions:**
- **One PostgreSQL instance, two databases**: Langfuse gets its own DB on the same instance rather than a separate PostgreSQL container. Saves ~200MB RAM.
- **Redis AOF persistence**: `--appendonly yes` ensures Redis Streams messages survive container restarts — critical for the A2A event bus where losing an alert is unacceptable.
- **Port remapping**: Langfuse (4000→3000) and Grafana (4001→3000) are remapped to avoid collisions since both use port 3000 internally. PostgreSQL and Redis use env-var-configurable ports (defaulting to 5434 and 6381) to avoid conflicts when other projects occupy the standard ports.
- **Prometheus alert rules**: `monitoring/alerts.yml` is mounted read-only alongside `prometheus.yml` for alerting on budget overruns, latency spikes, and agent failures.
- **Grafana provisioning**: Dashboard and datasource provisioning directories are mounted read-only from `monitoring/grafana/provisioning/` and `monitoring/grafana/dashboards/`, enabling auto-configured dashboards on startup.
- **Ollama runs on host**: Not in Docker, so it can access the GPU directly. Services reach it via `host.docker.internal`.

## How It Connects

| Downstream Spec | Uses |
|----------------|------|
| S1.4 (DB Schema) | PostgreSQL + PostGIS |
| S1.5 (Makefile) | `docker-compose up/down` targets |
| S2.2 (DB Connection) | PostgreSQL connection |
| S2.3 (Redis Utils) | Redis connection |
| S2.5 (Telemetry) | Langfuse, Prometheus |
| S6.1 (ChromaDB Setup) | ChromaDB connection |
| S6.3 (Neo4j Graph) | Neo4j connection |
| S9.4 (Grafana Dashboards) | Grafana |
| S9.6 (Deployment) | Docker Compose as deployment base |

## Interview Talking Points

**Q: Why one `docker-compose.yml` instead of per-service containers?**
A: Declarative multi-service orchestration. One file defines the entire infrastructure topology — networks, volumes, dependency ordering, health checks. Running 7 separate `docker run` commands with the right flags, networks, and volume mounts is error-prone. Compose makes the infrastructure reproducible and version-controlled.

**Q: Why health checks + `depends_on` conditions?**
A: Without health checks, `depends_on` only waits for the container to *start*, not for the service inside to be *ready*. PostgreSQL's container starts in ~1s, but the database accepts connections after ~5s. Langfuse connecting during that gap would crash. `condition: service_healthy` + `pg_isready` ensures Langfuse only starts when PostgreSQL is actually accepting connections.

**Q: Why named volumes instead of bind mounts?**
A: Named volumes are managed by Docker — portable across machines, no host path dependencies, and Docker handles permissions. Bind mounts tie you to a specific host directory structure and can have permission issues (especially on macOS/Linux differences). Named volumes are the right choice for database data; bind mounts are for config files you want to edit (like `prometheus.yml`).
