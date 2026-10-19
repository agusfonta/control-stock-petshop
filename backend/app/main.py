"""FastAPI application factory."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.auth import router as auth
from app.modules.auth import usuarios_router as usuarios
from app.modules.clientes import router as clientes
from app.modules.compras import router as compras
from app.modules.distribuidoras import router as distribuidoras
from app.modules.health import router as health
from app.modules.migracion import router as migracion
from app.modules.models import metadata  # noqa: F401  (registra TODOS los modelos y backrefs)
from app.modules.productos import router as productos
from app.modules.reportes import router as reportes
from app.modules.stock import router as stock
from app.modules.ventas import router as ventas

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
