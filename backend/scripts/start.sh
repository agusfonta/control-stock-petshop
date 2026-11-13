#!/bin/sh
# Arranque de la imagen desplegable (C-15): migra -> seed demo opcional -> API.
# Si migrar o sembrar falla, `set -e` corta y la API no arranca.
set -eu

alembic upgrade head

# El seed demo solo corre si se pide explicitamente. Con ENV=prod se niega
# (SystemExit) y el contenedor sale con error sin tocar la base.
if [ "${SEED_DEMO_AL_ARRANCAR:-}" = "true" ]; then
    python -m scripts.seed_demo
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
