"""FastAPI application factory."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

from app.routers import (
    auth,
    clientes,
    compras,
    distribuidoras,
    health,
    migracion,
    productos,
    reportes,
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
api_router.include_router(reportes.router)
api_router.include_router(migracion.router)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Animall — Control Stock Petshop")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(api_router)
    return application


app = create_app()
