/** Pagos del cobro como funciones puras (D8). Todo en centavos enteros (D7). */
import type { MetodoPagoVenta } from "@/shared/api/types";

/** Medios que ofrece el mostrador; Mercado Pago no se ofrece (decision #12). */
export type MedioPago = Extract<MetodoPagoVenta, "efectivo" | "transferencia" | "tarjeta">;

export const MEDIOS_PAGO: readonly { value: MedioPago; label: string }[] = [
  { value: "efectivo", label: "Efectivo" },
  { value: "transferencia", label: "Transferencia" },
  { value: "tarjeta", label: "Tarjeta" },
];

export const MAX_PAGOS = 5;

export interface PagoDraft {
  /** Id local estable para keys de React; no se envia a la API. */
  id: string;
  metodo: MedioPago;
  montoCents: number;
}

export function sumCents(pagos: readonly Pick<PagoDraft, "montoCents">[]): number {
  return pagos.reduce((acc, p) => acc + p.montoCents, 0);
}

/** Positivo: falta cobrar. Negativo: sobra. Cero: cuadra. */
export function remainingCents(total: number, pagos: readonly Pick<PagoDraft, "montoCents">[]): number {
  return total - sumCents(pagos);
}

/** 1 a 5 pagos, cada uno entero > 0 (maximo dos decimales = centavos) y suma exactamente igual al total. */
export function canConfirm(total: number, pagos: readonly Pick<PagoDraft, "montoCents">[]): boolean {
  if (total <= 0 || pagos.length < 1 || pagos.length > MAX_PAGOS) return false;
  if (!pagos.every((p) => Number.isInteger(p.montoCents) && p.montoCents > 0)) return false;
  return remainingCents(total, pagos) === 0;
}

/** Vuelto = paga con - monto en efectivo. Informativo; nunca negativo. */
export function vueltoCents(pagaConCents: number, montoEfectivoCents: number): number {
  return Math.max(0, pagaConCents - montoEfectivoCents);
}

const ESCALONES_PESOS = [1000, 5000, 10000] as const;
const MAX_OPCIONES = 4;

/** Botones de "Paga con": el exacto y los proximos multiplos de $1.000 / $5.000 / $10.000. */
export function quickCashOptions(totalCents: number): number[] {
  if (totalCents <= 0) return [];
  const opciones = new Set<number>([totalCents]);
  for (const escalon of ESCALONES_PESOS) {
    const centavos = escalon * 100;
    opciones.add((Math.floor(totalCents / centavos) + 1) * centavos);
  }
  return [...opciones].sort((a, b) => a - b).slice(0, MAX_OPCIONES);
}

/**
 * Interpreta lo que escribe la persona en un campo de monto: "3800", "3.800,50", "3800.50", "$ 1.500".
 * Devuelve centavos o `null` si esta vacio, es invalido o tiene mas de dos decimales.
 */
export function parseMontoInput(texto: string): number | null {
  const limpio = texto.replace(/[$\s]/g, "");
  if (limpio === "") return null;
  let normal: string;
  if (limpio.includes(",")) {
    normal = limpio.replace(/\./g, "").replace(",", ".");
  } else if (/^\d{1,3}(\.\d{3})+$/.test(limpio)) {
    normal = limpio.replace(/\./g, "");
  } else {
    normal = limpio;
  }
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normal);
  if (match === null) return null;
  const [, entero = "0", decimales = ""] = match;
  return Number(entero) * 100 + Number(decimales.padEnd(2, "0"));
}
