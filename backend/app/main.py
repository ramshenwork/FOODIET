"""Creates the FastAPI app, mounts routers, and serves the built frontend from the same origin."""
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core import access, errors, logging as app_logging, middleware, monitoring
from app.core.errors import NotFound
from app.core.settings import ROOT, get_settings
from app.services.admin.router import router as admin_router
from app.services.aggregates.router import router as aggregates_router
from app.services.feedback.router import router as feedback_router
from app.services.assistant.router import router as assistant_router
from app.services.auth.router import router as auth_router
from app.services.billing.router import router as billing_router
from app.services.diary.router import router as diary_router
from app.services.profile.router import router as profile_router
from app.services.search.router import router as search_router
from app.services.entitlement.router import router as entitlement_router
from app.services.businesses.router import router as businesses_router
from app.services.ingredients.router import router as ingredients_router
from app.services.menus.router import router as menus_router
from app.services.qr.router import public_router as qr_public_router
from app.services.qr.router import router as qr_router
from app.services.recipes.router import router as recipes_router
from app.services.ontology.router import router as ontology_router
from app.services.system.router import router as system_router
from app.services.users.router import router as users_router

FRONTEND_DIST = ROOT / "frontend" / "dist"
SERVICE_ROUTERS = [system_router, auth_router, users_router, entitlement_router, ingredients_router, ontology_router,
                   businesses_router, menus_router, recipes_router, qr_router, admin_router,
                   profile_router, billing_router, search_router, diary_router,
                   feedback_router, aggregates_router, assistant_router]


def create_app() -> FastAPI:
    settings = get_settings()  # refuses unsafe production config at startup
    app_logging.setup()
    app = FastAPI(title=f"{settings.APP_NAME} API", docs_url=None if settings.is_production else "/api/docs",
                  openapi_url=None if settings.is_production else "/api/openapi.json")
    errors.install(app)
    middleware.install(app)
    monitoring.setup()

    routers = SERVICE_ROUTERS
    access.assert_all_routes_declared(routers)
    api = APIRouter(prefix="/api/v1")
    for r in routers:
        api.include_router(r)
    app.include_router(api)
    app.include_router(qr_public_router)  # public QR page, server-rendered HTML
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    if not FRONTEND_DIST.exists():
        return
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    index = FRONTEND_DIST / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise NotFound("No such API endpoint")
        candidate = (FRONTEND_DIST / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
