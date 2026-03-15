"""FastAPI application factory for CRISIS-BENCH API gateway."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.shared.errors import CrisisError

from .routes import agents, disasters, health
from .websocket import websocket_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle. Will init DB pools in later specs."""
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

    # WebSocket
    app.add_api_websocket_route("/ws", websocket_endpoint)

    return app
