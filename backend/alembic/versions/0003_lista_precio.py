"""0003 lista_precio: costos diferenciados por distribuidora (C-04).

Manual migration (no blind autogenerate), child of 0002.
Creates lista_precio with FKs to distribuidoras/productos and a unique
constraint on the (distribuidora_id, producto_id) pair. Mirrors
backend/app/models.py ListaPrecio column-for-column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "lista_precio",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("distribuidora_id", sa.String(36), nullable=False),
        sa.Column("producto_id", sa.String(36), nullable=False),
        sa.Column("costo", sa.Numeric(10, 2), nullable=False),
        sa.ForeignKeyConstraint(["distribuidora_id"], ["distribuidoras.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.UniqueConstraint(
            "distribuidora_id",
            "producto_id",
            name="uq_lista_precio_distribuidora_producto",
        ),
        *_audit_columns(),
    )


def downgrade() -> None:
    op.drop_table("lista_precio")
