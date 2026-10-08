/** Formato compartido por el comprobante, el listado y el detalle de ventas. */
import type { MetodoPagoVenta } from "@/shared/api/types";

/** Numero corto de venta (D11): primeros 8 caracteres del id, en mayusculas. */
export function numeroCorto(id: string): string {
  return id.slice(0, 8).toUpperCase();
}

const FECHA_HORA = new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" });

/** Fecha y hora en la zona del navegador: "01/10/26, 12:30". */
export function formatFechaHora(iso: string): string {
  return FECHA_HORA.format(new Date(iso));
}

export const METODO_LABEL: Record<MetodoPagoVenta, string> = {
  efectivo: "Efectivo",
  transferencia: "Transferencia",
  tarjeta: "Tarjeta",
  mp: "Mercado Pago",
};
