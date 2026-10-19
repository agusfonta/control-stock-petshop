"""Agregador de modelos: importa TODOS los modelos para registrar tablas, backrefs y listeners.

Orden de raices a hojas segun FKs. Lo importan alembic/env.py, init_db, conftest y main.
"""

# ruff: noqa: I001  (el orden de imports sigue las FKs, de raices a hojas)
from app.core.db import Base
from app.modules.auth import models as auth  # noqa: F401
from app.modules.productos import models as productos  # noqa: F401
from app.modules.distribuidoras import models as distribuidoras  # noqa: F401
from app.modules.clientes import models as clientes  # noqa: F401
from app.modules.stock import models as stock  # noqa: F401
from app.modules.compras import models as compras  # noqa: F401
from app.modules.ventas import models as ventas  # noqa: F401

metadata = Base.metadata
