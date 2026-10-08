import { z } from "zod";
import type { Cliente, ClienteInput } from "@/shared/api/types";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export const clienteSchema = z.object({
  nombre: z.string().trim().min(1, "Ingresá el nombre").max(200, "Máximo 200 caracteres"),
  telefono: z.string().trim().max(21, "Máximo 21 caracteres"),
  email: z
    .string()
    .trim()
    .max(320, "Máximo 320 caracteres")
    .refine((v) => v === "" || EMAIL.test(v), "Ingresá un email válido"),
  direccion: z.string().trim().max(300, "Máximo 300 caracteres"),
});

export type ClienteFormValues = z.infer<typeof clienteSchema>;

export function valoresClienteVacios(): ClienteFormValues {
  return { nombre: "", telefono: "", email: "", direccion: "" };
}

export function valoresClienteDesde(c: Cliente): ClienteFormValues {
  return {
    nombre: c.nombre,
    telefono: c.telefono ?? "",
    email: c.email ?? "",
    direccion: c.direccion ?? "",
  };
}

const opcional = (texto: string): string | null => (texto.trim() === "" ? null : texto.trim());

/** Cuerpo de alta/edicion: los opcionales vacios viajan como `null`. */
export function aPayloadCliente(v: ClienteFormValues): ClienteInput {
  return {
    nombre: v.nombre.trim(),
    telefono: opcional(v.telefono),
    email: opcional(v.email),
    direccion: opcional(v.direccion),
  };
}
