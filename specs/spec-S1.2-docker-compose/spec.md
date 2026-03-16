# Spec S1.2: Docker Compose for All Services

**Status**: done
**Phase**: 1 — Project Bootstrap
**Depends On**: S1.1 (Project structure + dependencies) ✅ done
**Location**: `docker-compose.yml`, `docker-compose.cpu.yml`

---

## 1. Overview

Create a Docker Compose configuration that starts all infrastructure services with a single `docker-compose up` command. A CPU-only override file (`docker-compose.cpu.yml`) is provided for machines without GPU access.

### Why This Matters

- **Interview**: Docker Compose orchestration is a fundamental DevOps skill — demonstrates understanding of multi-service architecture, networking, volumes, health checks, and dependency ordering.
- **Project**: Every subsequent spec (S1.4 DB schema, S2.2 DB connection, S2.3 Redis, etc.) depends on these services being available. This is the foundation for all integration testing.

---

## 2. Services

| Service | Image | Port(s) | Volume | Health Check |
|---------|-------|---------|--------|--------------|
| PostgreSQL + PostGIS | `postgis/postgis:16-3.4` | `${POSTGRES_PORT:-5434}` | `postgres_data` | `pg_isready` |
| Redis 7 | `redis:7-alpine` | `${REDIS_PORT:-6381}` | `redis_data` | `redis-cli ping` |
| Neo4j Community | `neo4j:5-community` | 7474 (HTTP), 7687 (Bolt) | `neo4j_data` | HTTP check on 7474 |
| ChromaDB | `chromadb/chroma:latest` | 8100 | `chroma_data` | HTTP check on `/api/v1/heartbeat` |
| Langfuse | `langfuse/langfuse:2` | 4000 | — (uses PostgreSQL) | HTTP check on `/api/public/health` |
| Prometheus | `prom/prometheus:latest` | 9090 | `prometheus_data` + config mount | HTTP check on `/-/healthy` |
| Grafana | `grafana/grafana:latest` | 4001 | `grafana_data` | HTTP check on `/api/health` |

### Notes

- **Ollama** runs on the host (not Docker) for GPU access. Services connect to it via `OLLAMA_HOST` env var (default `http://host.docker.internal:11434`).
- **Langfuse** requires its own PostgreSQL database. We create a second DB (`langfuse`) on the same PostgreSQL instance using an init script.
- All services use a shared Docker network `crisis-net`.
- All passwords/secrets come from `.env` file (never hardcoded).

---

## 3. docker-compose.yml Requirements

### 3.1 Networks
- `crisis-net` — bridge network, all services attached

### 3.2 Volumes (named)
- `postgres_data`, `redis_data`, `neo4j_data`, `chroma_data`, `prometheus_data`, `grafana_data`

### 3.3 Service Configuration

#### PostgreSQL + PostGIS
- Image: `postgis/postgis:16-3.4`
- Port: `${POSTGRES_PORT:-5434}:5432` (configurable via env, default 5434 to avoid conflicts)
- Environment: `POSTGRES_USER=crisis`, `POSTGRES_PASSWORD=${POSTGRES_PASSWORD}`, `POSTGRES_DB=crisis_bench`
- Volume: `postgres_data:/var/lib/postgresql/data`
- Init script mount: `./scripts/init_langfuse_db.sh:/docker-entrypoint-initdb.d/init_langfuse_db.sh`
- Health check: `pg_isready -U crisis`
- Restart: `unless-stopped`

#### Redis
- Image: `redis:7-alpine`
- Port: `${REDIS_PORT:-6381}:6379` (configurable via env, default 6381 to avoid conflicts)
- Command: `redis-server --appendonly yes` (AOF persistence for Streams durability)
- Volume: `redis_data:/data`
- Health check: `redis-cli ping`
- Restart: `unless-stopped`

#### Neo4j Community
- Image: `neo4j:5-community`
- Ports: `7474:7474`, `7687:7687`
- Environment: `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`, `NEO4J_PLUGINS=["apoc"]`
- Volume: `neo4j_data:/data`
- Health check: `wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1`
- Restart: `unless-stopped`

#### ChromaDB
- Image: `chromadb/chroma:latest`
- Port: `8100:8000`
- Volume: `chroma_data:/chroma/chroma`
- Environment: `ANONYMIZED_TELEMETRY=false`
- Health check: `curl -f http://localhost:8000/api/v1/heartbeat || exit 1`
- Restart: `unless-stopped`

#### Langfuse
- Image: `langfuse/langfuse:2`
- Port: `4000:3000`
- Environment: `DATABASE_URL=postgresql://crisis:${POSTGRES_PASSWORD}@postgres:5432/langfuse`, `NEXTAUTH_SECRET=${LANGFUSE_SECRET}`, `SALT=${LANGFUSE_SALT}`, `NEXTAUTH_URL=http://localhost:4000`
- Depends on: `postgres` (healthy)
- Health check: `curl -f http://localhost:3000/api/public/health || exit 1`
- Restart: `unless-stopped`

#### Prometheus
- Image: `prom/prometheus:latest`
- Port: `9090:9090`
- Volume: `prometheus_data:/prometheus`, `./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro`, `./monitoring/alerts.yml:/etc/prometheus/alerts.yml:ro`
- Health check: `wget --no-verbose --tries=1 --spider http://localhost:9090/-/healthy || exit 1`
- Restart: `unless-stopped`

#### Grafana
- Image: `grafana/grafana:latest`
- Port: `4001:3000`
- Volume: `grafana_data:/var/lib/grafana`, `./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro`, `./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro`
- Environment: `GF_SECURITY_ADMIN_PASSWORD=admin`, `GF_SERVER_HTTP_PORT=3000`
- Depends on: `prometheus` (started)
- Health check: `curl -f http://localhost:3000/api/health || exit 1`
- Restart: `unless-stopped`

---

## 4. docker-compose.cpu.yml Requirements

An override file for CPU-only environments (no GPU). This file:
- Is used via: `docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up`
- Contains only overrides, no full service definitions
- Sets `OLLAMA_HOST=http://host.docker.internal:11434` as extra environment for services that need Ollama access

---

## 5. Supporting Files

### 5.1 `scripts/init_langfuse_db.sh`
- Bash script mounted into PostgreSQL's `docker-entrypoint-initdb.d/`
- Creates the `langfuse` database if it doesn't exist
- Uses `POSTGRES_USER` env var

### 5.2 `monitoring/prometheus.yml`
- Minimal Prometheus config
- Scrape targets: `api-gateway:8000/metrics` (will exist after S3.1)
- Scrape interval: 15s
- Global evaluation interval: 15s

---

## 6. Outcomes / Acceptance Criteria

1. `docker-compose config` validates without errors
2. `docker-compose up -d` starts all 7 services
3. Each service passes its health check within 60 seconds
4. PostgreSQL has both `crisis_bench` and `langfuse` databases
5. Redis responds to PING
6. Neo4j is reachable on Bolt (7687) and HTTP (7474)
7. ChromaDB heartbeat returns 200
8. Langfuse health endpoint returns 200
9. Prometheus UI accessible on 9090
10. Grafana UI accessible on 4001
11. All services are on `crisis-net` network
12. No secrets hardcoded — all from `.env`

---

## 7. TDD Notes

### What to Test
Since Docker Compose files are YAML configuration (not Python code), we test:

1. **YAML validity**: Parse `docker-compose.yml` and `docker-compose.cpu.yml` as valid YAML
2. **Service presence**: All 7 services defined
3. **Port mappings**: Correct host:container port pairs
4. **Volume definitions**: All named volumes declared
5. **Health checks**: Every service has a health check
6. **Network**: All services on `crisis-net`
7. **Environment secrets**: No hardcoded passwords (all use `${VAR}` syntax)
8. **Depends-on ordering**: Langfuse depends on postgres, Grafana depends on prometheus
9. **Init script**: PostgreSQL mounts the langfuse db init script
10. **Override merge**: CPU override file merges correctly with base

### Test File
`tests/unit/test_docker_compose.py`

### How to Test
- Use `pyyaml` to parse the compose files
- Validate structure, keys, and values programmatically
- No Docker daemon required for unit tests
