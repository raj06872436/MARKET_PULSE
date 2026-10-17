import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

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
    started = time.perf_counter()
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
        if request.url.path.startswith("/api/") and request.url.path != "/api/health":
            # One JSON line per API call, without query strings (they can hold search text).
            logger.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code,
                        (time.perf_counter() - started) * 1000)
        return response
    finally:
        request_id_var.reset(token)


app.include_router(api_router)

if settings.static_dir and (static := Path(settings.static_dir)).is_dir():
    index = static / "index.html"

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        """The built React app. Hashed assets are cached for a year; any other path gets index.html for the router."""
        if path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        file = (static / path).resolve()
        if path and file.is_file() and file.is_relative_to(static.resolve()):
            immutable = path.startswith("assets/")
            return FileResponse(file, headers={"Cache-Control": "public, max-age=31536000, immutable" if immutable else "no-cache"})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
