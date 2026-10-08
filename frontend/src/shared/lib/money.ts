/**
 * Dinero en la UI: siempre centavos enteros (D7). Nunca se multiplica un float
 * por 100: los strings se parsean digito a digito y los numeros se llevan a
 * texto antes de redondear.
 */

/** Monto tal como llega de la API: numero JSON o string decimal. */
export type Money = number | string;

const DECIMAL = /^([+-]?)(\d+)(?:\.(\d+))?$/;
const ARS = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Convierte un monto a centavos enteros con redondeo mitad hacia arriba (en magnitud). */
export function toCents(value: Money): number {
  const text = typeof value === "number" ? numberToText(value) : value.trim();
  const match = DECIMAL.exec(text);
  if (match === null) {
    throw new Error(`Monto invalido: ${String(value)}`);
  }
  const [, sign, integer, fraction = ""] = match;
  const padded = `${fraction}000`;
  const cents = Number(integer) * 100 + Number(padded.slice(0, 2));
  const rounded = Number(padded.charAt(2)) >= 5 ? cents + 1 : cents;
  return sign === "-" ? -rounded : rounded;
}

function numberToText(value: number): string {
  if (!Number.isFinite(value)) {
    throw new Error(`Monto invalido: ${String(value)}`);
  }
  // 10 decimales absorben el ruido binario (0.1 + 0.2) sin notacion exponencial.
  return value.toFixed(10);
}

/** Serializa centavos como string decimal para la API: 380050 -> "3800.50". */
export function centsToApi(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(Math.round(cents));
  const integer = Math.trunc(abs / 100);
  const fraction = String(abs % 100).padStart(2, "0");
  return `${sign}${integer}.${fraction}`;
}

/** Formatea centavos como pesos argentinos: 2499950 -> "$ 24.999,50". */
export function formatARS(cents: number): string {
  return ARS.format(cents / 100);
}
