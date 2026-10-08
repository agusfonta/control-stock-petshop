import { describe, expect, it } from "vitest";
import { ApiError, parseApiError } from "@/shared/api/errors";

describe("parseApiError", () => {
  it("usa detail string como mensaje", () => {
    const err = parseApiError(409, { detail: "sku duplicado" });

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.message).toBe("sku duplicado");
    expect(err.fieldErrors).toEqual({});
    expect(err.faltantes).toBeUndefined();
  });

  it("convierte la lista de Pydantic en fieldErrors por campo", () => {
    const err = parseApiError(422, {
      detail: [
        { loc: ["body", "email"], msg: "campo invalido", type: "value_error" },
        { loc: ["body", "lineas", 0, "cantidad"], msg: "debe ser > 0", type: "x" },
        { loc: ["body", "email"], msg: "segundo mensaje ignorado", type: "x" },
      ],
    });

    expect(err.status).toBe(422);
    expect(err.fieldErrors).toEqual({
      email: "campo invalido",
      "lineas.0.cantidad": "debe ser > 0",
    });
    expect(err.message).toBe("Revisá los datos ingresados");
  });

  it("extrae faltantes del objeto detail de un 409 de stock", () => {
    const faltantes = [{ producto_id: "p1", solicitado: 5, disponible: 2 }];

    const err = parseApiError(409, {
      detail: { mensaje: "stock insuficiente", faltantes },
    });

    expect(err.message).toBe("stock insuficiente");
    expect(err.faltantes).toEqual(faltantes);
  });

  it("cae en un mensaje por estado cuando no hay detail utilizable", () => {
    expect(parseApiError(500, null).message).toBe("Error del servidor");
    expect(parseApiError(403, {}).message).toBe("No tenés permiso para esta acción");
    expect(parseApiError(404, "texto").message).toBe("No se encontró lo que buscabas");
  });

  it("status 0 representa error de red", () => {
    const err = parseApiError(0, null);

    expect(err.status).toBe(0);
    expect(err.message).toBe("No se pudo conectar con el servidor");
  });
});
