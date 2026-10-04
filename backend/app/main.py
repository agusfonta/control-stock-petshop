"""FastAPI application factory."""

from fastapi import APIRouter, FastAPI

from app.routers import auth, health, productos, usuarios

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(productos.router)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Animall — Control Stock Petshop")
    application.include_router(api_router)
    return application


app = create_app()
