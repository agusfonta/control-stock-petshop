"""0006 compras: pedidos, lineas, entradas de stock y pagos (C-07).

Manual migration (no blind autogenerate), child of 0005 (CHANGES.md decia
"005" pero 0005 ya existe: indice de C-06). Crea pedido_compra,
linea_pedido, entrada_stock y pago_distribuidora con FKs, checks
(cantidad > 0, costo_unitario > 0, monto > 0), uniques (un producto por
pedido en lineas y en entradas, barrera de doble recepcion D7) e indices
sobre las FKs consultadas. Enums nativos estado_pedido y
metodo_pago_distribuidora. Mirrors backend/app/models.py column-for-column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADO_PEDIDO = sa.Enum("pendiente", "recibido", "cancelado", name="estado_pedido")
METODO_PAGO = sa.Enum(
    "efectivo", "transferencia", "cheque", "otro", name="metodo_pago_distribuidora"
)


def _audit_columns() -> list[sa.Column]:
    """activo + timestamps de AuditMixin (igual que 0002)."""
    return [
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
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
    # NOTE: the enum types are auto-created by create_table (see 0002/0004);
    # no explicit .create() call to avoid DuplicateObject collisions.
    op.create_table(
        "pedido_compra",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("distribuidora_id", sa.String(36), nullable=False),
        sa.Column(
            "estado", ESTADO_PEDIDO, nullable=False, server_default="pendiente"
        ),
        sa.Column("usuario_id", sa.String(36), nullable=False),
        sa.Column("notas", sa.String(), nullable=True),
        sa.Column("recibido_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recibido_por_id", sa.String(36), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["distribuidora_id"], ["distribuidoras.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["recibido_por_id"], ["usuarios.id"]),
    )
    op.create_index(
        "ix_pedido_compra_distribuidora_id", "pedido_compra", ["distribuidora_id"]
    )
    op.create_index("ix_pedido_compra_estado", "pedido_compra", ["estado"])

    op.create_table(
        "linea_pedido",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pedido_id", sa.String(36), nullable=False),
        sa.Column("producto_id", sa.String(36), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(10, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["pedido_id"], ["pedido_compra.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.CheckConstraint("cantidad > 0", name="ck_linea_pedido_cantidad_positiva"),
        sa.CheckConstraint(
            "costo_unitario > 0", name="ck_linea_pedido_costo_positivo"
        ),
        sa.UniqueConstraint(
            "pedido_id", "producto_id", name="uq_linea_pedido_pedido_producto"
        ),
    )

    op.create_table(
        "entrada_stock",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pedido_id", sa.String(36), nullable=False),
        sa.Column("producto_id", sa.String(36), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(10, 2), nullable=False),
        sa.Column("usuario_id", sa.String(36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido_compra.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.CheckConstraint("cantidad > 0", name="ck_entrada_stock_cantidad_positiva"),
        sa.CheckConstraint(
            "costo_unitario > 0", name="ck_entrada_stock_costo_positivo"
        ),
        sa.UniqueConstraint(
            "pedido_id", "producto_id", name="uq_entrada_stock_pedido_producto"
        ),
    )

    op.create_table(
        "pago_distribuidora",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("distribuidora_id", sa.String(36), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("metodo", METODO_PAGO, nullable=False),
        sa.Column(
            "fecha",
            sa.Date(),
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        sa.Column("nota", sa.String(), nullable=True),
        sa.Column("usuario_id", sa.String(36), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["distribuidora_id"], ["distribuidoras.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.CheckConstraint("monto > 0", name="ck_pago_distribuidora_monto_positivo"),
    )
    op.create_index(
        "ix_pago_distribuidora_distribuidora_id",
        "pago_distribuidora",
        ["distribuidora_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pago_distribuidora_distribuidora_id", table_name="pago_distribuidora"
    )
    op.drop_table("pago_distribuidora")
    op.drop_table("entrada_stock")
    op.drop_table("linea_pedido")
    op.drop_index("ix_pedido_compra_estado", table_name="pedido_compra")
    op.drop_index("ix_pedido_compra_distribuidora_id", table_name="pedido_compra")
    op.drop_table("pedido_compra")
    bind = op.get_bind()
    METODO_PAGO.drop(bind, checkfirst=True)
    ESTADO_PEDIDO.drop(bind, checkfirst=True)
