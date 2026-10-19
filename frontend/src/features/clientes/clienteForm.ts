import { z } from "zod";
import type { Cliente, ClienteInput } from "@/shared/api/types";

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
  return { nombre: "", telefono: "", email: "", direccion: "", mascotaNombre: "", mascotaTipo: "" };
}

export function valoresClienteDesde(c: Cliente): ClienteFormValues {
  return {
    nombre: c.nombre,
    telefono: c.telefono ?? "",
    email: c.email ?? "",
    direccion: c.direccion ?? "",
    mascotaNombre: "",
    mascotaTipo: "",
  };
}

const opcional = (texto: string): string | null => (texto.trim() === "" ? null : texto.trim());

/** Cuerpo de alta/edicion: los opcionales vacios viajan como `null`; `mascota` solo si hay nombre y tipo. */
export function aPayloadCliente(v: ClienteFormValues): ClienteInput {
  const payload: ClienteInput = {
    nombre: v.nombre.trim(),
    telefono: opcional(v.telefono),
    email: opcional(v.email),
    direccion: opcional(v.direccion),
  };
  const nombreMascota = v.mascotaNombre.trim();
  if (nombreMascota !== "" && v.mascotaTipo !== "") {
    payload.mascota = { nombre: nombreMascota, tipo: v.mascotaTipo };
  }
  return payload;
}
