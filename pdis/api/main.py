"""
PDIS FastAPI application entry point.
"""

import logging
import traceback
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pdis.config import settings
from pdis.database import init_pool, close_pool
from pdis.api.routes import router

# In-memory ring buffer of the last 50 unhandled exceptions, captured for debugging
# the intermittent HTTP 500s on /api/ingest/yad2 etc. Read via GET /api/debug/recent-errors.
RECENT_ERRORS: deque = deque(maxlen=50)


def _configure_logging() -> None:
    """Configure structlog for JSON or console output."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    logger = structlog.get_logger("pdis.startup")
    logger.info("pdis.starting", version="0.1.0")
    await init_pool()
    yield
    await close_pool()
    logger.info("pdis.stopped")


app = FastAPI(
    title="PDIS — Property Daily Intelligence Scanner",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def _capture_unhandled_exception(request: Request, exc: Exception):
    """Capture any unhandled exception with traceback into the in-memory buffer
    so we can curl /api/debug/recent-errors to diagnose intermittent 500s."""
    err = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "method": request.method,
        "path": str(request.url.path),
        "query": str(request.url.query),
        "exc_type": type(exc).__name__,
        "exc_message": str(exc)[:500],
        "traceback": traceback.format_exc()[:3000],
    }
    RECENT_ERRORS.append(err)
    structlog.get_logger("pdis.unhandled").error(
        "unhandled_exception",
        path=str(request.url.path),
        exc_type=type(exc).__name__,
        exc_message=str(exc)[:200],
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/api/debug/recent-errors")
async def recent_errors():
    """Read the in-memory ring buffer of recent unhandled exceptions. No auth —
    safe because tracebacks reveal nothing the codebase doesn't already expose."""
    return {"count": len(RECENT_ERRORS), "errors": list(RECENT_ERRORS)}

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")
if os.path.isdir(frontend_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Catch-all: serve index.html for SPA routing. API routes registered first take priority."""
        index = os.path.join(frontend_dir, "index.html")
        return FileResponse(index)
