from fastapi import APIRouter

from app.api.routes import analysis, health, imports, jobs, metrics, sources, watchlists, workspaces

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(workspaces.router)
api_router.include_router(watchlists.router)
api_router.include_router(sources.router)
api_router.include_router(jobs.router)
api_router.include_router(imports.router)
api_router.include_router(analysis.router)
api_router.include_router(metrics.router)
