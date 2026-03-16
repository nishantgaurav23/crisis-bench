# Spec S9.6: Oracle Cloud Always Free Deployment

**Status**: done

## Overview
Production-ready deployment configuration for Oracle Cloud Infrastructure (OCI) Always Free tier. ARM64 (Ampere A1) Docker images, automated setup script, health monitoring, and nginx reverse proxy.

## Depends On
- S1.2 (Docker Compose) — done

## Outcomes
1. Multi-arch Dockerfiles (AMD64 + ARM64) for API gateway and dashboard
2. `docker-compose.prod.yml` override for production settings (restart policies, resource limits, env)
3. `scripts/deploy.sh` — automated OCI setup script (Docker install, clone, configure, start)
4. `scripts/health_check.sh` — periodic health monitoring of all services
5. Nginx reverse proxy config for routing API (:8000) and dashboard (:3000) behind port 80/443
6. `.env.production.example` — production environment template

## Oracle Cloud Always Free Resources
- **Compute**: 4 ARM64 Ampere A1 cores, 24 GB RAM
- **Storage**: 200 GB block volume
- **Network**: 10 TB/month outbound, public IP
- **OS**: Oracle Linux 8 or Ubuntu 22.04 (aarch64)

## Architecture on OCI
```
Internet → nginx (:80/:443)
              ├── /api/*  → API Gateway (:8000)
              ├── /ws     → WebSocket (:8000)
              └── /*      → Dashboard (:3000)

Docker Compose (prod):
  - postgres (PostGIS) — 4 GB RAM limit
  - redis — 512 MB
  - neo4j — 2 GB
  - chromadb — 1 GB
  - langfuse — 1 GB
  - prometheus — 512 MB
  - grafana — 512 MB
  - api — 2 GB
  - dashboard — 1 GB
  - nginx — 128 MB
  (Ollama runs on host for ARM64 native performance)
```

## Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `docker/Dockerfile.api` | Create | Multi-stage Python API image (ARM64 + AMD64) |
| `docker/Dockerfile.dashboard` | Create | Multi-stage Next.js dashboard image (ARM64 + AMD64) |
| `docker/nginx.conf` | Create | Nginx reverse proxy config |
| `docker-compose.prod.yml` | Create | Production overrides (resource limits, restart, env) |
| `.env.production.example` | Create | Production environment template |
| `scripts/deploy.sh` | Create | Automated OCI deployment script |
| `scripts/health_check.sh` | Create | Health monitoring script for all services |

## TDD Notes
- Test Dockerfile.api builds and starts correctly (mock app)
- Test Dockerfile.dashboard builds correctly
- Test nginx config syntax is valid
- Test docker-compose.prod.yml is valid YAML and merges correctly with base
- Test deploy.sh validates required env vars before proceeding
- Test health_check.sh correctly identifies healthy/unhealthy services
- All tests mock external calls — no real OCI API or Docker builds in unit tests

## Non-Goals
- Kubernetes / Helm charts (Docker Compose only)
- SSL/TLS certificate automation (manual Let's Encrypt for now)
- CI/CD integration (that's S9.5)
- Multi-node deployment (single machine only)
