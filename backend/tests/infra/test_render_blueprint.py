"""Imagen desplegable y Blueprint de Render (C-15 demo, RED-first).

Verifica por lectura de texto/YAML (sin Docker ni red) los invariantes del
Dockerfile `runtime`, del script de arranque y de `render.yaml`.
"""

import re
from pathlib import Path

import pytest
import yaml

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
DOCKERFILE = BACKEND_DIR / "Dockerfile"
START_SH = BACKEND_DIR / "scripts" / "start.sh"


def _etapa_runtime() -> list[str]:
    lineas = DOCKERFILE.read_text(encoding="utf-8").splitlines()
    inicio = next(i for i, ln in enumerate(lineas) if re.match(r"FROM .+ AS runtime\s*$", ln))
    return lineas[inicio:]


def test_runtime_es_la_ultima_etapa() -> None:
    froms = [ln for ln in DOCKERFILE.read_text(encoding="utf-8").splitlines() if ln.startswith("FROM ")]
    assert froms[-1].endswith("AS runtime")
    assert len(froms) >= 2  # hay otras etapas (deps, dev) y runtime es la final


def test_runtime_usuario_no_root_scripts_y_cmd() -> None:
    etapa = "\n".join(_etapa_runtime())
    usuarios = re.findall(r"^USER (\S+)", etapa, flags=re.M)
    assert usuarios and usuarios[-1] not in ("root", "0")
    assert "COPY ./scripts ./scripts" in etapa
    cmd = re.findall(r"^CMD (.+)$", etapa, flags=re.M)
    assert cmd and "scripts/start.sh" in cmd[-1]
    assert "uvicorn" not in cmd[-1]  # uvicorn lo lanza el script, tras migrar


def test_start_sh_migra_siembra_a_pedido_y_ejecuta_uvicorn() -> None:
    texto = START_SH.read_text(encoding="utf-8")
    assert "\r" not in texto  # LF: sh no tolera CRLF
    lineas = [ln.strip() for ln in texto.splitlines() if not ln.strip().startswith("#")]
    cuerpo = "\n".join(lineas)
    assert "set -eu" in cuerpo

    pos_migrar = cuerpo.index("alembic upgrade head")
    flag = re.search(r'"\$\{SEED_DEMO_AL_ARRANCAR(:-)?\}" = "true"', cuerpo)
    assert flag, "el seed debe depender de SEED_DEMO_AL_ARRANCAR=true"
    pos_flag = flag.start()
    pos_seed = cuerpo.index("python -m scripts.seed_demo")
    pos_uvicorn = cuerpo.index("exec uvicorn")
    assert pos_migrar < pos_flag < pos_seed < pos_uvicorn
    assert re.search(r'--port "\$\{PORT:-8000\}"', cuerpo)
    assert cuerpo.count("python -m scripts.seed_demo") == 1  # solo bajo el flag


def test_gitattributes_fuerza_lf_en_sh() -> None:
    ga = (REPO_DIR / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"^\*\.sh\s+text\s+eol=lf\s*$", ga, flags=re.M)


# --- Blueprint de Render ---------------------------------------------------

BLUEPRINT = REPO_DIR / "render.yaml"
REGION = "virginia"
CLAVES_SENSIBLES = ("PASSWORD", "SECRET", "TOKEN", "KEY")


@pytest.fixture(scope="module")
def blueprint() -> dict:
    return yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))


def _servicio(blueprint: dict, nombre: str) -> dict:
    return next(s for s in blueprint["services"] if s["name"] == nombre)


def _env(servicio: dict) -> dict[str, dict]:
    return {e["key"]: e for e in servicio["envVars"]}


def test_recursos_en_plan_gratis_y_misma_region(blueprint: dict) -> None:
    api = _servicio(blueprint, "animall-demo-api")
    kv = _servicio(blueprint, "animall-demo-kv")
    web = _servicio(blueprint, "animall-demo")
    db = next(d for d in blueprint["databases"] if d["name"] == "animall-demo-db")

    assert (api["type"], api["runtime"]) == ("web", "docker")
    assert kv["type"] == "keyvalue"
    assert (web["type"], web["runtime"]) == ("web", "static")
    for recurso in (api, kv, db):
        assert recurso["plan"] == "free"
        assert recurso["region"] == REGION
    assert "plan" not in web or web["plan"] == "free"
    assert len(blueprint["services"]) == 3 and len(blueprint["databases"]) == 1


def test_backend_docker_health_y_contexto(blueprint: dict) -> None:
    api = _servicio(blueprint, "animall-demo-api")
    assert api["healthCheckPath"] == "/api/health"
    assert api["dockerfilePath"] == "./backend/Dockerfile"
    assert api["dockerContext"] == "./backend"


def test_backend_env_staging_con_seed_y_conexiones_de_recursos(
    blueprint: dict,
) -> None:
    env = _env(_servicio(blueprint, "animall-demo-api"))
    assert env["ENV"]["value"] == "staging"
    assert str(env["SEED_DEMO_AL_ARRANCAR"]["value"]).lower() == "true"
    assert str(env["PORT"]["value"]) == "8000"
    assert env["DATABASE_URL"]["fromDatabase"] == {
        "name": "animall-demo-db",
        "property": "connectionString",
    }
    redis_ref = env["REDIS_URL"]["fromService"]
    assert redis_ref["name"] == "animall-demo-kv"
    assert redis_ref["type"] == "keyvalue"
    assert redis_ref["property"] == "connectionString"


def test_secretos_generados_o_pedidos_nunca_literales(blueprint: dict) -> None:
    env = _env(_servicio(blueprint, "animall-demo-api"))
    assert env["SECRET_KEY"]["generateValue"] is True
    assert "value" not in env["SECRET_KEY"]
    for nombre in ("SEED_OWNER_PASSWORD", "SEED_MOSTRADOR_PASSWORD"):
        assert env[nombre]["sync"] is False
        assert "value" not in env[nombre]


def test_ninguna_variable_sensible_tiene_valor_literal(blueprint: dict) -> None:
    todas = [e for s in blueprint["services"] for e in s.get("envVars", [])]
    assert todas
    for e in todas:
        if any(c in e["key"].upper() for c in CLAVES_SENSIBLES):
            assert "value" not in e, f"{e['key']} no puede ser literal"
    literales = {e["key"] for e in todas if "value" in e}
    assert not literales & {"DATABASE_URL", "REDIS_URL"}


def test_keyvalue_sin_acceso_publico(blueprint: dict) -> None:
    assert _servicio(blueprint, "animall-demo-kv")["ipAllowList"] == []
    db = next(d for d in blueprint["databases"] if d["name"] == "animall-demo-db")
    assert db["ipAllowList"] == []


def test_static_site_construye_frontend(blueprint: dict) -> None:
    web = _servicio(blueprint, "animall-demo")
    assert web["rootDir"] == "frontend"
    assert "npm run build" in web["buildCommand"]
    assert web["staticPublishPath"].lstrip("./") == "dist"
    assert "VITE_API_BASE_URL" not in _env(web)  # /api relativo, mismo origen


def test_rewrite_api_antes_que_el_fallback_spa(blueprint: dict) -> None:
    rutas = _servicio(blueprint, "animall-demo")["routes"]
    assert all(r["type"] == "rewrite" for r in rutas)  # nunca redirect
    origenes = [r["source"] for r in rutas]
    assert origenes.index("/api/*") < origenes.index("/*")
    api = rutas[origenes.index("/api/*")]
    assert re.fullmatch(r"https://[a-z0-9-]+\.onrender\.com/api/\*", api["destination"])
    assert "animall-demo-api" in api["destination"]
    assert rutas[origenes.index("/*")]["destination"] == "/index.html"


def test_cors_apunta_al_frontend_de_la_demo(blueprint: dict) -> None:
    env = _env(_servicio(blueprint, "animall-demo-api"))
    assert env["CORS_ORIGINS"]["value"] == "https://animall-demo.onrender.com"
