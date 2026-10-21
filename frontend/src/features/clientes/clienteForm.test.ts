import { describe, expect, it } from "vitest";
import { aPayloadCliente, clienteSchema, valoresClienteDesde, valoresClienteVacios } from "@/features/clientes/clienteForm";
import type { Mascota } from "@/shared/api/types";
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
      mascotas: [],
    });
    expect(aPayloadCliente(v)).toMatchObject({ telefono: "123", email: "a@b.co", direccion: null });
  });
});

describe("clienteSchema - mascotas en edición", () => {
  const fila = (nombre: string, tipo: "perro" | "gato" | "otro" = "perro", id?: string) => ({
    ...(id === undefined ? {} : { id }),
    nombre,
    tipo,
  });

  function erroresPath(mascotas: ReturnType<typeof fila>[]): string[] {
    const res = clienteSchema.safeParse({ ...valoresClienteVacios(), nombre: "Ana", mascotas });
    return res.success ? [] : res.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`);
  }

  it("filas completas son válidas, con o sin id", () => {
    expect(erroresPath([fila("MIMI", "gato", "m-1"), fila("Luna", "otro")])).toEqual([]);
    expect(erroresPath([])).toEqual([]);
  });

  it("un nombre vacío marca esa fila y no las demás", () => {
    expect(erroresPath([fila("MIMI", "gato", "m-1"), fila("   ", "perro", "m-2")])).toEqual([
      "mascotas.1.nombre: Ingresá el nombre",
    ]);
  });

  it("limita el nombre a 100 caracteres", () => {
    expect(erroresPath([fila("x".repeat(101))])).toEqual(["mascotas.0.nombre: Máximo 100 caracteres"]);
  });
});

describe("valoresClienteDesde - mascotas", () => {
  it("sin mascotas cargadas la lista queda vacía", () => {
    expect(valoresClienteDesde(makeCliente()).mascotas).toEqual([]);
  });

  it("copia id, nombre y tipo de cada mascota", () => {
    const mascotas: Mascota[] = [
      { id: "m-1", nombre: "MIMI", tipo: "gato", activo: true },
      { id: "m-2", nombre: "Toby", tipo: "perro", activo: true },
    ];
    expect(valoresClienteDesde(makeCliente(), mascotas).mascotas).toEqual([
      { id: "m-1", nombre: "MIMI", tipo: "gato" },
      { id: "m-2", nombre: "Toby", tipo: "perro" },
    ]);
  });
});

describe("aPayloadCliente - mascotas en edición", () => {
  const base = { ...valoresClienteVacios(), nombre: "Ana" };

  it("con las mascotas cargadas manda la lista completa, recortada y sin id en las nuevas", () => {
    const payload = aPayloadCliente(
      {
        ...base,
        mascotas: [
          { id: "m-1", nombre: " Mimi ", tipo: "gato" },
          { nombre: "Luna", tipo: "otro" },
        ],
      },
      "edicion-con-mascotas",
    );
    expect(payload.mascotas).toEqual([{ id: "m-1", nombre: "Mimi", tipo: "gato" }, { nombre: "Luna", tipo: "otro" }]);
    expect(payload.mascotas?.[1]).not.toHaveProperty("id");
  });

  it("una lista vacía se envía (da de baja todas)", () => {
    expect(aPayloadCliente(base, "edicion-con-mascotas").mascotas).toEqual([]);
  });

  it("sin mascotas cargadas no manda la clave mascotas", () => {
    const payload = aPayloadCliente({ ...base, mascotas: [{ id: "m-1", nombre: "Mimi", tipo: "gato" }] }, "edicion");
    expect("mascotas" in payload).toBe(false);
  });

  it("en edición nunca manda mascota (singular)", () => {
    const v = { ...base, mascotaNombre: "Firulais", mascotaTipo: "perro" as const };
    expect("mascota" in aPayloadCliente(v, "edicion")).toBe(false);
    expect("mascota" in aPayloadCliente(v, "edicion-con-mascotas")).toBe(false);
  });

  it("el alta no cambia: manda mascota y no mascotas", () => {
    const payload = aPayloadCliente({ ...base, mascotaNombre: "Firulais", mascotaTipo: "perro" });
    expect(payload.mascota).toEqual({ nombre: "Firulais", tipo: "perro" });
    expect("mascotas" in payload).toBe(false);
  });
});
