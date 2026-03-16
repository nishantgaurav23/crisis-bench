# Spec S9.6: Oracle Cloud Always Free Deployment — Explanation

## Why This Spec Exists
CRISIS-BENCH needs a way to run in production beyond a developer's laptop. Oracle Cloud Infrastructure (OCI) Always Free tier provides **permanent** free compute (4 ARM64 cores, 24 GB RAM, 200 GB storage) — unlike AWS/GCP free tiers that expire. This spec creates all deployment artifacts needed to go from a fresh OCI instance to a running system with one script.

## What It Does

### Docker Images (`docker/Dockerfile.api`, `docker/Dockerfile.dashboard`)
- **Multi-stage builds** for both API (Python/FastAPI) and Dashboard (Next.js)
- Dependency layer caching: `pyproject.toml` / `package.json` copied before source code, so dependency installs are cached across builds
- Non-root users for security (principle of least privilege)
- Built-in HEALTHCHECK instructions for Docker's health monitoring
- Works on both AMD64 (dev machines) and ARM64 (OCI Ampere)

### Nginx Reverse Proxy (`docker/nginx.conf`)
- Single entry point on port 80
- Routes `/api/*` → API Gateway (:8000), `/ws` → WebSocket, `/*` → Dashboard (:3000)
- WebSocket upgrade handling with extended timeout (86400s)
- Security headers (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection)
- Gzip compression for text/JSON responses

### Production Compose (`docker-compose.prod.yml`)
- Overrides the base `docker-compose.yml` with production settings
- Memory limits per service (total ~13 GB, leaving ~11 GB for OS + Ollama)
- `restart: always` on all services
- Redis password authentication + memory limits
- PostgreSQL SCRAM-SHA-256 auth
- Neo4j heap/pagecache tuning
- Nginx as the only publicly-exposed service (port 80)

### Deployment Script (`scripts/deploy.sh`)
- Automated first-time setup: Docker install → repo clone → Ollama install → model pull → build → start
- `--update` flag for pull-and-restart updates
- Environment validation (checks all required secrets before starting)
- Idempotent (safe to run multiple times)

### Health Check (`scripts/health_check.sh`)
- Checks all 10 services (PostgreSQL, Redis, Neo4j, ChromaDB, Langfuse, Prometheus, Grafana, API, Dashboard, Ollama)
- Color-coded output with UP/DOWN status
- JSON output mode (`--json`) for monitoring integration
- Non-zero exit code on any failure (for cron alerting)

## How It Connects

| Component | Connects To | Relationship |
|-----------|------------|--------------|
| `Dockerfile.api` | S3.1 (FastAPI), S7.1+ (agents) | Packages the API + agent system |
| `Dockerfile.dashboard` | S3.3-S3.7 (dashboard) | Packages the Next.js dashboard |
| `nginx.conf` | S3.1 (API), S3.2 (WebSocket) | Routes traffic to internal services |
| `docker-compose.prod.yml` | S1.2 (base compose) | Overrides base with production settings |
| `deploy.sh` | All specs | Deploys the entire system |
| `health_check.sh` | S9.4 (Grafana) | Can feed into Grafana alerting |

## Key Design Decisions

1. **Why not Kubernetes?** Single machine, $0 budget. K8s adds a control plane, etcd, and complexity for zero benefit on a single node.

2. **Why Ollama on host (not Docker)?** ARM64 native performance. Running Ollama in Docker on ARM64 adds a virtualization layer that reduces inference speed. Host-native Ollama can also access GPU directly if available.

3. **Why 13 GB for services?** OCI gives 24 GB total. OS needs ~1 GB, Ollama with a 7B Q4 model needs ~6 GB for the model + inference buffer, leaving ~13 GB for all Docker services. PostgreSQL gets the most (4 GB) because it handles spatial queries on PostGIS data.

4. **Why not auto-TLS?** Let's Encrypt with certbot requires port 80 to be available for ACME challenges during setup. The deploy script sets up HTTP first; TLS can be added manually with certbot afterward. Automating it adds complexity and can fail silently.
