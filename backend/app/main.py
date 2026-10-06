"""FastAPI application factory."""

from fastapi import APIRouter, FastAPI

from app.routers import (
    auth,
    clientes,
    compras,
    distribuidoras,
    health,
    productos,
    stock,
    usuarios,
    ventas,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(productos.router)
api_router.include_router(distribuidoras.router)
api_router.include_router(stock.router)
api_router.include_router(compras.router)
api_router.include_router(clientes.router)
api_router.include_router(ventas.router)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Animall — Control Stock Petshop")
    application.include_router(api_router)
    return application


app = create_app()
