/**
 * Store del carrito (D8): en memoria, sobrevive a la navegacion entre pantallas
 * pero no a una recarga; se vacia al cerrar sesion. Delega la logica en `cart.ts`.
 */
import { create } from "zustand";
import { registerLogoutCleanup } from "@/features/auth/session";
import {
  type Cart,
  addProduct as addProductPure,
  applyFaltantes as applyFaltantesPure,
  cartSignature,
  clampToDisponible as clampPure,
  removeLine as removeLinePure,
  setQty as setQtyPure,
  syncPrecios as syncPreciosPure,
  totalCents,
} from "@/features/pos/cart";
import type { Cliente, Faltante, LineaVenta, PagoVentaInput, Producto } from "@/shared/api/types";

/** Intento de cobro en curso: `idempotencyKey` se reutiliza mientras el contenido no cambie (D9). */
interface CheckoutState {
  signature: string;
  idempotencyKey: string;
  /** Id del borrador ya creado en el servidor (para reintentar la confirmacion sin duplicar). */
  ventaId?: string;
  /** Pagos enviados en el ultimo intento (el reintento reenvia los mismos). */
  pagos?: PagoVentaInput[];
}

interface CartStoreState {
  lineas: Cart;
  cliente: Cliente | null;
  checkout: CheckoutState | null;
  /** Devuelve el aviso (`Solo hay N unidades`, `Sin stock`) o `null`. */
  addProduct: (producto: Producto, qty?: number) => string | null;
  setQty: (productoId: string, qty: number) => string | null;
  removeLine: (productoId: string) => void;
  setCliente: (cliente: Cliente | null) => void;
  applyFaltantes: (faltantes: readonly Faltante[]) => void;
  /** Toma los precios unitarios del borrador del servidor (el total definitivo es el suyo). */
  syncPrecios: (lineas: readonly Pick<LineaVenta, "producto_id" | "precio_unit">[]) => void;
  /** "Ajustar a disponible"; devuelve el aviso para mostrar. */
  clampToDisponible: () => string | null;
  total: () => number;
  /** Reutiliza `checkout` si la firma no cambio; si cambio, crea uno nuevo con otra clave. */
  prepareCheckout: () => CheckoutState;
  patchCheckout: (patch: Partial<Pick<CheckoutState, "ventaId" | "pagos">>) => void;
  resetCheckout: () => void;
  /** Vacia carrito, cliente y checkout. */
  clear: () => void;
}

const VACIO = { lineas: [] as Cart, cliente: null, checkout: null };

export const useCartStore = create<CartStoreState>()((set, get) => ({
  ...VACIO,

  addProduct(producto, qty = 1) {
    const { cart, aviso } = addProductPure(get().lineas, producto, qty);
    set({ lineas: cart });
    return aviso;
  },

  setQty(productoId, qty) {
    const { cart, aviso } = setQtyPure(get().lineas, productoId, qty);
    set({ lineas: cart });
    return aviso;
  },

  removeLine(productoId) {
    set({ lineas: removeLinePure(get().lineas, productoId) });
  },

  setCliente(cliente) {
    set({ cliente });
  },

  applyFaltantes(faltantes) {
    set({ lineas: applyFaltantesPure(get().lineas, faltantes) });
  },

  syncPrecios(lineas) {
    set({ lineas: syncPreciosPure(get().lineas, lineas) });
  },

  clampToDisponible() {
    const { cart, aviso } = clampPure(get().lineas);
    set({ lineas: cart });
    return aviso;
  },

  total: () => totalCents(get().lineas),

  prepareCheckout() {
    const { lineas, cliente, checkout } = get();
    const signature = cartSignature(lineas, cliente?.id ?? null);
    if (checkout !== null && checkout.signature === signature) return checkout;
    const nuevo: CheckoutState = { signature, idempotencyKey: crypto.randomUUID() };
    set({ checkout: nuevo });
    return nuevo;
  },

  patchCheckout(patch) {
    const { checkout } = get();
    if (checkout !== null) set({ checkout: { ...checkout, ...patch } });
  },

  resetCheckout() {
    set({ checkout: null });
  },

  clear() {
    set({ ...VACIO });
  },
}));

// El carrito no debe sobrevivir al cierre de sesion de otra persona.
registerLogoutCleanup(() => useCartStore.getState().clear());
