import { describe, expect, it } from "vitest";
import { crearAjusteSchema, parseDelta, stockResultante } from "@/features/stock/ajuste";

describe("parseDelta", () => {
  it("acepta enteros con signo", () => {
    expect(parseDelta("-2")).toBe(-2);
    expect(parseDelta("+3")).toBe(3);
    expect(parseDelta(" 5 ")).toBe(5);
    expect(parseDelta("−4")).toBe(-4); // signo menos tipografico
  });

  it("devuelve null para vacio, decimales y texto", () => {
    expect(parseDelta("")).toBeNull();
    expect(parseDelta("1.5")).toBeNull();
    expect(parseDelta("abc")).toBeNull();
    expect(parseDelta("-")).toBeNull();
  });
});

describe("stockResultante", () => {
  it("suma la diferencia al stock actual", () => {
    expect(stockResultante(10, "-2")).toBe(8);
    expect(stockResultante(10, "5")).toBe(15);
  });

  it("devuelve null si la diferencia es invalida", () => {
    expect(stockResultante(10, "")).toBeNull();
  });
});

describe("crearAjusteSchema", () => {
  const schema = crearAjusteSchema(10);

  function mensajes(delta: string, motivo: string): Record<string, string> {
    const res = schema.safeParse({ delta, motivo });
    if (res.success) return {};
    return Object.fromEntries(res.error.issues.map((i) => [String(i.path[0]), i.message]));
  }

  it("acepta una diferencia valida con motivo", () => {
    expect(schema.safeParse({ delta: "-2", motivo: "rotura" }).success).toBe(true);
  });

  it("exige motivo", () => {
    expect(mensajes("-2", "   ").motivo).toBe("Indicá el motivo");
  });

  it("rechaza diferencia 0 o invalida", () => {
    expect(mensajes("0", "x").delta).toBe("La diferencia no puede ser 0");
    expect(mensajes("1.5", "x").delta).toBe("Ingresá un número entero (ej. -2 o 5)");
  });

  it("impide dejar el stock negativo", () => {
    expect(mensajes("-11", "x").delta).toBe("El stock no puede quedar negativo");
    expect(schema.safeParse({ delta: "-10", motivo: "x" }).success).toBe(true);
  });
});
