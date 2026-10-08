/**
 * Flujo de cobro idempotente (D9): borrador -> sincronizar total -> confirmar.
 * Sin React: lee y escribe el carrito en `useCartStore` y devuelve un resultado
 * tipado que la UI traduce a mensajes.
 */
import type { PagoDraft } from "@/features/pos/payments";
import { useCartStore } from "@/features/pos/useCartStore";
import { apiFetch } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import type { PagoVentaInput, Venta, VentaCreate } from "@/shared/api/types";
import { centsToApi, toCents } from "@/shared/lib/money";

export type ResultadoCobro =
  | { tipo: "ok"; venta: Venta }
  /** El servidor calculo otro total: precios actualizados, hay que reconfirmar los pagos. */
  | { tipo: "precio-cambio"; totalCents: number }
  /** 409 con faltantes: las lineas ya quedaron marcadas en el carrito. */
  | { tipo: "faltantes" }
  | {
      tipo: "error";
      mensaje: string;
      status: number;
      /** Red/5xx: se puede reenviar lo mismo (misma clave, mismo id, mismos pagos). */
      reintentable: boolean;
      /** 404 de cliente/producto: conviene refrescar datos antes de seguir. */
      refrescar: boolean;
    };

interface OpcionesCobro {
  /** Reenvia los pagos del intento anterior en lugar de los de pantalla. */
  reintento?: boolean;
}

export function pagosParaApi(pagos: readonly Pick<PagoDraft, "metodo" | "montoCents">[]): PagoVentaInput[] {
  return pagos.map((p) => ({ metodo: p.metodo, monto: centsToApi(p.montoCents) }));
}

function esReintentable(error: ApiError): boolean {
  return error.status === 0 || error.status >= 500;
}

function traducirError(error: unknown): ResultadoCobro {
  if (error instanceof ApiError) {
    if (error.status === 409 && error.faltantes !== undefined && error.faltantes.length > 0) {
      const store = useCartStore.getState();
      store.applyFaltantes(error.faltantes);
      // No es un corte de red: al reabrir el cobro no hay nada que "reintentar" con los mismos pagos.
      store.patchCheckout({ pagos: undefined });
      return { tipo: "faltantes" };
    }
    const reintentable = esReintentable(error);
    if (!reintentable) useCartStore.getState().patchCheckout({ pagos: undefined });
    return {
      tipo: "error",
      mensaje: error.message,
      status: error.status,
      reintentable,
      refrescar: error.status === 404,
    };
  }
  return { tipo: "error", mensaje: "No se pudo completar la venta", status: 0, reintentable: true, refrescar: false };
}

async function crearBorrador(): Promise<Venta> {
  const { lineas, cliente, prepareCheckout, patchCheckout } = useCartStore.getState();
  const checkout = prepareCheckout();
  const body: VentaCreate = {
    idempotency_key: checkout.idempotencyKey,
    cliente_id: cliente?.id ?? null,
    lineas: lineas.map((l) => ({ producto_id: l.productoId, cantidad: l.cantidad })),
  };
  const venta = await apiFetch<Venta>("/ventas", { method: "POST", body });
  patchCheckout({ ventaId: venta.id });
  return venta;
}

/**
 * Ejecuta el cobro. Reutiliza el borrador ya creado (`checkout.ventaId`) si el carrito no cambio,
 * de modo que un reintento tras un corte de red nunca duplica la venta.
 */
export async function cobrarVenta(pagos: readonly PagoDraft[], opciones: OpcionesCobro = {}): Promise<ResultadoCobro> {
  try {
    const store = useCartStore.getState();
    let checkout = store.prepareCheckout();

    if (checkout.ventaId === undefined) {
      const borrador = await crearBorrador();
      if (toCents(borrador.total) !== store.total()) {
        useCartStore.getState().syncPrecios(borrador.lineas);
        return { tipo: "precio-cambio", totalCents: toCents(borrador.total) };
      }
      checkout = useCartStore.getState().prepareCheckout();
    }

    const ventaId = checkout.ventaId;
    if (ventaId === undefined) throw new ApiError(0, "No se pudo crear la venta");
    const enviar = opciones.reintento === true && checkout.pagos !== undefined ? checkout.pagos : pagosParaApi(pagos);
    useCartStore.getState().patchCheckout({ pagos: enviar });
    const venta = await apiFetch<Venta>(`/ventas/${ventaId}/confirmar`, { method: "POST", body: { pagos: enviar } });
    return { tipo: "ok", venta };
  } catch (error) {
    return traducirError(error);
  }
}
