"""0007 ventas: venta, linea_venta, pago_venta y evento_outbox (C-10).

Manual migration (no blind autogenerate), child of 0006. Crea las cuatro
tablas con FKs, checks (total/cantidad/precio_unit/subtotal/monto > 0,
ref_mp solo en pagos mp, fechas de confirmacion y anulacion segun el
estado), uniques (clave de idempotencia por vendedor D8, un producto por
venta, un ref_mp por pago, un evento por venta y tipo D11) e indices
(historial por cliente, listado por vendedor y por fecha, indice parcial
de eventos pendientes). Enums nativos estado_venta y metodo_pago_venta.
No altera tipo_movimiento (D3: la anulacion reutiliza el tipo `venta`).
Mirrors backend/app/models.py column-for-column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADO_VENTA = sa.Enum("borrador", "confirmada", "anulada", name="estado_venta")
METODO_PAGO_VENTA = sa.Enum(
    "efectivo", "transferencia", "mp", "tarjeta", name="metodo_pago_venta"
)


def _audit_columns() -> list[sa.Column]:
    """activo + timestamps de AuditMixin (igual que 0002/0006)."""
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
    # NOTE: the enum types are auto-created by create_table (see 0002/0004/
    # 0006); no explicit .create() call to avoid DuplicateObject collisions.
    op.create_table(
        "venta",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cliente_id", sa.String(36), nullable=True),
        sa.Column("usuario_id", sa.String(36), nullable=False),
        sa.Column(
            "estado", ESTADO_VENTA, nullable=False, server_default="borrador"
        ),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False),
        sa.Column("confirmada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmada_por_id", sa.String(36), nullable=True),
        sa.Column("anulada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anulada_por_id", sa.String(36), nullable=True),
        sa.Column("motivo_anulacion", sa.String(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["confirmada_por_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["anulada_por_id"], ["usuarios.id"]),
        sa.CheckConstraint("total > 0", name="ck_venta_total_positivo"),
        sa.CheckConstraint(
            "estado = 'borrador' OR confirmada_at IS NOT NULL",
            name="ck_venta_confirmada_con_fecha",
        ),
        sa.CheckConstraint(
            "estado <> 'anulada' OR "
            "(anulada_at IS NOT NULL AND motivo_anulacion IS NOT NULL)",
            name="ck_venta_anulada_con_fecha_y_motivo",
        ),
        sa.UniqueConstraint(
            "usuario_id", "idempotency_key", name="uq_venta_usuario_idempotency_key"
        ),
    )
    op.create_index(
        "ix_venta_cliente_id_created_at", "venta", ["cliente_id", "created_at"]
    )
    op.create_index(
        "ix_venta_usuario_id_created_at", "venta", ["usuario_id", "created_at"]
    )
    op.create_index("ix_venta_created_at", "venta", ["created_at"])

    op.create_table(
        "linea_venta",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("venta_id", sa.String(36), nullable=False),
        sa.Column("producto_id", sa.String(36), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unit", sa.Numeric(10, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["venta_id"], ["venta.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.CheckConstraint("cantidad > 0", name="ck_linea_venta_cantidad_positiva"),
        sa.CheckConstraint(
            "precio_unit > 0", name="ck_linea_venta_precio_unit_positivo"
        ),
        sa.CheckConstraint("subtotal > 0", name="ck_linea_venta_subtotal_positivo"),
        sa.UniqueConstraint(
            "venta_id", "producto_id", name="uq_linea_venta_venta_producto"
        ),
    )
    op.create_index("ix_linea_venta_producto_id", "linea_venta", ["producto_id"])

    op.create_table(
        "pago_venta",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("venta_id", sa.String(36), nullable=False),
        sa.Column("metodo", METODO_PAGO_VENTA, nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("ref_mp", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["venta_id"], ["venta.id"]),
        sa.CheckConstraint("monto > 0", name="ck_pago_venta_monto_positivo"),
        sa.CheckConstraint(
            "ref_mp IS NULL OR metodo = 'mp'", name="ck_pago_venta_ref_mp_solo_mp"
        ),
        sa.UniqueConstraint("ref_mp", name="uq_pago_venta_ref_mp"),
    )
    op.create_index("ix_pago_venta_venta_id", "pago_venta", ["venta_id"])

    op.create_table(
        "evento_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("agregado_id", sa.String(36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("procesado_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tipo", "agregado_id", name="uq_evento_outbox_tipo_agregado"
        ),
    )
    op.create_index(
        "ix_evento_outbox_pendientes",
        "evento_outbox",
        ["created_at"],
        postgresql_where=sa.text("procesado_at IS NULL"),
        sqlite_where=sa.text("procesado_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_evento_outbox_pendientes", table_name="evento_outbox")
    op.drop_table("evento_outbox")
    op.drop_index("ix_pago_venta_venta_id", table_name="pago_venta")
    op.drop_table("pago_venta")
    op.drop_index("ix_linea_venta_producto_id", table_name="linea_venta")
    op.drop_table("linea_venta")
    op.drop_index("ix_venta_created_at", table_name="venta")
    op.drop_index("ix_venta_usuario_id_created_at", table_name="venta")
    op.drop_index("ix_venta_cliente_id_created_at", table_name="venta")
    op.drop_table("venta")
    bind = op.get_bind()
    METODO_PAGO_VENTA.drop(bind, checkfirst=True)
    ESTADO_VENTA.drop(bind, checkfirst=True)
