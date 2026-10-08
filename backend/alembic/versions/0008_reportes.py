"""0008 reportes: costo congelado en linea_venta e indice de reportes (C-14).

Manual migration (no blind autogenerate), child of 0007. Agrega
`linea_venta.costo_unit` NUMERIC(10, 2) NULL con el check "nulo o mayor que
cero" (D1: el costo del producto se congela junto con precio_unit al crear
el borrador, para el margen historico) y el indice compuesto
`ix_venta_estado_confirmada_at (estado, confirmada_at)` que usan todos los
reportes (D11: igualdad primero, rango despues). Sin backfill: las lineas
previas quedan con costo NULL (completarlas con el costo actual
reintroduciria el error que se quiere evitar). Las lineas siguen siendo
inmutables para la aplicacion. batch_alter_table solo recrea la tabla en
SQLite (que no agrega checks con ALTER); en Postgres emite ALTER directo.
Mirrors backend/app/models.py column-for-column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECK = "ck_linea_venta_costo_unit_positivo"
INDICE = "ix_venta_estado_confirmada_at"


def upgrade() -> None:
    with op.batch_alter_table("linea_venta") as batch:
        batch.add_column(sa.Column("costo_unit", sa.Numeric(10, 2), nullable=True))
        batch.create_check_constraint(CHECK, "costo_unit IS NULL OR costo_unit > 0")
    op.create_index(INDICE, "venta", ["estado", "confirmada_at"])


def downgrade() -> None:
    op.drop_index(INDICE, table_name="venta")
    with op.batch_alter_table("linea_venta") as batch:
        batch.drop_constraint(CHECK, type_="check")
        batch.drop_column("costo_unit")
