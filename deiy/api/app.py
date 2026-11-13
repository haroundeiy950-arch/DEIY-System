"""FastAPI application factory and HTTP surface assembly."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from deiy.auth.router import admin_router, router as auth_router
from deiy.config import Settings
from deiy.container import AppContainer, build_container
from deiy.errors import AppError, NotFound, Unauthorized
from deiy.exams.router import router as exams_router
from deiy.infra.storage import LocalStorage, S3Storage
from deiy.library.router import router as library_router
from deiy.rooms.router import router as rooms_router
from deiy.support.router import router as support_router
from deiy.utilities.router import router as utilities_router

_APP: FastAPI | None = None
_WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app(settings: Settings | None = None, container: AppContainer | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate_security()
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container.start()
        try:
            yield
        finally:
            container.stop()

    app = FastAPI(
        title=f"{settings.app_name} Platform API",
        version=settings.version,
        description=(
            "Backend for the DEIY System Architecture Specification: onboarding & RBAC, "
            "digital library & live streaming, smart proctored exams, AI micro study rooms, "
            "and platform utilities with a cost-aware AI stack (Whisper + Gemini or offline mocks)."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.container = container
    app.state.settings = settings

    origins = list(settings.cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_error_handlers(app)

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(library_router)
    app.include_router(exams_router)
    app.include_router(rooms_router)
    app.include_router(utilities_router)
    app.include_router(support_router)

    @app.get("/", tags=["Meta"])
    def index() -> RedirectResponse:
        return RedirectResponse(url="/ui/", status_code=307)

    @app.get("/health", tags=["Meta"])
    def health() -> dict:
        return container.health()

    @app.get("/media/{key:path}", tags=["2. Content & Digital Library"])
    def media(key: str, token: str):
        storage = container.storage
        if isinstance(storage, S3Storage):
            return RedirectResponse(storage.presign(key, ttl_seconds=settings.media_url_ttl_seconds))
        if not isinstance(storage, LocalStorage):
            raise NotFound("Media backend unavailable.")
        if not storage.verify_media_token(key, token):
            raise Unauthorized("Invalid or expired media token.", code="invalid_media_token")
        path = storage.path_for(key)
        if not path.exists():
            raise NotFound("Media object not found.")
        return FileResponse(path)

   
    if _WEB_DIR.is_dir() and (_WEB_DIR / "index.html").is_file():
        app.mount(
            "/ui",
            StaticFiles(directory=str(_WEB_DIR), html=True),
            name="web-ui",
        )

        if (_WEB_DIR / "css").is_dir():
            app.mount(
                "/css",
                StaticFiles(directory=str(_WEB_DIR / "css")),
                name="web-css",
            )

        if (_WEB_DIR / "js").is_dir():
            app.mount(
                "/js",
                StaticFiles(directory=str(_WEB_DIR / "js")),
                name="web-js",
            )

        @app.get("/app", include_in_schema=False)
        def web_app() -> RedirectResponse:
            return RedirectResponse("/ui/")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(
            _WEB_DIR / "favicon.svg",
            media_type="image/svg+xml",
        )
    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(exc.to_dict()))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_failed",
                "message": "Request validation failed.",
                "details": jsonable_encoder(exc.errors()),
            },
        )


def get_app() -> FastAPI:
    """Lazy singleton so importing the package has no side effects."""

    global _APP
    if _APP is None:
        _APP = create_app()
    return _APP


def reset_app() -> None:
    """Test helper: drop the cached application instance."""

    global _APP
    _APP = None
