"""
API routes for the dental clinic appointment agent.

All route handlers are thin — business logic lives in the services layer.
"""

import uuid

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.config import SESSION_TIMEOUT_SECONDS, SESSION_WARNING_SECONDS, TEMPLATES_DIR
from app.services.booking import BookingService
from app.services.llm import LLMService
from app.services.session import SessionManager

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    state: str
    log: list[dict]


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def create_router(
    booking_service: BookingService,
    session_manager: SessionManager,
    llm_service: LLMService,
) -> APIRouter:
    """Build and return the main API router with all endpoints."""
    router = APIRouter()

    #  Chat endpoint
    @router.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        session_id = request.session_id or str(uuid.uuid4())
        session = session_manager.get_or_create(session_id)

        reply = llm_service.get_reply(session, request.message)

        return ChatResponse(
            response=reply,
            session_id=session_id,
            state=session.state,
            log=session.log,
        )

    #  Utility 
    @router.get("/slots")
    async def get_slots():
        return booking_service.get_slots()

    @router.get("/bookings")
    async def get_bookings():
        return booking_service.get_bookings()

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: str):
        session = session_manager.get(session_id)
        if not session:
            return JSONResponse({"error": "Session not found"}, status_code=404)
        return session.to_dict()

    @router.get("/sessions")
    async def list_sessions():
        return session_manager.list_sessions()


    @router.get("/health")
    async def health():
        return {"status": "healthy", "service": "dental-clinic-agent"}

    #  Web UI 
    @router.get("/", response_class=HTMLResponse)
    async def index():
        template = (TEMPLATES_DIR / "index.html").read_text()
        # Inject timeout settings so the JS can use them
        html = (
            template
            .replace("{{ session_timeout }}", str(SESSION_TIMEOUT_SECONDS))
            .replace("{{ session_warning }}", str(SESSION_WARNING_SECONDS))
        )
        return HTMLResponse(content=html)

    return router
