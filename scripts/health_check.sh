#!/usr/bin/env bash
# ============================================================
# CRISIS-BENCH: Health Check Script
#
# Checks all services and reports their status.
# Exit code 0 = all healthy, 1 = one or more unhealthy.
#
# Usage:
#   ./scripts/health_check.sh           # Check all services
#   ./scripts/health_check.sh --json    # Output as JSON
# ============================================================

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILURES=0
JSON_MODE=false

if [ "${1:-}" = "--json" ]; then
    JSON_MODE=true
fi

# ── Check Functions ───────────────────────────────────────────────────
check_service() {
    local name="$1"
    local check_cmd="$2"

    if eval "$check_cmd" &>/dev/null; then
        if [ "$JSON_MODE" = true ]; then
            echo "  \"$name\": \"UP\","
        else
            echo -e "  ${GREEN}[UP]${NC}   $name"
        fi
    else
        FAILURES=$((FAILURES + 1))
        if [ "$JSON_MODE" = true ]; then
            echo "  \"$name\": \"DOWN\","
        else
            echo -e "  ${RED}[DOWN]${NC} $name"
        fi
    fi
}

# ── Main ──────────────────────────────────────────────────────────────
echo ""
if [ "$JSON_MODE" = true ]; then
    echo "{"
else
    echo "CRISIS-BENCH Health Check"
    echo "========================="
fi

# PostgreSQL (port 5432 inside Docker network, mapped port varies)
check_service "PostgreSQL" \
    "docker exec crisis-postgres pg_isready -U crisis"

# Redis (port 6379 inside Docker)
check_service "Redis" \
    "docker exec crisis-redis redis-cli ping"

# Neo4j (port 7474 HTTP)
check_service "Neo4j" \
    "curl -sf http://localhost:7474 >/dev/null"

# ChromaDB (port 8100 mapped to 8000 internal)
check_service "ChromaDB" \
    "curl -sf http://localhost:8100/api/v1/heartbeat >/dev/null"

# Langfuse (port 4000)
check_service "Langfuse" \
    "curl -sf http://localhost:4000/api/public/health >/dev/null"

# Prometheus (port 9090)
check_service "Prometheus" \
    "curl -sf http://localhost:9090/-/healthy >/dev/null"

# Grafana (port 4001)
check_service "Grafana" \
    "curl -sf http://localhost:4001/api/health >/dev/null"

# API Gateway (port 8000)
check_service "API Gateway" \
    "curl -sf http://localhost:8000/health >/dev/null"

# Dashboard (port 3000)
check_service "Dashboard" \
    "curl -sf http://localhost:3000/ >/dev/null"

# Ollama (port 11434, runs on host)
check_service "Ollama" \
    "curl -sf http://localhost:11434/api/tags >/dev/null"

# ── Summary ───────────────────────────────────────────────────────────
echo ""
if [ "$JSON_MODE" = true ]; then
    echo "  \"failures\": $FAILURES"
    echo "}"
else
    TOTAL=10
    HEALTHY=$((TOTAL - FAILURES))
    if [ $FAILURES -eq 0 ]; then
        echo -e "${GREEN}All $TOTAL services healthy.${NC}"
    else
        echo -e "${YELLOW}$HEALTHY/$TOTAL services healthy, $FAILURES FAILED.${NC}"
    fi
fi

if [ $FAILURES -gt 0 ]; then
    exit 1
fi

exit 0
