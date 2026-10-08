import { describe, expect, it } from "vitest";
import { aPayloadCliente, clienteSchema, valoresClienteDesde, valoresClienteVacios } from "@/features/clientes/clienteForm";
import { makeCliente } from "@/test/fixtures";

function errores(valores: Partial<ReturnType<typeof valoresClienteVacios>>): Record<string, string> {
  const res = clienteSchema.safeParse({ ...valoresClienteVacios(), ...valores });
  if (res.success) return {};
  return Object.fromEntries(res.error.issues.map((i) => [String(i.path[0]), i.message]));
}

describe("clienteSchema", () => {
  it("solo el nombre es obligatorio", () => {
    expect(errores({ nombre: "Lucía Herrera" })).toEqual({});
    expect(errores({ nombre: "   " }).nombre).toBe("Ingresá el nombre");
  });

  it("valida el formato del email cuando se carga", () => {
    expect(errores({ nombre: "A", email: "no-es-email" }).email).toBe("Ingresá un email válido");
    expect(errores({ nombre: "A", email: "ana@mail.com" })).toEqual({});
  });

  it("limita la longitud de los campos", () => {
    expect(errores({ nombre: "x".repeat(201) }).nombre).toBe("Máximo 200 caracteres");
    expect(errores({ nombre: "A", telefono: "1".repeat(22) }).telefono).toBe("Máximo 21 caracteres");
    expect(errores({ nombre: "A", direccion: "d".repeat(301) }).direccion).toBe("Máximo 300 caracteres");
  });
});

describe("aPayloadCliente", () => {
  it("recorta y manda null en los opcionales vacíos", () => {
    const v = { ...valoresClienteVacios(), nombre: " Lucía Herrera ", telefono: "351-8901234" };
    expect(aPayloadCliente(v)).toEqual({
      nombre: "Lucía Herrera",
      telefono: "351-8901234",
      email: null,
      direccion: null,
    });
  });

  it("round-trip desde un cliente del servidor", () => {
    const v = valoresClienteDesde(makeCliente({ telefono: "123", email: "a@b.co" }));
    expect(v).toEqual({ nombre: "Ana Perez", telefono: "123", email: "a@b.co", direccion: "" });
    expect(aPayloadCliente(v)).toMatchObject({ telefono: "123", email: "a@b.co", direccion: null });
  });
});
