"""FastAPI application factory for CRISIS-BENCH API gateway."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.shared.errors import CrisisError

from .neo4j_setup import ensure_neo4j_ready
from .rag_setup import ensure_rag_ready
from .routes import agents, benchmark, disasters, health, metrics
from .websocket import websocket_endpoint

logger = logging.getLogger("crisis.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — initialises RAG collections and Neo4j graph."""
    rag_ok = await ensure_rag_ready()
    if rag_ok:
        logger.info("RAG subsystem ready — ChromaDB seeded and available")
    else:
        logger.warning(
            "RAG subsystem unavailable — agents will operate without RAG context"
        )

    neo4j_ok = await ensure_neo4j_ready()
    if neo4j_ok:
        logger.info("Neo4j infrastructure graph ready — 10 states seeded")
    else:
        logger.warning(
            "Neo4j unavailable — InfraStatus agent will operate without graph data"
        )
    yield


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""
    app = FastAPI(
        title="CRISIS-BENCH API",
        description="Multi-agent disaster response coordination API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow dashboard and configurable origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handler for CrisisError hierarchy
    @app.exception_handler(CrisisError)
    async def crisis_error_handler(request: Request, exc: CrisisError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=exc.to_dict(),
        )

    # Routers
    app.include_router(health.router)
    app.include_router(disasters.router)
    app.include_router(agents.router)
    app.include_router(benchmark.router)
    app.include_router(metrics.router)

    # WebSocket
    app.add_api_websocket_route("/ws", websocket_endpoint)

    return app
