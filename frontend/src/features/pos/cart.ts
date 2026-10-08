/**
 * Carrito del POS como funciones puras (D8). Todo en centavos enteros (D7);
 * cada funcion devuelve un carrito nuevo y, cuando recorta, un aviso para la UI.
 */
import type { Faltante, Producto } from "@/shared/api/types";
import { type Money, toCents } from "@/shared/lib/money";

export interface CartLine {
  productoId: string;
  sku: string;
  nombre: string;
  /** Precio unitario mostrado (informativo: el total definitivo lo da el servidor). */
  precioCents: number;
  cantidad: number;
  /** `stock_actual` conocido; tope de la cantidad. */
  stock: number;
  /** Stock informado por un 409 (D9): marca la linea hasta "Ajustar a disponible". */
  disponible?: number;
}

export type Cart = readonly CartLine[];

export interface CartResult {
  cart: Cart;
  /** Mensaje para mostrar (`Solo hay N unidades`, `Sin stock`...) o `null`. */
  aviso: string | null;
}

function avisoStock(stock: number): string {
  return `Solo hay ${stock} ${stock === 1 ? "unidad" : "unidades"}`;
}

/** Suma `qty` unidades; refresca precio y stock con el producto recien consultado (descarta marcas de faltante). */
export function addProduct(cart: Cart, producto: Producto, qty = 1): CartResult {
  const stock = producto.stock_actual;
  if (stock <= 0) return { cart, aviso: "Sin stock" };

  const precioCents = toCents(producto.precio_venta);
  const existente = cart.find((l) => l.productoId === producto.id);
  const pedida = (existente?.cantidad ?? 0) + Math.max(1, Math.trunc(qty));
  const cantidad = Math.min(pedida, stock);
  const aviso = pedida > stock ? avisoStock(stock) : null;
  const linea: CartLine = {
    productoId: producto.id,
    sku: producto.sku,
    nombre: producto.nombre,
    precioCents,
    cantidad,
    stock,
  };
  if (existente === undefined) return { cart: [...cart, linea], aviso };
  return { cart: cart.map((l) => (l.productoId === producto.id ? linea : l)), aviso };
}

/** Fija la cantidad de una linea: entera, entre 1 y `stock`. Quitar es `removeLine`. */
export function setQty(cart: Cart, productoId: string, qty: number): CartResult {
  let aviso: string | null = null;
  const next = cart.map((linea) => {
    if (linea.productoId !== productoId) return linea;
    const pedida = Number.isFinite(qty) ? Math.trunc(qty) : 1;
    let cantidad = Math.max(1, pedida);
    if (cantidad > linea.stock) {
      cantidad = linea.stock;
      aviso = avisoStock(linea.stock);
    }
    // La marca de faltante sigue mientras la cantidad supere lo disponible.
    if (linea.disponible !== undefined && cantidad > linea.disponible) return { ...linea, cantidad };
    const { disponible: _resuelta, ...resto } = linea;
    return { ...resto, cantidad };
  });
  return { cart: next, aviso };
}

export function removeLine(cart: Cart, productoId: string): Cart {
  return cart.filter((l) => l.productoId !== productoId);
}

export function lineSubtotalCents(linea: CartLine): number {
  return linea.precioCents * linea.cantidad;
}

export function totalCents(cart: Cart): number {
  return cart.reduce((acc, l) => acc + lineSubtotalCents(l), 0);
}

export function unidadesTotales(cart: Cart): number {
  return cart.reduce((acc, l) => acc + l.cantidad, 0);
}

/** Marca `disponible` en las lineas que el servidor informo como faltantes (409). */
export function applyFaltantes(cart: Cart, faltantes: readonly Faltante[]): Cart {
  return cart.map((linea) => {
    const f = faltantes.find((x) => x.producto_id === linea.productoId);
    return f === undefined ? linea : { ...linea, disponible: f.disponible };
  });
}

/** "Ajustar a disponible": recorta a lo informado, quita lo agotado y limpia las marcas. */
export function clampToDisponible(cart: Cart): CartResult {
  let ajustadas = 0;
  const next: CartLine[] = [];
  for (const linea of cart) {
    if (linea.disponible === undefined) {
      next.push(linea);
      continue;
    }
    ajustadas += 1;
    const { disponible, ...resto } = linea;
    if (disponible <= 0) continue;
    next.push({ ...resto, cantidad: Math.min(linea.cantidad, disponible), stock: disponible });
  }
  const aviso =
    ajustadas === 0 ? null : `Ajustamos ${ajustadas === 1 ? "1 producto" : `${ajustadas} productos`} al stock disponible`;
  return { cart: next, aviso };
}

/** Lleva a las lineas el precio unitario que devolvio el servidor al crear el borrador (D9, paso 2). */
export function syncPrecios(cart: Cart, lineas: readonly { producto_id: string; precio_unit: Money }[]): Cart {
  return cart.map((linea) => {
    const del_servidor = lineas.find((l) => l.producto_id === linea.productoId);
    return del_servidor === undefined ? linea : { ...linea, precioCents: toCents(del_servidor.precio_unit) };
  });
}

/** Firma del contenido (lineas ordenadas por producto + cliente): decide si se reutiliza la idempotency_key (D9). */
export function cartSignature(cart: Cart, clienteId: string | null): string {
  const lineas = [...cart]
    .sort((a, b) => (a.productoId < b.productoId ? -1 : a.productoId > b.productoId ? 1 : 0))
    .map((l) => `${l.productoId}:${l.cantidad}`)
    .join(",");
  return `${clienteId ?? "-"}|${lineas}`;
}
