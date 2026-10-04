"""0004 movimiento_stock: append-only ledger of stock changes (C-05).

Manual migration (no blind autogenerate), child of 0003.
Creates movimiento_stock with FKs to productos/usuarios, a native enum
tipo_movimiento with the 4 types reserved from day one (venta/entrada
for C-07/C-10, apertura for C-08, ajuste for this change), a check
stock_nuevo >= 0 and indexes on producto_id/created_at. Mirrors
backend/app/models.py MovimientoStock column-for-column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPO_MOVIMIENTO = sa.Enum("venta", "entrada", "ajuste", "apertura", name="tipo_movimiento")


def upgrade() -> None:
    # NOTE: the enum type is auto-created by create_table (see 0002);
    # no explicit .create() call to avoid DuplicateObject collisions.
    op.create_table(
        "movimiento_stock",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("producto_id", sa.String(36), nullable=False),
        sa.Column("tipo", TIPO_MOVIMIENTO, nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("stock_previo", sa.Integer(), nullable=False),
        sa.Column("stock_nuevo", sa.Integer(), nullable=False),
        sa.Column("ref_id", sa.String(36), nullable=True),
        sa.Column("motivo", sa.String(), nullable=True),
        sa.Column("usuario_id", sa.String(36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.CheckConstraint(
            "stock_nuevo >= 0", name="ck_movimiento_stock_nuevo_no_negativo"
        ),
    )
    op.create_index(
        "ix_movimiento_stock_producto_id", "movimiento_stock", ["producto_id"]
    )
    op.create_index(
        "ix_movimiento_stock_created_at", "movimiento_stock", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_movimiento_stock_created_at", table_name="movimiento_stock")
    op.drop_index("ix_movimiento_stock_producto_id", table_name="movimiento_stock")
    op.drop_table("movimiento_stock")
    TIPO_MOVIMIENTO.drop(op.get_bind(), checkfirst=True)
