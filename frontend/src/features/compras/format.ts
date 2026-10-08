import type { EstadoPedido, MetodoPagoDistribuidora } from "@/shared/api/types";

export const ESTADO_PEDIDO_LABEL: Record<EstadoPedido, string> = {
  pendiente: "Pendiente",
  recibido: "Recibido",
  cancelado: "Cancelado",
};

export const METODO_PAGO_LABEL: Record<MetodoPagoDistribuidora, string> = {
  efectivo: "Efectivo",
  transferencia: "Transferencia",
  cheque: "Cheque",
  otro: "Otro",
};

export const METODOS_PAGO: readonly MetodoPagoDistribuidora[] = ["efectivo", "transferencia", "cheque", "otro"];

const FECHA = new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" });
const FECHA_HORA = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** Instante ISO del servidor -> "05/10/2026" en hora local. */
export function formatFecha(iso: string): string {
  return FECHA.format(new Date(iso));
}

export function formatFechaHora(iso: string): string {
  return FECHA_HORA.format(new Date(iso));
}

/** Fecha calendario `YYYY-MM-DD` -> "05/10/2026" sin pasar por zona horaria (no corre un dia). */
export function formatDia(dia: string): string {
  const [anio, mes, d] = dia.split("-");
  return anio === undefined || mes === undefined || d === undefined ? dia : `${d}/${mes}/${anio}`;
}

/** Hoy en hora local como `YYYY-MM-DD` (valor por defecto de la fecha de un pago). */
export function hoyISO(ahora: Date = new Date()): string {
  const mes = String(ahora.getMonth() + 1).padStart(2, "0");
  const dia = String(ahora.getDate()).padStart(2, "0");
  return `${ahora.getFullYear()}-${mes}-${dia}`;
}
