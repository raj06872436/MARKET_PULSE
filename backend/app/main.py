import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_var

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("app.requests")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    scheduler = None
    if settings.scheduler_enabled:
        from app.jobs.scheduler import start_scheduler

        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Tag every request with an ID (echoed in the response and logs) and add security headers.

    An unexpected error becomes a plain 500 with that ID, so details stay in the server log, not the browser."""
    rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
    token = request_id_var.set(rid)
    try:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            response = JSONResponse(
                {"detail": "Something went wrong on our side. Try again, and quote this ID if it keeps happening.",
                 "request_id": rid},
                status_code=500,
            )
        response.headers["X-Request-ID"] = rid
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.secure_cookies:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
    finally:
        request_id_var.reset(token)


app.include_router(api_router)
