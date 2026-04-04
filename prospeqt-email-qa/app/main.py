from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.services.workspace import load_from_env

_scheduler = AsyncIOScheduler()

_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # Load workspace API keys from environment on startup
    load_from_env()

    # Start scheduler (jobs will be added in Phase 2)
    _scheduler.start()

    yield

    # Shutdown
    _scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    """App factory — creates and configures the FastAPI application."""
    application = FastAPI(
        title="Prospeqt Email QA",
        description="QA dashboard for Instantly email campaigns across workspaces",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Mount static files if the directory exists
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register routers (Phase 2+)
    # from app.routes import dashboard, admin
    # application.include_router(dashboard.router)
    # application.include_router(admin.router)

    return application


app = create_app()
