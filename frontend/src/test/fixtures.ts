import type { Cliente, Me, Producto } from "@/shared/api/types";

/** Datos de ejemplo compartidos por los tests (el demo real vive en backend/scripts/seed_demo.py). */
export const duena: Me = { id: "u-duena", email: "duena@petshop.local", rol: "duena", activo: true };
export const mostrador: Me = { id: "u-mostrador", email: "mostrador@petshop.local", rol: "mostrador", activo: true };

const FECHA = "2026-10-01T12:00:00Z";

export function makeProducto(overrides: Partial<Producto> = {}): Producto {
  return {
    id: "p-1",
    sku: "RC-MINI-3KG",
    nombre: "Royal Canin Mini Adult 3 kg",
    marca: "Royal Canin",
    categoria: "Alimento perro",
    unidad: "bolsa",
    costo: "18000.00",
    margen_pct: "0.35",
    precio_venta: "24300.00",
    stock_actual: 10,
    stock_minimo: 3,
    distribuidora_default_id: null,
    activo: true,
    created_at: FECHA,
    updated_at: FECHA,
    ...overrides,
  };
}

export function makeCliente(overrides: Partial<Cliente> = {}): Cliente {
  return {
    id: "c-1",
    nombre: "Ana Perez",
    telefono: null,
    email: null,
    direccion: null,
    activo: true,
    created_at: FECHA,
    updated_at: FECHA,
    ...overrides,
  };
}

/** Respuesta paginada de la API alrededor de una lista de items. */
export function paginated<T>(items: T[], page = 1, pageSize = 20): {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
} {
  return {
    items,
    total: items.length,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(items.length / pageSize),
  };
}
