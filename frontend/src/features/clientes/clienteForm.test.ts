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

describe("clienteSchema - teléfono", () => {
  const MSG = "Ingresá un teléfono válido (6 a 20 dígitos)";

  it("acepta formatos comunes y el formato guardado por el seed", () => {
    for (const tel of ["", "351-8765432", "+54 9 351 876 5432", "(0351) 876-5432", "123456"]) {
      expect(errores({ nombre: "A", telefono: tel })).toEqual({});
    }
  });

  it("rechaza letras, muy corto o muy largo con un mensaje en español", () => {
    for (const tel of ["abc", "12345", "351-87x6543", "1".repeat(21)]) {
      expect(errores({ nombre: "A", telefono: tel }).telefono, tel).toBe(MSG);
    }
  });
});

describe("clienteSchema - mascota opcional", () => {
  it("con ambos vacíos no hay errores", () => {
    expect(errores({ nombre: "Ana" })).toEqual({});
  });

  it("nombre sin tipo marca el tipo", () => {
    expect(errores({ nombre: "Ana", mascotaNombre: "Firulais" })).toEqual({ mascotaTipo: "Elegí el tipo" });
  });

  it("tipo sin nombre marca el nombre", () => {
    expect(errores({ nombre: "Ana", mascotaTipo: "gato" })).toEqual({ mascotaNombre: "Ingresá el nombre" });
  });

  it("nombre solo con espacios cuenta como vacío", () => {
    expect(errores({ nombre: "Ana", mascotaNombre: "   ", mascotaTipo: "perro" })).toEqual({
      mascotaNombre: "Ingresá el nombre",
    });
    expect(errores({ nombre: "Ana", mascotaNombre: "   " })).toEqual({});
  });

  it("nombre y tipo completos son válidos y el nombre se limita a 100", () => {
    expect(errores({ nombre: "Ana", mascotaNombre: "Firulais", mascotaTipo: "perro" })).toEqual({});
    expect(errores({ nombre: "Ana", mascotaNombre: "x".repeat(101), mascotaTipo: "perro" }).mascotaNombre).toBe(
      "Máximo 100 caracteres",
    );
  });
});

describe("aPayloadCliente - mascota", () => {
  it("no incluye la clave mascota sin nombre de mascota", () => {
    const payload = aPayloadCliente({ ...valoresClienteVacios(), nombre: "Ana" });
    expect("mascota" in payload).toBe(false);
  });

  it("incluye mascota con nombre recortado y tipo", () => {
    const payload = aPayloadCliente({
      ...valoresClienteVacios(),
      nombre: "Ana",
      mascotaNombre: " Mishi ",
      mascotaTipo: "gato",
    });
    expect(payload.mascota).toEqual({ nombre: "Mishi", tipo: "gato" });
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
    expect(v).toEqual({
      nombre: "Ana Perez",
      telefono: "123",
      email: "a@b.co",
      direccion: "",
      mascotaNombre: "",
      mascotaTipo: "",
    });
    expect(aPayloadCliente(v)).toMatchObject({ telefono: "123", email: "a@b.co", direccion: null });
  });
});
