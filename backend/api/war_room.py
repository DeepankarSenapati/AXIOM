"""Authenticated, synthetic-only War Room review endpoints."""

from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, HTTPException

import backend.config as settings
import backend.engine.war_room as war_room_engine
import backend.engine.war_room_claude as claude
from backend.auth.dependencies import get_current_user
from backend.db.models import DBUser
from backend.engine.war_room import build_review
from backend.engine.war_room_models import CapabilitiesResponse, WarRoomError, WarRoomRequest, WarRoomResponse

router = APIRouter(prefix="/arena/war-room", tags=["war room"])

# Bounds simultaneous reruns and provider calls in this process.
_review_slots = BoundedSemaphore(settings.WAR_ROOM_MAX_CONCURRENT_REVIEWS)


@router.get("/capabilities", response_model=CapabilitiesResponse)
def war_room_capabilities(_user: DBUser = Depends(get_current_user)) -> CapabilitiesResponse:
    configured = claude.is_configured()
    return CapabilitiesResponse(
        claude_configured=configured,
        model=claude.model_name() if configured else None,
        max_claude_reviews=war_room_engine.claude_quota.limit,
        claude_reviews_remaining=war_room_engine.claude_quota.remaining(),
    )


@router.post("/review", response_model=WarRoomResponse)
def war_room_review(request: WarRoomRequest, _user: DBUser = Depends(get_current_user)) -> WarRoomResponse:
    if not _review_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="The War Room is busy. Please try again shortly.")
    try:
        return build_review(request)
    except WarRoomError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from None
    finally:
        _review_slots.release()
