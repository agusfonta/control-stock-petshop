import { describe, expect, it } from "vitest";
import { fraccionAMargenPct, margenPctAFraccion, parseMargenPct, precioPreview } from "@/features/productos/pricing";

describe("precioPreview", () => {
  it("calcula costo x (1 + margen) en centavos", () => {
    expect(precioPreview(1_800_000, 35)).toBe(2_430_000);
  });

  it("acepta costo y margen con decimales sin errores de float", () => {
    expect(precioPreview(1050, 12.5)).toBe(1181); // 1181.25 -> redondeo a centavo
    expect(precioPreview(999, 10)).toBe(1099); // 1098.9
  });

  it("margen 0 devuelve el costo", () => {
    expect(precioPreview(5000, 0)).toBe(5000);
  });

  it("devuelve null si falta costo o margen o son invalidos", () => {
    expect(precioPreview(null, 35)).toBeNull();
    expect(precioPreview(1000, null)).toBeNull();
    expect(precioPreview(0, 35)).toBeNull();
    expect(precioPreview(1000, -5)).toBeNull();
  });
});

describe("margen % <-> fraccion", () => {
  it("35 -> '0.35' y '0.35' -> 35", () => {
    expect(margenPctAFraccion(35)).toBe("0.35");
    expect(fraccionAMargenPct("0.35")).toBe(35);
  });

  it("maneja decimales y enteros", () => {
    expect(margenPctAFraccion(12.5)).toBe("0.125");
    expect(margenPctAFraccion(100)).toBe("1");
    expect(margenPctAFraccion(0)).toBe("0");
    expect(fraccionAMargenPct(0.4)).toBe(40);
    expect(fraccionAMargenPct("1.2500")).toBe(125);
  });

  it("round-trip estable sin ruido de float", () => {
    for (const pct of [7, 15.5, 33.33, 60]) {
      expect(fraccionAMargenPct(margenPctAFraccion(pct))).toBe(pct);
    }
  });
});

describe("parseMargenPct", () => {
  it("acepta coma o punto decimal", () => {
    expect(parseMargenPct("35")).toBe(35);
    expect(parseMargenPct("12,5")).toBe(12.5);
    expect(parseMargenPct(" 7.25 ")).toBe(7.25);
  });

  it("devuelve null para texto invalido o vacio", () => {
    expect(parseMargenPct("")).toBeNull();
    expect(parseMargenPct("abc")).toBeNull();
    expect(parseMargenPct("-3")).toBeNull();
  });
});
