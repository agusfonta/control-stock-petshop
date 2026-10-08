import type { Cuenta, Distribuidora, LineaPedido, ListaPrecio, PagoDistribuidora, Pedido } from "@/shared/api/types";

/** Datos de ejemplo de distribuidoras y compras para los tests de B4. */
const FECHA = "2026-10-01T12:00:00Z";

export function makeDistribuidora(overrides: Partial<Distribuidora> = {}): Distribuidora {
  return {
    id: "d-1",
    nombre: "Distribuidora Norte",
    contacto: null,
    cuit: null,
    condiciones: null,
    activo: true,
    created_at: FECHA,
    updated_at: FECHA,
    ...overrides,
  };
}

export function makeListaPrecio(overrides: Partial<ListaPrecio> = {}): ListaPrecio {
  return {
    id: "lp-1",
    distribuidora_id: "d-1",
    producto_id: "p-1",
    costo: "18000.00",
    activo: true,
    created_at: FECHA,
    updated_at: FECHA,
    ...overrides,
  };
}

export function makeLineaPedido(overrides: Partial<LineaPedido> = {}): LineaPedido {
  return { id: "l-1", producto_id: "p-1", cantidad: 10, costo_unitario: "18000.00", subtotal: "180000.00", ...overrides };
}

export function makePedido(overrides: Partial<Pedido> = {}): Pedido {
  return {
    id: "ped-1",
    distribuidora_id: "d-1",
    estado: "pendiente",
    usuario_id: "u-duena",
    notas: null,
    recibido_at: null,
    recibido_por_id: null,
    total_estimado: "180000.00",
    lineas: [makeLineaPedido()],
    created_at: FECHA,
    updated_at: FECHA,
    ...overrides,
  };
}

export function makePago(overrides: Partial<PagoDistribuidora> = {}): PagoDistribuidora {
  return {
    id: "pg-1",
    distribuidora_id: "d-1",
    monto: "50000.00",
    metodo: "transferencia",
    fecha: "2026-10-05",
    nota: null,
    usuario_id: "u-duena",
    activo: true,
    created_at: FECHA,
    updated_at: FECHA,
    ...overrides,
  };
}

export function makeCuenta(overrides: Partial<Cuenta> = {}): Cuenta {
  return { distribuidora_id: "d-1", total_recibido: "120000.00", total_pagado: "0.00", saldo: "120000.00", ...overrides };
}
