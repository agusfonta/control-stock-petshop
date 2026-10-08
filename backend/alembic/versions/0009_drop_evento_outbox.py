"""0009 drop evento_outbox: se elimina la bandeja de eventos de C-10.

Manual migration (no blind autogenerate), child of 0008. La tabla
`evento_outbox` (creada en 0007) quedo sin consumidor: el outbox se
rediseña en C-11 con el contrato real de facturacion. Se eliminan el indice
parcial `ix_evento_outbox_pendientes` y la tabla; el downgrade la recrea tal
cual la creaba 0007 (columnas, unique `uq_evento_outbox_tipo_agregado` e
indice parcial), sin datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_evento_outbox_pendientes", table_name="evento_outbox")
    op.drop_table("evento_outbox")


def downgrade() -> None:
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
