from fastapi import APIRouter

from app.api.routes import health, watchlists, workspaces

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(workspaces.router)
api_router.include_router(watchlists.router)
