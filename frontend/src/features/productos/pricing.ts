import type { Money } from "@/shared/lib/money";

/**
 * Margen e precio del catalogo (D7, decision #9): el margen se ingresa como porcentaje
 * (35 = 35 %) y viaja como fraccion ("0.35"); el precio se calcula en centavos enteros.
 */

const ESCALA_FRACCION = 1_000_000; // 6 decimales de fraccion = 4 decimales de porcentaje

/** Vista previa `costo x (1 + margen%)` en centavos; `null` si falta o es invalido algun dato. */
export function precioPreview(costoCents: number | null, margenPct: number | null): number | null {
  if (costoCents === null || margenPct === null) return null;
  if (!Number.isFinite(costoCents) || !Number.isFinite(margenPct)) return null;
  if (costoCents <= 0 || margenPct < 0) return null;
  const puntosBase = Math.round(margenPct * 100); // 12.5 % -> 1250
  return Math.floor((costoCents * (10_000 + puntosBase) + 5_000) / 10_000);
}

/** Porcentaje -> fraccion para la API, sin ruido de float: 35 -> "0.35", 100 -> "1". */
export function margenPctAFraccion(pct: number): string {
  const escalado = Math.round(pct * 10_000);
  const entero = Math.trunc(escalado / ESCALA_FRACCION);
  const decimales = String(escalado % ESCALA_FRACCION)
    .padStart(6, "0")
    .replace(/0+$/, "");
  return decimales === "" ? String(entero) : `${entero}.${decimales}`;
}

/** Fraccion de la API -> porcentaje para el formulario: "0.35" -> 35. */
export function fraccionAMargenPct(fraccion: Money): number {
  return Math.round(Number(fraccion) * 1_000_000) / 10_000;
}

/** Lee el campo de margen del formulario (coma o punto); `null` si es vacio, negativo o no numerico. */
export function parseMargenPct(texto: string): number | null {
  const limpio = texto.trim().replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(limpio)) return null;
  return Number(limpio);
}
