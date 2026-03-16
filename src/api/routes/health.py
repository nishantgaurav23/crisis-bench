"""Health check endpoint."""

from fastapi import APIRouter

from src.shared.config import get_settings

router = APIRouter()


@router.get("/health")
async def health():
    """Returns system health status."""
    settings = get_settings()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "services": {},
    }
