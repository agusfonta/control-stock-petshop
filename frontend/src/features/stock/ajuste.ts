import { z } from "zod";

/** Lee la diferencia tipeada ("-2", "+3", "5"); `null` si no es un entero. Acepta el signo menos tipografico. */
export function parseDelta(texto: string): number | null {
  const limpio = texto.trim().replace("−", "-");
  if (!/^[+-]?\d+$/.test(limpio)) return null;
  return Number(limpio);
}

/** Stock que quedaria tras aplicar la diferencia; `null` si la diferencia no es valida. */
export function stockResultante(stockActual: number, delta: string): number | null {
  const valor = parseDelta(delta);
  return valor === null ? null : stockActual + valor;
}

/** Esquema del dialogo "Ajustar stock" para un producto con `stockActual` unidades. */
export function crearAjusteSchema(stockActual: number) {
  return z
    .object({
      delta: z.string(),
      motivo: z.string().trim().min(1, "Indicá el motivo").max(500, "Máximo 500 caracteres"),
    })
    .superRefine((valores, ctx) => {
      const delta = parseDelta(valores.delta);
      if (delta === null) {
        ctx.addIssue({ code: "custom", path: ["delta"], message: "Ingresá un número entero (ej. -2 o 5)" });
      } else if (delta === 0) {
        ctx.addIssue({ code: "custom", path: ["delta"], message: "La diferencia no puede ser 0" });
      } else if (stockActual + delta < 0) {
        ctx.addIssue({ code: "custom", path: ["delta"], message: "El stock no puede quedar negativo" });
      }
    });
}

export type AjusteValues = z.infer<ReturnType<typeof crearAjusteSchema>>;
