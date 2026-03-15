"""Disaster CRUD endpoints (in-memory store for MVP)."""

import uuid

from fastapi import APIRouter, Response

from src.shared.errors import CrisisValidationError
from src.shared.models import Disaster

router = APIRouter(prefix="/api/v1/disasters", tags=["disasters"])

# In-memory store — will be replaced by PostgreSQL in later specs
_disasters: dict[uuid.UUID, Disaster] = {}


@router.post("", status_code=201, response_model=Disaster)
async def create_disaster(disaster: Disaster):
    """Create a new disaster record."""
    _disasters[disaster.id] = disaster
    return disaster


@router.get("", response_model=list[Disaster])
async def list_disasters():
    """List all disasters."""
    return list(_disasters.values())


@router.get("/{disaster_id}", response_model=Disaster)
async def get_disaster(disaster_id: uuid.UUID):
    """Get a single disaster by ID."""
    disaster = _disasters.get(disaster_id)
    if disaster is None:
        raise CrisisValidationError(
            f"Disaster {disaster_id} not found",
            context={"disaster_id": str(disaster_id)},
        )
    return disaster


@router.delete("/{disaster_id}", status_code=204)
async def delete_disaster(disaster_id: uuid.UUID):
    """Delete a disaster by ID."""
    if disaster_id not in _disasters:
        raise CrisisValidationError(
            f"Disaster {disaster_id} not found",
            context={"disaster_id": str(disaster_id)},
        )
    del _disasters[disaster_id]
    return Response(status_code=204)
