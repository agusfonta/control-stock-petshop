# Discovery — Control Stock Petshop

**Fecha**: 2026-10-01
**Fuentes investigadas**: 5 competidores (ver `discovery/sources/`)

## 1. Problema que resuelve

La dueña de un petshop de un solo local maneja todo a mano con papel o Excel: ventas sin registrar sistemáticamente, stock desactualizado y sin alertas, compras a distribuidoras sin circuito ordenado. Necesita un sistema simple de mostrador que ordene venta, stock y compras sin frenar la atención.

## 2. Usuarios / roles

- **Dueña/admin**: controla stock, precios, distribuidoras, pagos/pedidos y reportes.
- **Mostrador/vendedor**: vende rápido, registra entradas, consulta stock.

Sin rol veterinario en v1, sin multi-local en v1.

## 3. Casos de uso

1. Como vendedora, quiero cobrar una venta rápido (búsqueda/código) para no frenar el mostrador.
2. Como vendedora, quiero registrar la venta con factura/ticket (ARCA) para cumplir sin salir del flujo.
3. Como dueña, quiero ver stock en tiempo real con alertas de mínimos para pedir antes de quedarme sin lo que más rota.
4. Como dueña, quiero registrar distribuidoras, entradas de stock, pagos y pedidos para ordenar el circuito de compra.
5. Como dueña, quiero un registro de clientes para historial y cuenta corriente.

## 4. Competidores / soluciones existentes

| Competidor | Problema que resuelve | Pricing | Diferenciadores |
|---|---|---|---|
| Contabilium | ERP genérico pyme (facturación, stock, compras) | No publicado en home, prueba 10 días | Cobertura regional + integraciones ecommerce |
| Datalive | Gestión gastronómica integral (POS, producción, delivery) | No publicado, venta por contacto | Vertical gastronómico (KDS, kioscos, offline+sync) |
| Trud | Gestión petshop/vet integral + IA | $40k/$60k/$100k por mes + módulos | El más completo, AFIP nativa, fraccionados y vet por módulos |
| Mi Pet Shop (GesArg) | Orden de mostrador simple para petshop | $15.000/mes ilimitado, 7 días gratis | El más simple y barato, granel + código + FE |
| VetAdmin | Clínica veterinaria + stock/ventas | u$s15-25/mes, offline u$s600 único | Profundidad clínica + opción offline |

**Notas**: Trud es el techo funcional, Mi Pet Shop el piso de precio/simplicidad. Contabilium y Datalive aportados por el usuario como referencias genéricas — solo aportan patrones (vertical específico > genérico, configuración asistida, multidispositivo). Mapa validado por el usuario.

## 5. Funcionalidades necesarias

- Registrar ventas y facturar (ticket + FE ARCA).
- Controlar stock en tiempo real con alertas de mínimos.
- Registrar distribuidoras, entradas de stock, pagos y pedidos a distribuidoras.
- Registro de clientes.
- Todo lo anterior en v1 (decisión explícita del usuario, sin recorte a 3).

## 6. Funcionalidades opcionales

- Turnos/veterinaria e historia clínica → fase 2 (explícito).
- A definir si v1 o v2: venta a granel por peso, control por lote/vencimiento, reportes avanzados, promociones/cupones, ecommerce.

## 7. Reglas de negocio

- No vender sin stock (bloquear o alertar — a definir comportamiento exacto en KB).
- Stock mínimo por producto dispara alerta/reposición.
- Precios diferenciados por distribuidora.
- Precio de venta = precio al costo × (1 + % margen configurable).
- Más reglas a añadir luego (el usuario anticipa que surgirán más; quedan como preguntas abiertas para kb-creator).

## 8. Integraciones

- ARCA facturación electrónica (riesgo principal, ver punto 10).
- Mercado Pago para cobros.
- Implícitas de mostrador: lector de código de barras, impresión de ticket (a confirmar en KB).

## 9. Restricciones

- Dispositivo: tablet del local (tiene que andar bien ahí + PC/celular).
- Offline ante corte de internet: deseable pero para v2 — tenerlo en cuenta en decisiones sin implementarlo en v1.
- Sin stack/plazo fijo declarado.

## 10. Riesgos

- **Supuesto sin probar**: que el circuito completo (ventas + stock + distribuidoras + clientes) sea usable en mostrador sin capacitación pesada.
- **Riesgo ARCA**: integración fiscal (homologación, certificados, caídas) — el usuario lo marca como preocupación top.
- **Riesgo backups**: pérdida de datos de stock/ventas sin estrategia de respaldo.
- **Riesgo despliegue**: dónde subir backend, frontend y base de datos (costos, dominios, TLS, uptime).
- **Riesgo migración**: carga inicial desde papel/Excel con datos inconsistentes.

## 11. Preguntas abiertas

- ¿Granel por peso y vencimientos por lote entran en v1 o v2?
- ¿Comportamiento exacto de "no vender sin stock" (bloqueo duro vs. alerta con override)?
- ¿Qué más reglas de negocio faltan? (el usuario anticipa más).
- Demo existente en `C:\Users\agusf\Desktop\PetShop\Animall` (FastAPI + frontend + docker): revisar como insumo en kb-creator para reutilizar lo útil sin basarse en él — no bloquea Discovery.
- Despliegue: ¿dónde se aloja cada pieza? (pasa a kb-creator como `needs_infra`).
