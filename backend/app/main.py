"""FastAPI application factory."""

from fastapi import APIRouter, FastAPI

from app.routers import health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Animall — Control Stock Petshop")
    application.include_router(api_router)
    return application


app = create_app()
