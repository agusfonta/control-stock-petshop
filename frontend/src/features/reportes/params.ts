/** Fechas y parametros de los reportes: todo `YYYY-MM-DD` local, bordes inclusive (spec C-14). */

const MAX_DIAS_PERIODO = 366;

export interface Periodo {
  /** `""` = que decida el servidor (ultimos 30 dias). */
  desde: string;
  hasta: string;
}

const DIA_MS = 24 * 60 * 60 * 1000;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Fecha local del navegador como `YYYY-MM-DD` (nunca la fecha UTC). */
export function toIsoDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseIso(iso: string): number {
  const [y = 0, m = 1, d = 1] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

/** Dias que abarca el periodo, ambos bordes inclusive. */
export function diasDelPeriodo(desde: string, hasta: string): number {
  return Math.round((parseIso(hasta) - parseIso(desde)) / DIA_MS) + 1;
}

/** Query de un periodo: los bordes vacios se omiten. */
export function periodoQuery(p: Periodo): { desde: string | undefined; hasta: string | undefined } {
  return { desde: p.desde === "" ? undefined : p.desde, hasta: p.hasta === "" ? undefined : p.hasta };
}

/** Mensaje de error si el periodo no pasaria la validacion del servidor; `null` si esta bien. */
export function validarPeriodo(p: Periodo): string | null {
  if (p.desde === "" || p.hasta === "") return null;
  if (p.desde > p.hasta) return "La fecha “Desde” no puede ser posterior a “Hasta”.";
  if (diasDelPeriodo(p.desde, p.hasta) > MAX_DIAS_PERIODO) {
    return `El período no puede superar ${MAX_DIAS_PERIODO} días.`;
  }
  return null;
}

export type PeriodoPreset = "7d" | "30d" | "mes";

export const PRESET_LABEL: Record<PeriodoPreset, string> = {
  "7d": "Últimos 7 días",
  "30d": "Últimos 30 días",
  mes: "Este mes",
};

/** Periodos rapidos que terminan hoy. */
export function periodoPreset(preset: PeriodoPreset, hoy: Date = new Date()): Periodo {
  const hasta = toIsoDate(hoy);
  if (preset === "mes") {
    return { desde: toIsoDate(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), hasta };
  }
  const dias = preset === "7d" ? 7 : 30;
  return { desde: toIsoDate(new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - (dias - 1))), hasta };
}

/** `2026-10-07` -> `7/10/2026` (es-AR), sin desfase por zona horaria. */
export function fechaLegible(iso: string): string {
  return new Intl.DateTimeFormat("es-AR", { timeZone: "UTC" }).format(new Date(parseIso(iso)));
}

/** Destino de "Crear pedido" desde Reposicion: `/compras` con la distribuidora por defecto y el producto. */
export function pedidoUrl(item: { producto_id: string; distribuidora_default_id: string | null }): string {
  const query = new URLSearchParams({ nuevo: "1" });
  if (item.distribuidora_default_id !== null) query.set("distribuidora", item.distribuidora_default_id);
  query.set("producto", item.producto_id);
  return `/compras?${query.toString()}`;
}

/** Venta diaria (unidades por dia) con hasta 2 decimales: "1,5". */
export function formatUnidadesDia(valor: number | string): string {
  return Number(valor).toLocaleString("es-AR", { maximumFractionDigits: 2 });
}

/** Fraccion de la API (`0.35`) como porcentaje legible ("35%"); `null` (costo 0) -> "—". */
export function formatMargenPct(fraccion: number | string | null): string {
  if (fraccion === null) return "—";
  return `${(Number(fraccion) * 100).toLocaleString("es-AR", { maximumFractionDigits: 1 })}%`;
}
