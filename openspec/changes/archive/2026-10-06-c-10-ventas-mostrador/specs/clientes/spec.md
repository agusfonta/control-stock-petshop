# Spec Delta

## ADDED Requirements

### Requirement: Historial de ventas por cliente

The system SHALL exponer `GET /api/clientes/{id}/ventas`, para los roles `duena` y `mostrador`, que devuelve las ventas `confirmada` y `anulada` asociadas a ese cliente (nunca borradores), cada una con su `id`, `estado`, `total`, vendedor, fecha de creación y de confirmación, ordenadas por fecha de creación descendente y paginadas como el resto de los listados (metadata `total`, `page`, `page_size`, `total_pages`). Un `mostrador` SHALL ver solo las ventas de ese cliente que él mismo registró; la dueña ve todas. Un cliente inexistente responde `404`; un cliente dado de baja conserva su historial (`200`). Un anónimo recibe `401`.

#### Scenario: Historial con ventas confirmadas y anuladas

- **WHEN** un cliente tiene una venta confirmada, una venta anulada y un borrador, y una dueña llama a `GET /api/clientes/{id}/ventas`
- **THEN** el sistema responde `200` con las dos ventas confirmada y anulada, la más reciente primero, sin el borrador, con `total=2`

#### Scenario: Cliente sin ventas

- **WHEN** un usuario autenticado consulta el historial de un cliente sin ventas
- **THEN** el sistema responde `200` con lista vacía y `total=0`

#### Scenario: Mostrador ve solo sus ventas del cliente

- **WHEN** un cliente tiene una venta confirmada registrada por la dueña y otra registrada por un usuario `mostrador`, y ese mostrador consulta su historial
- **THEN** el sistema responde `200` solo con la venta registrada por ese mostrador

#### Scenario: Historial de cliente dado de baja

- **WHEN** una dueña consulta el historial de un cliente dado de baja que tiene ventas confirmadas
- **THEN** el sistema responde `200` con esas ventas

#### Scenario: Historial de cliente inexistente

- **WHEN** un usuario autenticado llama a `GET /api/clientes/{id-inexistente}/ventas`
- **THEN** el sistema responde `404`

#### Scenario: Historial sin autenticación

- **WHEN** un cliente anónimo llama a `GET /api/clientes/{id}/ventas`
- **THEN** el sistema responde `401`
