# Arquitectura Propuesta

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| Monolito modular | FastAPI routers por dominio | Equipo chico, costo bajo, despliegue simple |
| Transacción unitaria | Confirmar venta | Consistencia stock+pagos (RN-VT-02) |
| Outbox/jobs Redis | FE ARCA, alertas, reportes | No bloquear mostrador, reintentos |
| RBAC simple | JWT + roles | 2 roles, sin ABAC |

## Estructura de directorios

```
control-stock-petshop/
├── backend/
│   └── app/
│       ├── routers/ (auth, productos, ventas, compras, clientes, reportes)
│       ├── services/ (ventas, stock, precios, fe_arca, mp)
│       ├── models.py / schemas.py / deps.py
│       └── core/ (config, security, db)
├── frontend/
│   └── src/
│       ├── features/ (pos, stock, compras, clientes, reportes)
│       ├── shared/ + pages/
└── knowledge-base/ + openspec/
```

Arranque limpio inspirado en demo Animall, con TypeScript obligatorio en FE y `plantilla_productos.csv` reutilizable para migración.

## Seguridad

- Autenticación: JWT access corto + refresh, bcrypt.
- Autorización: RBAC dueña/mostrador, solo dueña anula y configura.
- Validación de input: Pydantic schemas estrictos, cantidades > 0.
- Secrets management: `.env` local, secrets del host en prod (ARCA certs, MP token, SECRET_KEY).

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|---|---|---|---|
| DATABASE_URL | Postgres | postgresql://... | Y |
| REDIS_URL | Colas/jobs | redis://... | N |
| SECRET_KEY | JWT | random | Y |
| ARCA_CERT/KEY | Certificados FE | path | Y |
| MP_ACCESS_TOKEN | Mercado Pago | ... | Y |
