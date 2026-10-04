"""0005 lista_precio producto idx: indice para comparar por producto (C-06).

Manual migration (no blind autogenerate), child of 0004, index-only (D1):
el unique (distribuidora_id, producto_id) de 0003 no sirve al filtrar
solo por producto (columna izquierda = distribuidora); comparar por
producto seria full scan al crecer las listas. Sin cambios de columnas.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_lista_precio_producto_id", "lista_precio", ["producto_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_lista_precio_producto_id", table_name="lista_precio")
