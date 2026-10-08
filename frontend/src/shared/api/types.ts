/**
 * Tipos de la API escritos a mano, espejando los schemas Pydantic (D3).
 * Dinero: `Money` (numero JSON o string decimal); se convierte con `toCents`.
 */
import type { Money } from "@/shared/lib/money";

export type { Faltante } from "@/shared/api/errors";
export type { Money };

export type Rol = "duena" | "mostrador";
export type Unidad = "unidad" | "bolsa" | "caja";
export type EstadoVenta = "borrador" | "confirmada" | "anulada";
export type MetodoPagoVenta = "efectivo" | "transferencia" | "mp" | "tarjeta";
export type EstadoPedido = "pendiente" | "recibido" | "cancelado";
export type MetodoPagoDistribuidora = "efectivo" | "transferencia" | "cheque" | "otro";

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Auth
export interface Me {
  id: string;
  email: string;
  rol: Rol;
  activo: boolean;
}
export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}
export interface LoginRequest {
  email: string;
  password: string;
}

// Productos y stock
export interface Producto {
  id: string;
  sku: string;
  nombre: string;
  marca: string | null;
  categoria: string | null;
  unidad: Unidad;
  costo: Money;
  margen_pct: Money;
  precio_venta: Money;
  stock_actual: number;
  stock_minimo: number;
  distribuidora_default_id: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}
export interface ProductoCreate {
  sku: string;
  nombre: string;
  marca?: string | null;
  categoria?: string | null;
  unidad: Unidad;
  costo: string;
  margen_pct: string;
  stock_actual?: number;
  stock_minimo: number;
  distribuidora_default_id?: string | null;
}
export type ProductoUpdate = Partial<Omit<ProductoCreate, "stock_actual">>;
export interface MargenMinimoRequest {
  margen_pct?: string | null;
  stock_minimo?: number | null;
}
export interface StockItem extends Producto {
  bajo_minimo: boolean;
}
export interface AlertasStock {
  total_bajo_minimo: number;
  items: StockItem[];
}
export interface Movimiento {
  id: string;
  producto_id: string;
  tipo: "venta" | "entrada" | "ajuste" | "apertura";
  cantidad: number;
  stock_previo: number;
  stock_nuevo: number;
  ref_id: string | null;
  motivo: string | null;
  usuario_id: string;
  created_at: string;
}
export interface AjusteStockRequest {
  cantidad_delta: number;
  motivo: string;
}
export interface AjusteStockResponse {
  producto: Producto;
  movimiento: Movimiento;
}

// Distribuidoras y compras
export interface Distribuidora {
  id: string;
  nombre: string;
  contacto: string | null;
  cuit: string | null;
  condiciones: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}
export interface DistribuidoraInput {
  nombre: string;
  contacto?: string | null;
  cuit?: string | null;
  condiciones?: string | null;
}
export interface ListaPrecio {
  id: string;
  distribuidora_id: string;
  producto_id: string;
  costo: Money;
  activo: boolean;
  created_at: string;
  updated_at: string;
}
export interface CompararFila {
  distribuidora_id: string;
  distribuidora_nombre: string;
  costo: Money;
  precio_sugerido: Money;
}
export interface CompararResponse {
  producto_id: string;
  filas: CompararFila[];
}
export interface LineaPedido {
  id: string;
  producto_id: string;
  cantidad: number;
  costo_unitario: Money;
  subtotal: Money;
}
export interface Pedido {
  id: string;
  distribuidora_id: string;
  estado: EstadoPedido;
  usuario_id: string;
  notas: string | null;
  recibido_at: string | null;
  recibido_por_id: string | null;
  total_estimado: Money;
  lineas: LineaPedido[];
  created_at: string;
  updated_at: string;
}
export interface PedidoCreate {
  distribuidora_id: string;
  lineas: { producto_id: string; cantidad: number }[];
  notas?: string | null;
}
export interface PagoDistribuidora {
  id: string;
  distribuidora_id: string;
  monto: Money;
  metodo: MetodoPagoDistribuidora;
  fecha: string;
  nota: string | null;
  usuario_id: string;
  activo: boolean;
  created_at: string;
  updated_at: string;
}
export interface PagoDistribuidoraCreate {
  distribuidora_id: string;
  monto: string;
  metodo: MetodoPagoDistribuidora;
  fecha?: string;
  nota?: string | null;
}
export interface Cuenta {
  distribuidora_id: string;
  total_recibido: Money;
  total_pagado: Money;
  saldo: Money;
}

// Clientes
export interface Cliente {
  id: string;
  nombre: string;
  telefono: string | null;
  email: string | null;
  direccion: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}
export interface ClienteInput {
  nombre: string;
  telefono?: string | null;
  email?: string | null;
  direccion?: string | null;
}

// Ventas
export interface LineaVenta {
  id: string;
  producto_id: string;
  producto_nombre: string;
  cantidad: number;
  precio_unit: Money;
  subtotal: Money;
}
export interface PagoVenta {
  id: string;
  metodo: MetodoPagoVenta;
  monto: Money;
  ref_mp: string | null;
  created_at: string;
}
export interface Venta {
  id: string;
  estado: EstadoVenta;
  cliente_id: string | null;
  usuario_id: string;
  total: Money;
  lineas: LineaVenta[];
  pagos: PagoVenta[];
  created_at: string;
  confirmada_at: string | null;
  confirmada_por_id: string | null;
  anulada_at: string | null;
  anulada_por_id: string | null;
  motivo_anulacion: string | null;
}
export interface VentaResumen {
  id: string;
  estado: EstadoVenta;
  cliente_id: string | null;
  usuario_id: string;
  total: Money;
  created_at: string;
  confirmada_at: string | null;
  anulada_at: string | null;
}
export interface VentaCreate {
  idempotency_key: string;
  cliente_id?: string | null;
  lineas: { producto_id: string; cantidad: number }[];
}
export interface PagoVentaInput {
  metodo: MetodoPagoVenta;
  monto: string;
}
export interface ConfirmarVentaRequest {
  pagos: PagoVentaInput[];
}
export interface AnularVentaRequest {
  motivo: string;
}

// Reportes
export interface VentasDiaReporte {
  fecha: string;
  alcance: "todas" | "propias";
  cantidad_ventas: number;
  total_vendido: Money;
  ticket_promedio: Money;
  unidades_vendidas: number;
  por_metodo: { metodo: MetodoPagoVenta; monto: Money; cantidad_pagos: number }[];
  anuladas: { cantidad: number; total: Money };
}
export interface ProductoVendido {
  producto_id: string;
  sku: string;
  nombre: string;
  activo: boolean;
  unidades: number;
  monto: Money;
}
export interface MasVendidosReporte {
  desde: string;
  hasta: string;
  orden: "cantidad" | "monto";
  items: ProductoVendido[];
}
export interface ReposicionItem {
  producto_id: string;
  sku: string;
  nombre: string;
  stock_actual: number;
  stock_minimo: number;
  bajo_minimo: boolean;
  unidades_vendidas: number;
  venta_diaria: Money;
  cobertura_dias: number | null;
  distribuidora_default_id: string | null;
}
export interface ReposicionReporte {
  dias: number;
  cobertura_max_dias: number;
  items: ReposicionItem[];
}
export interface MargenProducto {
  producto_id: string;
  sku: string;
  nombre: string;
  unidades: number;
  ingresos: Money;
  costo: Money;
  margen_bruto: Money;
  margen_pct: Money | null;
}
export interface MargenesTotales {
  ingresos: Money;
  costo: Money;
  margen_bruto: Money;
  margen_pct: Money | null;
  lineas_sin_costo: number;
  ingresos_sin_costo: Money;
}
export interface MargenesReporte extends Paginated<MargenProducto> {
  desde: string;
  hasta: string;
  totales: MargenesTotales;
}
