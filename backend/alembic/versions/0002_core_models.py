"""0002 core models: usuarios, productos, distribuidoras, clientes + pg_trgm.

Manual migration (no blind autogenerate), child of 0001 anchor.
Mirrors backend/app/models.py column-for-column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROL_USUARIO = sa.Enum("duena", "mostrador", name="rol_usuario")
UNIDAD_PRODUCTO = sa.Enum("unidad", "bolsa", "caja", name="unidad_producto")


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
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # NOTE: enum types are auto-created by the first create_table that uses
    # them (alembic issues CREATE TYPE without checkfirst), so there must be
    # no explicit .create() call here — it would collide (DuplicateObject).

    op.create_table(
        "distribuidoras",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("contacto", sa.String(), nullable=True),
        sa.Column("cuit", sa.String(), nullable=True),
        sa.Column("condiciones", sa.String(), nullable=True),
        *_audit_columns(),
    )
    op.create_table(
        "usuarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("rol", ROL_USUARIO, nullable=False),
        *_audit_columns(),
    )
    op.create_table(
        "clientes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("telefono", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("direccion", sa.String(), nullable=True),
        sa.Column(
            "saldo_cc", sa.Numeric(10, 2), nullable=False, server_default="0"
        ),
        *_audit_columns(),
    )
    op.create_table(
        "productos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sku", sa.String(), nullable=False, unique=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("marca", sa.String(), nullable=True),
        sa.Column("categoria", sa.String(), nullable=True),
        sa.Column(
            "unidad",
            UNIDAD_PRODUCTO,
            nullable=False,
            server_default="unidad",
        ),
        sa.Column("costo", sa.Numeric(10, 2), nullable=False),
        sa.Column("margen_pct", sa.Numeric(5, 4), nullable=False),
        sa.Column(
            "stock_actual", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "stock_minimo", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("distribuidora_default_id", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(
            ["distribuidora_default_id"],
            ["distribuidoras.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("stock_actual >= 0", name="ck_productos_stock_no_negativo"),
        *_audit_columns(),
    )
    op.create_index("ix_productos_categoria", "productos", ["categoria"])
    op.execute(
        "CREATE INDEX ix_productos_nombre_trgm "
        "ON productos USING gin (nombre gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_productos_nombre_trgm")
    op.drop_index("ix_productos_categoria", table_name="productos")
    op.drop_table("productos")
    op.drop_table("clientes")
    op.drop_table("usuarios")
    op.drop_table("distribuidoras")
    UNIDAD_PRODUCTO.drop(op.get_bind(), checkfirst=True)
    ROL_USUARIO.drop(op.get_bind(), checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
