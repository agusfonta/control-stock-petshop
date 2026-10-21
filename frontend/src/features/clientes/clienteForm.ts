import { z } from "zod";
import { mascotaSchema } from "@/features/clientes/mascotaForm";
import type { Cliente, ClienteInput, Mascota } from "@/shared/api/types";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const TELEFONO = /^\+?[0-9]{6,20}$/;
const SEPARADORES_TELEFONO = /[\s\-()]/g;

export const clienteSchema = z
  .object({
    nombre: z.string().trim().min(1, "Ingresá el nombre").max(200, "Máximo 200 caracteres"),
    telefono: z
      .string()
      .trim()
      .max(21, { error: "Máximo 21 caracteres", abort: true })
      .refine(
        (v) => v === "" || TELEFONO.test(v.replace(SEPARADORES_TELEFONO, "")),
        "Ingresá un teléfono válido (6 a 20 dígitos)",
      ),
    email: z
      .string()
      .trim()
      .max(320, "Máximo 320 caracteres")
      .refine((v) => v === "" || EMAIL.test(v), "Ingresá un email válido"),
    direccion: z.string().trim().max(300, "Máximo 300 caracteres"),
    mascotaNombre: z.string().trim().max(100, "Máximo 100 caracteres"),
    /** `""` = sin elegir. */
    mascotaTipo: z.union([z.enum(["perro", "gato", "otro"]), z.literal("")]),
    /** Solo en la edicion: mascotas activas del cliente (`id` ausente = nueva). */
    mascotas: z.array(mascotaSchema.extend({ id: z.string().optional() })),
  })
  .superRefine((v, ctx) => {
    if (v.mascotaNombre !== "" && v.mascotaTipo === "") {
      ctx.addIssue({ code: "custom", path: ["mascotaTipo"], message: "Elegí el tipo" });
    }
    if (v.mascotaNombre === "" && v.mascotaTipo !== "") {
      ctx.addIssue({ code: "custom", path: ["mascotaNombre"], message: "Ingresá el nombre" });
    }
  });

export type ClienteFormValues = z.infer<typeof clienteSchema>;

export function valoresClienteVacios(): ClienteFormValues {
  return { nombre: "", telefono: "", email: "", direccion: "", mascotaNombre: "", mascotaTipo: "", mascotas: [] };
}

export function valoresClienteDesde(c: Cliente, mascotas: readonly Mascota[] = []): ClienteFormValues {
  return {
    nombre: c.nombre,
    telefono: c.telefono ?? "",
    email: c.email ?? "",
    direccion: c.direccion ?? "",
    mascotaNombre: "",
    mascotaTipo: "",
    mascotas: mascotas.map((m) => ({ id: m.id, nombre: m.nombre, tipo: m.tipo })),
  };
}

const opcional = (texto: string): string | null => (texto.trim() === "" ? null : texto.trim());

/**
 * Cuerpo de alta/edicion: los opcionales vacios viajan como `null`.
 * - `alta`: `mascota` solo si hay nombre y tipo.
 * - `edicion`: sin mascotas (no se cargaron: el servidor no las toca).
 * - `edicion-con-mascotas`: `mascotas` completo (reemplazo total); nunca `mascota`.
 */
export type ModoPayloadCliente = "alta" | "edicion" | "edicion-con-mascotas";

export function aPayloadCliente(v: ClienteFormValues, modo: ModoPayloadCliente = "alta"): ClienteInput {
  const payload: ClienteInput = {
    nombre: v.nombre.trim(),
    telefono: opcional(v.telefono),
    email: opcional(v.email),
    direccion: opcional(v.direccion),
  };
  if (modo === "edicion-con-mascotas") {
    payload.mascotas = v.mascotas.map((m) => {
      const nombre = m.nombre.trim();
      return m.id === undefined ? { nombre, tipo: m.tipo } : { id: m.id, nombre, tipo: m.tipo };
    });
  }
  const nombreMascota = v.mascotaNombre.trim();
  if (modo === "alta" && nombreMascota !== "" && v.mascotaTipo !== "") {
    payload.mascota = { nombre: nombreMascota, tipo: v.mascotaTipo };
  }
  return payload;
}
