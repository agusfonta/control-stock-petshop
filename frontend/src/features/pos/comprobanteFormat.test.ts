import { describe, expect, it } from "vitest";
import { formatFechaHora, numeroCorto } from "@/features/pos/comprobanteFormat";

describe("comprobanteFormat", () => {
  it("el numero corto son los primeros 8 caracteres del id en mayusculas", () => {
    expect(numeroCorto("a1b2c3d4-0000-4000-8000-000000000001")).toBe("A1B2C3D4");
  });

  it("formatea fecha y hora en es-AR", () => {
    expect(formatFechaHora("2026-10-01T15:30:00Z")).toMatch(/^\d{1,2}\/\d{1,2}\/\d{2,4},? \d{1,2}:\d{2}/);
  });
});
