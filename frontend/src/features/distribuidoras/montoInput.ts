import { toCents } from "@/shared/lib/money";

/**
 * Interpreta un importe tipeado por una persona y lo devuelve en centavos.
 * Con coma decimal (es-AR) el punto es separador de miles; sin coma, `17.500`
 * son miles y `17500.5` un decimal. `null` si esta vacio, es <= 0 o tiene mas de 2 decimales.
 */
export function parseMontoInput(texto: string): number | null {
  const t = texto.trim();
  if (t === "") return null;
  let normalizado: string;
  if (t.includes(",")) {
    if (!/^\d{1,3}(\.\d{3})*,\d{1,2}$|^\d+,\d{1,2}$/.test(t)) return null;
    normalizado = t.replace(/\./g, "").replace(",", ".");
  } else if (/^\d{1,3}(\.\d{3})+$/.test(t)) {
    normalizado = t.replace(/\./g, "");
  } else if (/^\d+(\.\d{1,2})?$/.test(t)) {
    normalizado = t;
  } else {
    return null;
  }
  const cents = toCents(normalizado);
  return cents > 0 ? cents : null;
}
