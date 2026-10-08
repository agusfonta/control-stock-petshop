import { describe, expect, it } from "vitest";
import { centsToApi, formatARS, toCents } from "@/shared/lib/money";

const normalizar = (texto: string): string => texto.replace(/\s/g, " ");

describe("toCents", () => {
  it("convierte desde string sin errores de float", () => {
    expect(toCents("15.045")).toBe(1505);
    expect(toCents("0.10")).toBe(10);
    expect(toCents("3800.50")).toBe(380050);
  });

  it("convierte desde numero", () => {
    expect(toCents(24999.5)).toBe(2499950);
    expect(toCents(0.1 + 0.2)).toBe(30);
    expect(toCents(1.005)).toBe(101);
  });

  it("redondea mitad hacia arriba a 2 decimales", () => {
    expect(toCents("0.005")).toBe(1);
    expect(toCents("0.004")).toBe(0);
    expect(toCents("2.675")).toBe(268);
  });

  it("acepta enteros, negativos y notacion exponencial de float", () => {
    expect(toCents(0)).toBe(0);
    expect(toCents(5)).toBe(500);
    expect(toCents("-12.30")).toBe(-1230);
    expect(toCents(1e-7)).toBe(0);
  });

  it("rechaza valores no numericos", () => {
    expect(() => toCents("abc")).toThrow();
    expect(() => toCents(Number.NaN)).toThrow();
  });
});

describe("centsToApi", () => {
  it("serializa a string con dos decimales", () => {
    expect(centsToApi(380050)).toBe("3800.50");
    expect(centsToApi(5)).toBe("0.05");
    expect(centsToApi(0)).toBe("0.00");
    expect(centsToApi(-1230)).toBe("-12.30");
  });
});

describe("formatARS", () => {
  it("formatea en pesos argentinos con miles y 2 decimales", () => {
    expect(normalizar(formatARS(2499950))).toBe("$ 24.999,50");
    expect(normalizar(formatARS(0))).toBe("$ 0,00");
    expect(normalizar(formatARS(123456789))).toBe("$ 1.234.567,89");
  });
});
