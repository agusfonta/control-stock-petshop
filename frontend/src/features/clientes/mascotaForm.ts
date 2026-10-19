import { z } from "zod";
import type { Mascota, TipoMascota } from "@/shared/api/types";

export const TIPOS_MASCOTA: readonly TipoMascota[] = ["perro", "gato", "otro"];

export const TIPO_MASCOTA_LABEL: Record<TipoMascota, string> = {
  perro: "Perro",
  gato: "Gato",
  otro: "Otro",
};

export const mascotaSchema = z.object({
  nombre: z.string().trim().min(1, "Ingresá el nombre").max(100, "Máximo 100 caracteres"),
  tipo: z.enum(["perro", "gato", "otro"]),
});

export type MascotaFormValues = z.infer<typeof mascotaSchema>;

export function valoresMascotaVacios(): MascotaFormValues {
  return { nombre: "", tipo: "perro" };
}

export function valoresMascotaDesde(m: Mascota): MascotaFormValues {
  return { nombre: m.nombre, tipo: m.tipo };
}
