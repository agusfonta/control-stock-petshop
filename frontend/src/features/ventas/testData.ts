import type { LineaVenta, PagoVenta, Venta, VentaResumen } from "@/shared/api/types";

/** Datos de ejemplo de ventas para los tests de B2b. */
const FECHA = "2026-10-01T15:30:00Z";

export function makeLineaVenta(overrides: Partial<LineaVenta> = {}): LineaVenta {
  return {
    id: "lv-1",
    producto_id: "p-1",
    producto_nombre: "Royal Canin Mini Adult 3 kg",
    cantidad: 1,
    precio_unit: "3800.00",
    subtotal: "3800.00",
    ...overrides,
  };
}

export function makePagoVenta(overrides: Partial<PagoVenta> = {}): PagoVenta {
  return { id: "pg-1", metodo: "efectivo", monto: "3800.00", ref_mp: null, created_at: FECHA, ...overrides };
}

/** Venta confirmada de $ 3.800 pagada en efectivo. */
export function makeVenta(overrides: Partial<Venta> = {}): Venta {
  return {
    id: "a1b2c3d4-0000-4000-8000-000000000001",
    estado: "confirmada",
    cliente_id: null,
    usuario_id: "u-mostrador",
    total: "3800.00",
    lineas: [makeLineaVenta()],
    pagos: [makePagoVenta()],
    created_at: FECHA,
    confirmada_at: FECHA,
    confirmada_por_id: "u-mostrador",
    anulada_at: null,
    anulada_por_id: null,
    motivo_anulacion: null,
    ...overrides,
  };
}

export function makeVentaResumen(overrides: Partial<VentaResumen> = {}): VentaResumen {
  return {
    id: "a1b2c3d4-0000-4000-8000-000000000001",
    estado: "confirmada",
    cliente_id: null,
    usuario_id: "u-mostrador",
    total: "3800.00",
    created_at: FECHA,
    confirmada_at: FECHA,
    anulada_at: null,
    ...overrides,
  };
}
