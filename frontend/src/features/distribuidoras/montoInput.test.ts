import { describe, expect, it } from "vitest";
import { parseMontoInput } from "@/features/distribuidoras/montoInput";

describe("parseMontoInput", () => {
  it("entiende enteros y decimales con punto o coma", () => {
    expect(parseMontoInput("17500")).toBe(1750000);
    expect(parseMontoInput("17500.5")).toBe(1750050);
    expect(parseMontoInput("17500,50")).toBe(1750050);
    expect(parseMontoInput(" 0,99 ")).toBe(99);
  });
  it("entiende el separador de miles es-AR", () => {
    expect(parseMontoInput("17.500")).toBe(1750000);
    expect(parseMontoInput("1.250.000,75")).toBe(125000075);
  });
  it("devuelve null para vacio, cero, negativos, texto o mas de 2 decimales", () => {
    for (const malo of ["", "  ", "0", "0,00", "-5", "abc", "12,345", "1,2,3", "$ 100"]) {
      expect(parseMontoInput(malo)).toBeNull();
    }
  });
});
