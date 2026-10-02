# Spec Delta — core-models

## Purpose

Persistir el catálogo base del petshop (usuarios, productos, distribuidoras y clientes) con constraints e índices reales, más la migración inicial y el seed mínimo que desbloquean auth, CRUDs y ventas.

## ADDED Requirements

### Requirement: Usuarios con rol y email único

The system SHALL persistir usuarios con id uuid, email único, hash de password, rol (`duena` o `mostrador`), flag `activo` y timestamps de auditoría (`created_at`, `updated_at`).

#### Scenario: Email duplicado rechazado

- **WHEN** se intenta persistir un segundo usuario con un email ya existente
- **THEN** el sistema rechaza la operación con error de unicidad y no crea el registro

#### Scenario: Usuario nuevo queda activo por defecto

- **WHEN** se crea un usuario sin especificar `activo`
- **THEN** el sistema lo persiste con `activo == true` y `created_at`/`updated_at` informados

### Requirement: Productos con SKU único y stock no negativo

The system SHALL persistir productos con id uuid, `sku` único, nombre, marca, categoria, unidad (`unidad`/`bolsa`/`caja`), costo, `margen_pct`, `stock_actual`, `stock_minimo`, `distribuidora_default_id` nullable y flag `activo`, con constraint `stock_actual >= 0`.

#### Scenario: Stock negativo rechazado

- **WHEN** se intenta persistir o actualizar un producto con `stock_actual < 0`
- **THEN** el sistema rechaza la operación con error de constraint y el stock almacenado no cambia

#### Scenario: SKU duplicado rechazado

- **WHEN** se intenta persistir un producto con un `sku` ya existente
- **THEN** el sistema rechaza la operación con error de unicidad

### Requirement: Precio de venta calculado automáticamente

The system SHALL garantizar `precio_venta = costo × (1 + margen_pct)` (RN-PR-01) de modo que toda lectura de precio de un producto refleje el costo y margen vigentes sin intervención manual.

#### Scenario: Precio refleja costo y margen

- **WHEN** un producto se persiste con `costo = 1000` y `margen_pct = 0.5`
- **THEN** el sistema expone `precio_venta == 1500`

#### Scenario: Cambio de costo actualiza precio sugerido

- **WHEN** se actualiza el `costo` de un producto existente a un valor mayor
- **THEN** el sistema expone un `precio_venta` mayor conforme a la fórmula, sin crear registros históricos (las ventas históricas no existen aún en este change)

### Requirement: Distribuidoras y clientes persistidos

The system SHALL persistir distribuidoras (nombre, contacto, cuit, condiciones, `activo`, auditoría) y clientes (nombre, teléfono, email, dirección, `saldo_cc` default 0, `activo`, auditoría), con `Producto.distribuidora_default_id` referenciando opcionalmente a una distribuidora.

#### Scenario: Producto sin distribuidora por defecto

- **WHEN** se crea un producto sin `distribuidora_default_id`
- **THEN** el sistema lo persiste con esa referencia en nulo y el producto queda consultable

#### Scenario: Saldo de cuenta corriente por defecto

- **WHEN** se crea un cliente sin especificar `saldo_cc`
- **THEN** el sistema lo persiste con `saldo_cc == 0`

### Requirement: Índices de búsqueda de catálogo

The system SHALL proveer índices para `sku` (único), `nombre` (búsqueda por trigramas) y `categoria` de modo que la búsqueda por código, nombre parcial y categoría use índices dedicados.

#### Scenario: Búsqueda por nombre parcial usa índice trgm

- **WHEN** se busca un producto por fragmento de `nombre` con operador de similitud
- **THEN** el sistema resuelve la consulta apoyada en el índice trgm sobre `nombre`

### Requirement: Migración inicial real y auditoría append-friendly

The system SHALL proveer la migración Alembic `0002` (hija de la anchor `0001`) que crea exactamente las tablas `usuarios`, `productos`, `distribuidoras`, `clientes` con sus constraints, índices y la extensión `pg_trgm`, y toda fila creada SHALL incluir `created_at`/`updated_at` informados.

#### Scenario: Migración crea las 4 tablas

- **WHEN** se aplica la migración `0002` sobre una base creada desde `0001`
- **THEN** existen las tablas `usuarios`, `productos`, `distribuidoras` y `clientes` con sus constraints, y el downgrade las elimina sin dejar residuos

### Requirement: Seed mínimo idempotente sin secretos hardcodeados

The system SHALL proveer un seed idempotente que deja roles `duena`/`mostrador`, un usuario dueña inicial (password tomado de env `SEED_OWNER_PASSWORD`, nunca hardcodeado), categorías base (alimentos, accesorios, higiene, farmacia) y métodos de pago base (efectivo, transferencia, MP, tarjeta), sin catálogo precargado.

#### Scenario: Seed repetido no duplica

- **WHEN** el seed se ejecuta dos veces seguidas
- **THEN** el segundo run no crea duplicados y el estado final contiene exactamente 1 usuario dueña, las 4 categorías y los 4 métodos de pago

#### Scenario: Seed sin password real en el repo

- **WHEN** se inspecciona el código del seed y su documentación
- **THEN** no existe ninguna credencial real hardcodeada y la fuente del password inicial está documentada como variable de entorno
