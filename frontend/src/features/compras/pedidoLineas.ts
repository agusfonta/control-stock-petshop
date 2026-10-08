import { type Money, toCents } from "@/shared/lib/money";
import type { StockItem } from "@/shared/api/types";

/** Tope de lineas por pedido que acepta la API. */
const MAX_LINEAS_PEDIDO = 100;

/** Linea de un pedido en armado: solo producto y cantidad (el costo lo fija el servidor). */
export interface LineaBorrador {
  producto_id: string;
  cantidad: number;
}

/** Cantidad entera mayor a cero. */
export function cantidadValida(cantidad: number): boolean {
  return Number.isInteger(cantidad) && cantidad > 0;
}

/** Agrega un producto; si ya esta, suma a su linea (nunca hay productos repetidos). */
export function agregarLinea(lineas: LineaBorrador[], productoId: string, cantidad = 1): LineaBorrador[] {
  if (!cantidadValida(cantidad)) return lineas;
  if (lineas.some((l) => l.producto_id === productoId)) {
    return lineas.map((l) => (l.producto_id === productoId ? { ...l, cantidad: l.cantidad + cantidad } : l));
  }
  return [...lineas, { producto_id: productoId, cantidad }];
}

/** Cambia la cantidad tal cual; un valor invalido se conserva para que la UI lo marque. */
export function setCantidad(lineas: LineaBorrador[], productoId: string, cantidad: number): LineaBorrador[] {
  return lineas.map((l) => (l.producto_id === productoId ? { ...l, cantidad } : l));
}

export function quitarLinea(lineas: LineaBorrador[], productoId: string): LineaBorrador[] {
  return lineas.filter((l) => l.producto_id !== productoId);
}

/** Distribuidora elegida, 1 a 100 lineas, todas con cantidad valida y sin productos repetidos. */
export function puedeEnviarPedido(distribuidoraId: string, lineas: LineaBorrador[]): boolean {
  if (distribuidoraId === "" || lineas.length === 0 || lineas.length > MAX_LINEAS_PEDIDO) return false;
  const ids = new Set(lineas.map((l) => l.producto_id));
  return ids.size === lineas.length && lineas.every((l) => cantidadValida(l.cantidad));
}

export interface Sugerencia {
  producto: StockItem;
  bajoMinimo: boolean;
  /** El producto figura en la lista de precios de la distribuidora elegida. */
  enLista: boolean;
  cantidadSugerida: number;
}

interface SugerirParams {
  /** Productos de la lista de precios de la distribuidora. */
  lista: StockItem[];
  /** Productos bajo el stock minimo (`GET /stock/alertas`). */
  bajoMinimo: StockItem[];
  yaEnPedido: string[];
}

/** Reponer hasta el doble del minimo, como minimo una unidad. */
function cantidadSugerida(p: StockItem): number {
  return Math.max(1, p.stock_minimo * 2 - p.stock_actual);
}

/** Productos de la lista + bajo minimo, sin los ya pedidos; los bajo minimo (mas urgentes) primero. */
export function sugerirProductos({ lista, bajoMinimo, yaEnPedido }: SugerirParams): Sugerencia[] {
  const excluidos = new Set(yaEnPedido);
  const porId = new Map<string, Sugerencia>();
  for (const producto of lista) {
    porId.set(producto.id, { producto, bajoMinimo: producto.bajo_minimo, enLista: true, cantidadSugerida: cantidadSugerida(producto) });
  }
  for (const producto of bajoMinimo) {
    const previa = porId.get(producto.id);
    porId.set(producto.id, {
      producto,
      bajoMinimo: true,
      enLista: previa?.enLista ?? false,
      cantidadSugerida: cantidadSugerida(producto),
    });
  }
  return [...porId.values()]
    .filter((s) => !excluidos.has(s.producto.id))
    .sort((a, b) => {
      if (a.bajoMinimo !== b.bajoMinimo) return a.bajoMinimo ? -1 : 1;
      if (a.bajoMinimo) return a.producto.stock_actual - b.producto.stock_actual;
      return a.producto.nombre.localeCompare(b.producto.nombre, "es");
    });
}

/** Total estimado en centavos: cantidad x costo por linea (lineas sin costo conocido suman 0). */
export function totalEstimadoCents(lineas: LineaBorrador[], costos: Map<string, Money>): number {
  return lineas.reduce((acc, l) => {
    const costo = costos.get(l.producto_id);
    return costo === undefined ? acc : acc + l.cantidad * toCents(costo);
  }, 0);
}
