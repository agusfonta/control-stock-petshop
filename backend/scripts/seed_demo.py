"""Seed de demostracion de Animall (C-13 D15). Solo ENV=dev|test.

Crea la duena y un usuario mostrador (passwords SOLO por variables de
entorno, sin defaults), un catalogo petshop, distribuidoras con listas de
precios superpuestas, clientes, un pedido recibido y uno pendiente, y ventas
de los ultimos 7 dias (una anulada) para que todos los reportes tengan datos.

Todo cambio de stock pasa por `services.stock.aplicar_movimiento` (via las
funciones de `services.compras` y `services.ventas`), asi cada unidad tiene su
movimiento. Solo las fechas de las ventas se retrasan despues de confirmarlas
(UPDATE directo de `venta`) para repartirlas en la semana.

Idempotente: si ya existe el SKU ancla solo asegura los usuarios y sale. Si el
seed se interrumpe a mitad de camino, reiniciar la base (borrar `dev.db` o
`docker compose down -v`) y volver a correrlo.

Uso (desde backend/):
    SEED_OWNER_PASSWORD=... SEED_MOSTRADOR_PASSWORD=... python -m scripts.seed_demo
"""

import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import update

ENVS_PERMITIDOS = ("dev", "test")
OWNER_ENV = "SEED_OWNER_PASSWORD"
MOSTRADOR_ENV = "SEED_MOSTRADOR_PASSWORD"
MOSTRADOR_EMAIL = "mostrador@petshop.local"
SKU_ANCLA = "RC-MINI-3KG"
_CENTAVOS = Decimal("0.01")

# (clave, nombre, contacto, cuit, condiciones)
DISTRIBUIDORAS = (
    ("sur", "Distribuidora Sur", "ventas@disur.com", "30-70123456-1", "Pago a 7 dias"),
    (
        "petfood",
        "PetFood Mayorista",
        "pedidos@petfoodmayorista.com",
        "30-71234567-2",
        "Contado, entrega en 48 hs",
    ),
    (
        "higiene",
        "Higiene & Co",
        "contacto@higieneandco.com",
        "30-72345678-3",
        "Pago a 15 dias",
    ),
    (
        "petfun",
        "PetFun Mayorista",
        "mayorista@petfun.com",
        "30-73456789-4",
        "Minimo de compra $50.000",
    ),
)

# (sku, nombre, marca, categoria, unidad, costo, margen, stock_inicial, minimo, distribuidora)
PRODUCTOS = (
    (
        "RC-MINI-3KG", "Royal Canin Mini Adulto 3kg", "Royal Canin", "alimentos", "bolsa",
        "18000", "0.35", 30, 10, "petfood",
    ),
    (
        "RC-MINI-10KG", "Royal Canin Mini Adulto 10kg", "Royal Canin", "alimentos", "bolsa",
        "52000", "0.35", 14, 10, "petfood",
    ),
    ("PROPLAN-AD-15KG", "Pro Plan Adulto 15kg", "Purina", "alimentos", "bolsa", "48000", "0.35", 20, 8, "sur"),
    ("WHISKAS-GATO-10KG", "Whiskas Pescado 10kg", "Whiskas", "alimentos", "bolsa", "32000", "0.35", 18, 8, "sur"),
    ("SNACK-HUESO-500G", "Huesitos snack 500g", "PetFun", "snacks", "unidad", "2500", "0.80", 40, 10, "petfun"),
    ("GALLETA-PERRO-1KG", "Galletitas huesito 1kg", "Animall", "snacks", "bolsa", "3000", "0.85", 35, 10, "petfun"),
    (
        "SHAMPOO-PULGAS-500ML", "Shampoo antipulgas 500ml", "Osmac", "higiene", "unidad",
        "4000", "0.90", 22, 6, "higiene",
    ),
    ("PIEDRA-GATO-4KG", "Piedras sanitarias 4kg", "Absorsol", "higiene", "bolsa", "3500", "0.90", 25, 10, "higiene"),
    ("TOALLITAS-50U", "Toallitas humedas x50", "PetCare", "higiene", "caja", "2000", "0.90", 30, 10, "higiene"),
    ("PELOTA-01", "Pelota resistente", "PetFun", "juguetes", "unidad", "1500", "0.95", 50, 10, "petfun"),
    ("SOGA-DENTAL", "Soga dental", "PetFun", "juguetes", "unidad", "1800", "0.95", 28, 8, "petfun"),
    ("RATON-CATNIP", "Raton con catnip", "CatJoy", "juguetes", "unidad", "1200", "1.00", 33, 10, "petfun"),
    ("CORREA-RETR-5M", "Correa retractil 5m", "Trixie", "accesorios", "unidad", "8000", "0.85", 15, 5, "petfun"),
    ("COLLAR-NYLON-M", "Collar nylon talle M", "Trixie", "accesorios", "unidad", "2500", "1.00", 20, 5, "petfun"),
    ("PLATO-ACERO", "Plato acero inoxidable", "Ferplast", "accesorios", "unidad", "3000", "1.00", 18, 5, "sur"),
    ("ANTIPAR-10KG", "Antiparasitario hasta 10kg", "Basken", "farmacia", "unidad", "5000", "0.90", 16, 6, "sur"),
    ("VIT-60C", "Vitaminas x60 comprimidos", "Lab Vet", "farmacia", "unidad", "6000", "0.90", 9, 5, "sur"),
    ("CUCHA-XL", "Cucha plastica XL", "Ferplast", "cuchas", "unidad", "25000", "0.80", 3, 3, "sur"),
    ("TRANSP-M", "Transportadora mediana", "Ferplast", "cuchas", "unidad", "22000", "0.80", 7, 3, "sur"),
)

# (distribuidora, sku, costo): superposicion de listas entre distribuidoras.
LISTAS = (
    ("petfood", "RC-MINI-3KG", "18000"),
    ("sur", "RC-MINI-3KG", "18500"),
    ("petfood", "RC-MINI-10KG", "52000"),
    ("sur", "RC-MINI-10KG", "52800"),
    ("sur", "PROPLAN-AD-15KG", "48000"),
    ("petfood", "PROPLAN-AD-15KG", "47500"),
    ("sur", "WHISKAS-GATO-10KG", "32000"),
    ("petfood", "WHISKAS-GATO-10KG", "31800"),
    ("petfun", "SNACK-HUESO-500G", "2500"),
    ("petfun", "GALLETA-PERRO-1KG", "3000"),
    ("higiene", "SHAMPOO-PULGAS-500ML", "4000"),
    ("higiene", "PIEDRA-GATO-4KG", "3500"),
    ("higiene", "TOALLITAS-50U", "2100"),
    ("petfun", "TOALLITAS-50U", "2150"),
    ("petfun", "PELOTA-01", "1500"),
    ("petfun", "SOGA-DENTAL", "1800"),
    ("petfun", "RATON-CATNIP", "1200"),
    ("petfun", "CORREA-RETR-5M", "8000"),
    ("sur", "CORREA-RETR-5M", "8300"),
    ("petfun", "COLLAR-NYLON-M", "2500"),
    ("sur", "PLATO-ACERO", "3000"),
    ("sur", "ANTIPAR-10KG", "5000"),
    ("sur", "VIT-60C", "6000"),
    ("sur", "CUCHA-XL", "25000"),
    ("sur", "TRANSP-M", "22000"),
)

# (nombre, email, telefono, direccion)
CLIENTES = (
    ("Martina Lopez", "martina.lopez@mail.com", "351-2345678", "Av Colon 1234, Cordoba"),
    ("Diego Ramirez", "diego.ramirez@mail.com", "351-8765432", "Belgrano 567, Cordoba"),
    ("Sofia Fernandez", "sofia.fernandez@mail.com", "351-4567890", "San Martin 890, Villa Maria"),
    ("Camila Torres", "camila.torres@mail.com", "351-3456789", "Rivadavia 234, Rio Cuarto"),
    ("Lucas Garcia", "lucas.garcia@mail.com", "351-5678901", "Mitre 678, Cordoba"),
    ("Valentina Sosa", "valentina.sosa@mail.com", "351-6789012", "Alberdi 345, Alta Gracia"),
    ("Pedro Gomez", "pedro.gomez@mail.com", "351-7890123", "Sarmiento 789, Jesus Maria"),
    ("Lucia Herrera", "lucia.herrera@mail.com", "351-8901234", "Laprida 456, Cordoba"),
)

# Pedidos: (distribuidora, [(sku, cantidad)], recibir)
PEDIDO_RECIBIDO = ("higiene", (("TOALLITAS-50U", 20), ("PIEDRA-GATO-4KG", 10), ("SHAMPOO-PULGAS-500ML", 10)))
PEDIDO_PENDIENTE = ("petfood", (("RC-MINI-10KG", 10), ("RC-MINI-3KG", 6)))

EFECTIVO = (("efectivo", 100),)
TRANSFERENCIA = (("transferencia", 100),)
TARJETA = (("tarjeta", 100),)

# (dias_atras, vendedor, cliente, [(sku, cantidad)], pagos[(metodo, porcentaje)])
# Los dias_atras > 0 se imputan al dia local correspondiente; 0 = hoy (ahora).
VENTAS_ANTES_DEL_PEDIDO = (
    (6, "mostrador", None, (("RC-MINI-3KG", 1), ("SNACK-HUESO-500G", 2)), EFECTIVO),
    (6, "duena", 0, (("PROPLAN-AD-15KG", 1),), TRANSFERENCIA),
    (5, "mostrador", None, (("PELOTA-01", 2), ("SOGA-DENTAL", 1)), EFECTIVO),
    (5, "mostrador", 1, (("RC-MINI-10KG", 1), ("GALLETA-PERRO-1KG", 2)), (("efectivo", 60), ("tarjeta", 40))),
    (4, "duena", 2, (("CUCHA-XL", 1), ("PLATO-ACERO", 1)), TARJETA),
    (3, "mostrador", None, (("VIT-60C", 2), ("ANTIPAR-10KG", 1)), EFECTIVO),
    (3, "mostrador", 3, (("RC-MINI-10KG", 3), ("COLLAR-NYLON-M", 1)), TRANSFERENCIA),
    (
        2, "mostrador", None,
        (("WHISKAS-GATO-10KG", 1), ("PIEDRA-GATO-4KG", 2), ("TOALLITAS-50U", 3)),
        (("efectivo", 50), ("transferencia", 50)),
    ),
    (2, "duena", 4, (("TRANSP-M", 1), ("RATON-CATNIP", 2)), TARJETA),
    (1, "mostrador", 0, (("SHAMPOO-PULGAS-500ML", 1), ("TOALLITAS-50U", 2)), EFECTIVO),
    (1, "mostrador", None, (("VIT-60C", 2), ("CUCHA-XL", 1)), EFECTIVO),
    (1, "duena", 5, (("RC-MINI-3KG", 2), ("SNACK-HUESO-500G", 3)), TRANSFERENCIA),
)
VENTAS_HOY = (
    (0, "mostrador", None, (("RC-MINI-3KG", 1), ("GALLETA-PERRO-1KG", 1)), EFECTIVO),
    (0, "mostrador", 1, (("PROPLAN-AD-15KG", 1), ("CORREA-RETR-5M", 1)), (("efectivo", 50), ("tarjeta", 50))),
    (0, "duena", None, (("CUCHA-XL", 1), ("PELOTA-01", 1)), TRANSFERENCIA),
    (0, "mostrador", None, (("TRANSP-M", 3), ("VIT-60C", 1)), EFECTIVO),
)
# Venta confirmada y luego anulada por la duena (devuelve el stock).
VENTA_ANULADA = (
    0,
    "mostrador",
    3,
    (("PELOTA-01", 1), ("SOGA-DENTAL", 1)),
    EFECTIVO,
    "Error de carga: el cliente se arrepintio",
)

HORAS_DEL_DIA = (10, 11, 12, 16, 17, 18, 19)


def _entorno_actual(env: str | None) -> str:
    if env is not None:
        return env
    from app.core.config import get_settings

    return get_settings().env


def _leer_passwords(owner: str | None, mostrador: str | None) -> tuple[str, str]:
    """Passwords por argumento o variable de entorno; sin defaults."""
    owner = owner or os.environ.get(OWNER_ENV)
    mostrador = mostrador or os.environ.get(MOSTRADOR_ENV)
    faltantes = [
        nombre
        for nombre, valor in ((OWNER_ENV, owner), (MOSTRADOR_ENV, mostrador))
        if not valor
    ]
    if faltantes:
        raise SystemExit(
            f"Faltan variables de entorno: {', '.join(faltantes)}. "
            "Definilas con las contrasenas de los usuarios demo y reintenta; "
            "no se usa ninguna credencial por defecto."
        )
    return owner, mostrador  # type: ignore[return-value]


def _asegurar_usuarios(factory, owner_password: str, mostrador_password: str):
    """Duena (via run_seed) y mostrador, get-or-create sin pisar passwords."""
    from app.core.security import hash_password
    from app.models import Usuario
    from scripts.seed import OWNER_EMAIL, run_seed

    run_seed(session_factory=factory, owner_password=owner_password)
    with factory() as session:
        if session.query(Usuario).filter_by(email=MOSTRADOR_EMAIL).one_or_none() is None:
            session.add(
                Usuario(
                    email=MOSTRADOR_EMAIL,
                    password_hash=hash_password(mostrador_password),
                    rol="mostrador",
                )
            )
            session.commit()
    return OWNER_EMAIL


def _instante_local(dias_atras: int, indice: int, zona: ZoneInfo, ahora: datetime) -> datetime:
    """Instante UTC dentro del dia local `hoy - dias_atras` (hora variada)."""
    dia: date = ahora.astimezone(zona).date() - timedelta(days=dias_atras)
    hora = HORAS_DEL_DIA[indice % len(HORAS_DEL_DIA)]
    local = datetime.combine(dia, time(hora, (indice * 7) % 60), zona)
    return local.astimezone(timezone.utc)


def _repartir(total: Decimal, pagos: tuple[tuple[str, int], ...]) -> list[tuple[str, Decimal]]:
    """Reparte `total` en pagos por porcentaje; el ultimo absorbe el resto."""
    montos: list[tuple[str, Decimal]] = []
    acumulado = Decimal(0)
    for i, (metodo, porcentaje) in enumerate(pagos):
        if i == len(pagos) - 1:
            monto = total - acumulado
        else:
            monto = (total * porcentaje / 100).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)
        acumulado += monto
        montos.append((metodo, monto))
    return montos


def _crear_datos(factory, owner_email: str) -> dict[str, int]:
    from app.models import (
        Cliente,
        Distribuidora,
        ListaPrecio,
        Producto,
        Usuario,
        Venta,
    )
    from app.schemas import (
        AnularVentaRequest,
        ConfirmarVentaRequest,
        LineaPedidoCreate,
        LineaVentaIn,
        PagoVentaIn,
        PedidoCreate,
        VentaCreate,
    )
    from app.core.config import get_settings
    from app.services import compras, ventas
    from app.services.stock import aplicar_movimiento

    zona = ZoneInfo(get_settings().reportes_tz)
    ahora = datetime.now(timezone.utc)

    with factory() as db:
        usuarios = {
            "duena": db.query(Usuario).filter_by(email=owner_email).one(),
            "mostrador": db.query(Usuario).filter_by(email=MOSTRADOR_EMAIL).one(),
        }
        duena = usuarios["duena"]

        distribuidoras: dict[str, Distribuidora] = {}
        for clave, nombre, contacto, cuit, condiciones in DISTRIBUIDORAS:
            d = Distribuidora(nombre=nombre, contacto=contacto, cuit=cuit, condiciones=condiciones)
            db.add(d)
            distribuidoras[clave] = d
        db.flush()

        productos: dict[str, Producto] = {}
        # El SKU ancla se crea ultimo: marca "seed completo" para la idempotencia.
        orden = sorted(PRODUCTOS, key=lambda p: p[0] == SKU_ANCLA)
        for sku, nombre, marca, categoria, unidad, costo, margen, _, minimo, dist in orden:
            p = Producto(
                sku=sku,
                nombre=nombre,
                marca=marca,
                categoria=categoria,
                unidad=unidad,
                costo=Decimal(costo),
                margen_pct=Decimal(margen),
                stock_actual=0,
                stock_minimo=minimo,
                distribuidora_default_id=distribuidoras[dist].id,
            )
            db.add(p)
            productos[sku] = p
        db.flush()

        for clave, sku, costo in LISTAS:
            db.add(
                ListaPrecio(
                    distribuidora_id=distribuidoras[clave].id,
                    producto_id=productos[sku].id,
                    costo=Decimal(costo),
                )
            )

        clientes: list[Cliente] = []
        for nombre, email, telefono, direccion in CLIENTES:
            c = Cliente(nombre=nombre, email=email, telefono=telefono, direccion=direccion)
            db.add(c)
            clientes.append(c)
        db.commit()

        # Stock inicial: apertura con su movimiento (RN-ST-03).
        for fila in PRODUCTOS:
            sku, inicial = fila[0], fila[7]
            if inicial > 0:
                aplicar_movimiento(
                    db,
                    productos[sku].id,
                    inicial,
                    "apertura",
                    duena,
                    motivo="Stock inicial (demo)",
                )
        db.commit()

        contador = {"ventas": 0}

        def _vender(dias_atras, vendedor, cliente_idx, lineas, pagos):
            usuario = usuarios[vendedor]
            borrador, _ = ventas.crear_venta(
                db,
                VentaCreate(
                    idempotency_key=str(uuid.uuid4()),
                    cliente_id=None if cliente_idx is None else clientes[cliente_idx].id,
                    lineas=[
                        LineaVentaIn(producto_id=productos[sku].id, cantidad=cant)
                        for sku, cant in lineas
                    ],
                ),
                usuario,
            )
            venta_id = borrador.id
            confirmada = ventas.confirmar_venta(
                db,
                venta_id,
                ConfirmarVentaRequest(
                    pagos=[
                        PagoVentaIn(metodo=metodo, monto=monto)
                        for metodo, monto in _repartir(Decimal(str(borrador.total)), pagos)
                    ]
                ),
                usuario,
            )
            if dias_atras > 0:
                instante = _instante_local(dias_atras, contador["ventas"], zona, ahora)
                db.execute(
                    update(Venta)
                    .where(Venta.id == venta_id)
                    .values(created_at=instante, confirmada_at=instante),
                    execution_options={"synchronize_session": False},
                )
                db.commit()
            contador["ventas"] += 1
            return confirmada

        for venta in VENTAS_ANTES_DEL_PEDIDO:
            _vender(*venta)

        # Pedido recibido (actualiza costos y stock) y pedido pendiente.
        dist_clave, lineas = PEDIDO_RECIBIDO
        recibido = compras.crear_pedido(
            db,
            PedidoCreate(
                distribuidora_id=distribuidoras[dist_clave].id,
                lineas=[
                    LineaPedidoCreate(producto_id=productos[sku].id, cantidad=cant)
                    for sku, cant in lineas
                ],
                notas="Reposicion semanal (demo)",
            ),
            duena,
        )
        compras.recibir_pedido(db, recibido.id, duena)

        dist_clave, lineas = PEDIDO_PENDIENTE
        compras.crear_pedido(
            db,
            PedidoCreate(
                distribuidora_id=distribuidoras[dist_clave].id,
                lineas=[
                    LineaPedidoCreate(producto_id=productos[sku].id, cantidad=cant)
                    for sku, cant in lineas
                ],
                notas="Pedido en camino (demo)",
            ),
            duena,
        )

        for venta in VENTAS_HOY:
            _vender(*venta)

        *args_anulada, motivo = VENTA_ANULADA
        anulada = _vender(*args_anulada)
        ventas.anular_venta(db, anulada.id, AnularVentaRequest(motivo=motivo), duena)

        return {
            "productos": len(PRODUCTOS),
            "distribuidoras": len(DISTRIBUIDORAS),
            "clientes": len(CLIENTES),
            "ventas": contador["ventas"],
        }


def run_seed_demo(
    session_factory=None,
    owner_password: str | None = None,
    mostrador_password: str | None = None,
    env: str | None = None,
) -> dict:
    """Carga el seed demo; devuelve un resumen. Idempotente."""
    entorno = _entorno_actual(env)
    if entorno not in ENVS_PERMITIDOS:
        raise SystemExit(
            f"seed_demo solo corre con ENV=dev o ENV=test (ENV={entorno!r}); "
            "no se modifico la base."
        )
    owner_pwd, mostrador_pwd = _leer_passwords(owner_password, mostrador_password)

    from app.core.db import SessionLocal
    from app.models import Producto

    factory = session_factory or SessionLocal
    owner_email = _asegurar_usuarios(factory, owner_pwd, mostrador_pwd)

    with factory() as session:
        existente = session.query(Producto).filter_by(sku=SKU_ANCLA).one_or_none()
    if existente is not None:
        return {
            "owner_email": owner_email,
            "mostrador_email": MOSTRADOR_EMAIL,
            "datos_creados": False,
        }

    resumen = _crear_datos(factory, owner_email)
    return {
        "owner_email": owner_email,
        "mostrador_email": MOSTRADOR_EMAIL,
        "datos_creados": True,
        **resumen,
    }


def main() -> None:
    resumen = run_seed_demo()
    if resumen["datos_creados"]:
        print(
            "seed_demo ok: "
            f"productos={resumen['productos']} distribuidoras={resumen['distribuidoras']} "
            f"clientes={resumen['clientes']} ventas={resumen['ventas']} "
            f"usuarios={resumen['owner_email']}, {resumen['mostrador_email']}"
        )
    else:
        print("seed_demo: datos demo ya cargados (usuarios verificados, nada duplicado)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        print(f"seed_demo failed: {exc.code}", file=sys.stderr)
        raise
