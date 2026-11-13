# Spec Delta

## MODIFIED Requirements

### Requirement: Seed de demostración

The system SHALL incluir un seed demo idempotente, ejecutable solo con `ENV` `dev`, `test` o `staging` (este último para la demo publicada, nunca para datos reales), que crea: usuario dueña y usuario mostrador; al menos 15 productos activos de distintas categorías con costo, margen, stock y mínimo (incluyendo algunos bajo mínimo y uno sin stock); al menos 3 distribuidoras con listas de precios que se superponen en algunos productos; al menos 6 clientes; un pedido recibido y uno pendiente; y ventas confirmadas distribuidas en los últimos 7 días (incluida al menos una hoy y una anulada) con pagos en efectivo, transferencia y tarjeta, de modo que todos los reportes muestren datos. Todo cambio de stock del seed SHALL quedar registrado con su movimiento. Las contraseñas de los usuarios SHALL leerse de variables de entorno (sin valores por defecto en el código) y los valores de prueba SHALL figurar solo en archivos de ejemplo de configuración y en el compose de desarrollo.

#### Scenario: Seed con datos para reportes

- **WHEN** se ejecuta el seed demo sobre una base vacía y la dueña abre Reportes
- **THEN** Ventas del día, Más vendidos, Reposición y Márgenes muestran datos no vacíos

#### Scenario: Seed sin contraseña configurada

- **WHEN** se ejecuta el seed demo sin las variables de contraseña definidas
- **THEN** falla con un mensaje que nombra las variables faltantes y no crea usuarios

#### Scenario: Seed bloqueado fuera de desarrollo

- **WHEN** se ejecuta el seed demo con `ENV=prod`
- **THEN** se niega a correr y no modifica la base

#### Scenario: Seed permitido en staging

- **WHEN** se ejecuta el seed demo con `ENV=staging` y las variables de contraseña definidas
- **THEN** crea los usuarios y los datos demo, y una segunda ejecución no duplica nada ni cambia las contraseñas
