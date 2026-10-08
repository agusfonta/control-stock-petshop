import { z } from "zod";
import type { Distribuidora, DistribuidoraInput } from "@/shared/api/types";

export const distribuidoraSchema = z.object({
  nombre: z.string().trim().min(1, "Ingresá el nombre").max(200, "Máximo 200 caracteres"),
  contacto: z.string().trim().max(200, "Máximo 200 caracteres"),
  cuit: z.string().trim().max(20, "Máximo 20 caracteres"),
  condiciones: z.string().trim().max(500, "Máximo 500 caracteres"),
});

export type DistribuidoraFormValues = z.infer<typeof distribuidoraSchema>;

export function valoresDistribuidoraVacios(): DistribuidoraFormValues {
  return { nombre: "", contacto: "", cuit: "", condiciones: "" };
}

export function valoresDistribuidoraDesde(d: Distribuidora): DistribuidoraFormValues {
  return { nombre: d.nombre, contacto: d.contacto ?? "", cuit: d.cuit ?? "", condiciones: d.condiciones ?? "" };
}

const opcional = (t: string): string | null => (t.trim() === "" ? null : t.trim());

/** Los opcionales vacios viajan como `null` (la edicion tambien los limpia). */
export function aPayloadDistribuidora(v: DistribuidoraFormValues): DistribuidoraInput {
  return {
    nombre: v.nombre.trim(),
    contacto: opcional(v.contacto),
    cuit: opcional(v.cuit),
    condiciones: opcional(v.condiciones),
  };
}
