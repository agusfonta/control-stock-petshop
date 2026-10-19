"""0010 mascotas: tabla de mascotas por cliente (C-17).

Manual migration, child of 0009. Crea `mascotas` (FK clientes.id, check del
tipo perro|gato|otro, soft-delete `activo` + timestamps de AuditMixin) y el
indice por `cliente_id`. Mirrors backend/app/modules/clientes/models.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mascotas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cliente_id", sa.String(36), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
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
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
        sa.CheckConstraint("tipo IN ('perro', 'gato', 'otro')", name="ck_mascotas_tipo"),
    )
    op.create_index("ix_mascotas_cliente_id", "mascotas", ["cliente_id"])


def downgrade() -> None:
    op.drop_index("ix_mascotas_cliente_id", table_name="mascotas")
    op.drop_table("mascotas")
