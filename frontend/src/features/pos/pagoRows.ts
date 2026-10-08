/** Filas editables del panel de cobro: texto crudo del monto + medio. */
import { MEDIOS_PAGO, type MedioPago, type PagoDraft, parseMontoInput } from "@/features/pos/payments";

export interface PagoRow {
  id: string;
  metodo: MedioPago;
  texto: string;
}

/** 380000 -> "3800"; 380050 -> "3800,50". */
export function centsToInput(cents: number): string {
  const entero = Math.trunc(cents / 100);
  const fraccion = cents % 100;
  return fraccion === 0 ? String(entero) : `${entero},${String(fraccion).padStart(2, "0")}`;
}

export function rowsToDrafts(rows: readonly PagoRow[]): PagoDraft[] {
  return rows.map((r) => ({ id: r.id, metodo: r.metodo, montoCents: parseMontoInput(r.texto) ?? 0 }));
}

/** Medio sugerido para "Agregar otro medio": el primero que todavia no se uso. */
export function siguienteMedio(usados: readonly { metodo: MedioPago }[]): MedioPago {
  const libre = MEDIOS_PAGO.find((m) => !usados.some((u) => u.metodo === m.value));
  return libre?.value ?? "efectivo";
}

let contador = 0;
export function nuevoRowId(): string {
  contador += 1;
  return `pago-${contador}`;
}
