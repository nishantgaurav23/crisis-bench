# Spec S9.6: Deployment — Implementation Checklist

## Phase 1: Tests (Red)
- [x] Write tests for deploy.sh (env validation, argument parsing)
- [x] Write tests for health_check.sh (service status parsing)
- [x] Write tests for docker-compose.prod.yml validity
- [x] Write tests for nginx config validation
- [x] Write tests for Dockerfile.api structure
- [x] Write tests for Dockerfile.dashboard structure

## Phase 2: Implementation (Green)
- [x] Create `docker/Dockerfile.api` — multi-stage Python build
- [x] Create `docker/Dockerfile.dashboard` — multi-stage Next.js build
- [x] Create `docker/nginx.conf` — reverse proxy for API + dashboard + WebSocket
- [x] Create `docker-compose.prod.yml` — production overrides
- [x] Create `.env.production.example` — production env template
- [x] Create `scripts/deploy.sh` — OCI deployment automation
- [x] Create `scripts/health_check.sh` — health monitoring

## Phase 3: Refactor + Verify
- [x] All tests pass (48/48)
- [x] ruff lint clean
- [x] No hardcoded secrets
- [x] Scripts are executable (chmod +x)
- [x] Docker Compose prod merges correctly with base
