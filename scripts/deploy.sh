#!/usr/bin/env bash
# ============================================================
# CRISIS-BENCH: Oracle Cloud Always Free Deployment Script
#
# Prerequisites:
#   - Oracle Cloud Always Free ARM64 instance (Ubuntu 22.04)
#   - SSH access to the instance
#   - .env file with production secrets
#
# Usage:
#   ./scripts/deploy.sh              # Full deploy
#   ./scripts/deploy.sh --update     # Pull latest + restart
#   ./scripts/deploy.sh --help       # Show help
# ============================================================

set -euo pipefail

# ── Constants ─────────────────────────────────────────────────────────
REPO_URL="https://github.com/nishantgaurav23/crisis-bench.git"
APP_DIR="${APP_DIR:-/opt/crisis-bench}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
LOG_FILE="/var/log/crisis-bench-deploy.log"

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# ── Help ──────────────────────────────────────────────────────────────
show_help() {
    cat <<'HELP'
CRISIS-BENCH Deployment Script (Oracle Cloud Always Free)

Usage:
  ./scripts/deploy.sh              Full first-time deployment
  ./scripts/deploy.sh --update     Pull latest code and restart services
  ./scripts/deploy.sh --status     Show service status
  ./scripts/deploy.sh --help       Show this help message
  ./scripts/deploy.sh -h           Show this help message

Environment:
  APP_DIR    Installation directory (default: /opt/crisis-bench)

Requirements:
  - Oracle Cloud Always Free ARM64 instance
  - Ubuntu 22.04 or Oracle Linux 8
  - .env file with production configuration

HELP
    exit 0
}

# ── Env Validation ────────────────────────────────────────────────────
validate_env() {
    local env_file="${APP_DIR}/.env"

    if [ ! -f "$env_file" ]; then
        err ".env file not found at $env_file"
        err "Copy .env.production.example to .env and fill in your values:"
        err "  cp .env.production.example .env"
        exit 1
    fi

    # Source env to check required vars
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a

    local required_vars=(
        "POSTGRES_PASSWORD"
        "NEO4J_PASSWORD"
        "REDIS_PASSWORD"
        "LANGFUSE_SECRET"
        "LANGFUSE_SALT"
    )

    local missing=0
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            err "Required variable $var is not set in .env"
            missing=1
        fi
    done

    if [ $missing -eq 1 ]; then
        err "Fix missing environment variables before deploying."
        exit 1
    fi

    log "Environment validation passed."
}

# ── Install Docker ────────────────────────────────────────────────────
install_docker() {
    if command -v docker &>/dev/null; then
        log "Docker already installed: $(docker --version)"
        return 0
    fi

    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh

    # Add current user to docker group
    sudo usermod -aG docker "$USER"

    # Enable and start Docker
    sudo systemctl enable docker
    sudo systemctl start docker

    log "Docker installed successfully."
}

# ── Install Docker Compose ────────────────────────────────────────────
install_compose() {
    if docker compose version &>/dev/null; then
        log "Docker Compose already available: $(docker compose version)"
        return 0
    fi

    log "Installing Docker Compose plugin..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-compose-plugin

    log "Docker Compose installed."
}

# ── Install Ollama ────────────────────────────────────────────────────
install_ollama() {
    if command -v ollama &>/dev/null; then
        log "Ollama already installed: $(ollama --version)"
        return 0
    fi

    log "Installing Ollama (runs on host for ARM64 native performance)..."
    curl -fsSL https://ollama.ai/install.sh | sh

    # Pull required models
    log "Pulling Ollama models..."
    ollama pull qwen2.5:7b-instruct-q4_K_M || warn "Failed to pull qwen2.5 model"
    ollama pull nomic-embed-text || warn "Failed to pull nomic-embed-text model"

    log "Ollama installed and models pulled."
}

# ── Clone/Update Repository ───────────────────────────────────────────
setup_repo() {
    if [ -d "$APP_DIR/.git" ]; then
        log "Updating existing repository..."
        cd "$APP_DIR"
        git pull --ff-only
    else
        log "Cloning repository to $APP_DIR..."
        sudo mkdir -p "$APP_DIR"
        sudo chown "$USER:$USER" "$APP_DIR"
        git clone "$REPO_URL" "$APP_DIR"
        cd "$APP_DIR"
    fi
}

# ── Build and Start ──────────────────────────────────────────────────
start_services() {
    cd "$APP_DIR"

    log "Building Docker images (ARM64)..."
    docker compose $COMPOSE_FILES build

    log "Starting services..."
    docker compose $COMPOSE_FILES up -d

    log "Waiting for services to become healthy..."
    sleep 15

    # Run health check
    if [ -f scripts/health_check.sh ]; then
        bash scripts/health_check.sh || warn "Some services may still be starting up"
    fi

    log "Services started. Run 'docker compose $COMPOSE_FILES ps' to check status."
}

# ── Update (pull + restart) ──────────────────────────────────────────
update_services() {
    cd "$APP_DIR"

    log "Pulling latest code..."
    git pull --ff-only

    log "Rebuilding and restarting..."
    docker compose $COMPOSE_FILES build
    docker compose $COMPOSE_FILES up -d

    log "Update complete."
}

# ── Status ────────────────────────────────────────────────────────────
show_status() {
    cd "$APP_DIR"
    docker compose $COMPOSE_FILES ps
}

# ── Main ──────────────────────────────────────────────────────────────
main() {
    case "${1:-}" in
        --help|-h)
            show_help
            ;;
        --update)
            validate_env
            update_services
            ;;
        --status)
            show_status
            ;;
        "")
            log "Starting full deployment to Oracle Cloud Always Free..."
            install_docker
            install_compose
            setup_repo
            validate_env
            install_ollama
            start_services
            log "Deployment complete!"
            log "Dashboard: http://$(hostname -I | awk '{print $1}')"
            log "API:       http://$(hostname -I | awk '{print $1}')/api/docs"
            log "Grafana:   http://$(hostname -I | awk '{print $1}')/grafana"
            ;;
        *)
            err "Unknown option: $1"
            show_help
            ;;
    esac
}

main "$@"
