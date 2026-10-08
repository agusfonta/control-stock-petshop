/** Resolucion de una lectura (lector de codigo de barras o Enter en el buscador), D10. */
import type { Producto } from "@/shared/api/types";

export type ScanResult =
  | { kind: "agregar"; producto: Producto }
  | { kind: "varios" }
  | { kind: "sin-resultados"; texto: string }
  | { kind: "vacio" };

/** SKU exacto (sin distinguir mayusculas, recortado) -> agregar; unico resultado -> agregar; sin resultados -> aviso. */
export function resolveScan(texto: string, resultados: readonly Producto[]): ScanResult {
  const limpio = texto.trim();
  if (limpio === "") return { kind: "vacio" };
  const buscado = limpio.toLowerCase();
  const porSku = resultados.find((p) => p.sku.trim().toLowerCase() === buscado);
  if (porSku !== undefined) return { kind: "agregar", producto: porSku };
  const [unico, ...resto] = resultados;
  if (unico !== undefined && resto.length === 0) return { kind: "agregar", producto: unico };
  if (resultados.length === 0) return { kind: "sin-resultados", texto: limpio };
  return { kind: "varios" };
}
