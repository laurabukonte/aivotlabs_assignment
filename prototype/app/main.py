"""
Dental Clinic Appointment Agent. FastAPI application factory.

Provides:
  POST /chat            - multi-turn text chat (LLM + function calling)
  GET  /                - web UI
  GET  /slots           - list all appointment slots
  GET  /bookings        - list confirmed bookings
  GET  /sessions/{id}   - full session transcript & log
  POST /reset-slots     - reset all slots to available ( helper)
  GET  /health          - health check
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request as StarletteRequest

from app.config import LOG_FILE, LOG_LEVEL, STATIC_DIR
from app.routes import create_router
from app.services.booking import BookingService
from app.services.llm import LLMService
from app.services.session import SessionManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger("agent")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Construct the FastAPI application with all middleware and routes."""
    application = FastAPI(title="Dental Clinic Appointment Agent")

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files (CSS, JS)
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Services
    booking_service = BookingService()
    session_manager = SessionManager()
    llm_service = LLMService(booking_service)

    # Routes
    router = create_router(booking_service, session_manager, llm_service)
    application.include_router(router)

    # Global exception handler – always return JSON
    @application.exception_handler(Exception)
    async def global_exception_handler(_request: StarletteRequest, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            {"error": str(exc) or "Internal Server Error"},
            status_code=500,
        )

    return application


app = create_app()


# Entrypoint
if __name__ == "__main__":
    import uvicorn

    from app.config import HOST, PORT

    uvicorn.run(app, host=HOST, port=PORT)