import { describe, expect, it } from "vitest";
import {
  MAX_PAGOS,
  MEDIOS_PAGO,
  type PagoDraft,
  canConfirm,
  parseMontoInput,
  quickCashOptions,
  remainingCents,
  sumCents,
  vueltoCents,
} from "@/features/pos/payments";

function pago(montoCents: number, metodo: PagoDraft["metodo"] = "efectivo", id = String(montoCents)): PagoDraft {
  return { id, metodo, montoCents };
}

describe("sumCents y remainingCents", () => {
  it("suma los pagos", () => {
    expect(sumCents([pago(180000), pago(150000, "tarjeta")])).toBe(330000);
    expect(sumCents([])).toBe(0);
  });

  it("positivo si falta, negativo si sobra, cero si cuadra", () => {
    expect(remainingCents(380000, [pago(180000), pago(150000, "tarjeta")])).toBe(50000);
    expect(remainingCents(380000, [pago(400000)])).toBe(-20000);
    expect(remainingCents(380000, [pago(380000)])).toBe(0);
  });
});

describe("canConfirm", () => {
  it("acepta un pago que iguala el total", () => {
    expect(canConfirm(380000, [pago(380000)])).toBe(true);
  });

  it("acepta pagos divididos que suman el total exacto", () => {
    expect(canConfirm(380000, [pago(180000), pago(200000, "tarjeta")])).toBe(true);
  });

  it("rechaza si falta o sobra", () => {
    expect(canConfirm(380000, [pago(180000), pago(150000, "tarjeta")])).toBe(false);
    expect(canConfirm(380000, [pago(400000)])).toBe(false);
  });

  it("rechaza montos en cero, negativos o con fracciones de centavo", () => {
    expect(canConfirm(380000, [pago(380000), pago(0, "tarjeta")])).toBe(false);
    expect(canConfirm(380000, [pago(400000), pago(-20000, "tarjeta")])).toBe(false);
    expect(canConfirm(100, [pago(50.5), pago(49.5, "tarjeta")])).toBe(false);
  });

  it("exige entre 1 y 5 pagos", () => {
    expect(canConfirm(0, [])).toBe(false);
    const cinco = [1, 2, 3, 4, 5].map((n) => pago(100, "efectivo", `p${n}`));
    expect(canConfirm(500, cinco)).toBe(true);
    const seis = [...cinco, pago(100, "efectivo", "p6")];
    expect(canConfirm(600, seis)).toBe(false);
    expect(MAX_PAGOS).toBe(5);
  });

  it("no confirma un carrito con total cero", () => {
    expect(canConfirm(0, [pago(0)])).toBe(false);
  });
});

describe("vueltoCents", () => {
  it("paga con menos monto en efectivo: 5000 - 3800 = 1200", () => {
    expect(vueltoCents(500000, 380000)).toBe(120000);
  });

  it("nunca es negativo si paga con menos de lo debido", () => {
    expect(vueltoCents(300000, 380000)).toBe(0);
  });

  it("paga justo no da vuelto", () => {
    expect(vueltoCents(380000, 380000)).toBe(0);
  });
});

describe("quickCashOptions", () => {
  it("incluye el exacto y los proximos multiplos, ascendente y sin repetir", () => {
    expect(quickCashOptions(380000)).toEqual([380000, 400000, 500000, 1000000]);
  });

  it("no repite cuando el total ya es multiplo", () => {
    expect(quickCashOptions(500000)).toEqual([500000, 600000, 1000000]);
    expect(quickCashOptions(1000000)).toEqual([1000000, 1100000, 1500000, 2000000]);
  });

  it("maneja totales con centavos", () => {
    expect(quickCashOptions(300030)).toEqual([300030, 400000, 500000, 1000000]);
  });

  it("sin total no ofrece nada", () => {
    expect(quickCashOptions(0)).toEqual([]);
  });
});

describe("parseMontoInput", () => {
  it("interpreta formato es-AR y punto decimal", () => {
    expect(parseMontoInput("3800")).toBe(380000);
    expect(parseMontoInput("3800,5")).toBe(380050);
    expect(parseMontoInput("3.800,50")).toBe(380050);
    expect(parseMontoInput("3800.50")).toBe(380050);
    expect(parseMontoInput(" $ 1.500 ")).toBe(150000);
  });

  it("devuelve null con texto vacio o invalido y con mas de dos decimales", () => {
    expect(parseMontoInput("")).toBeNull();
    expect(parseMontoInput("abc")).toBeNull();
    expect(parseMontoInput("10,123")).toBeNull();
  });
});

describe("MEDIOS_PAGO", () => {
  it("ofrece solo efectivo, transferencia y tarjeta (sin Mercado Pago)", () => {
    expect(MEDIOS_PAGO.map((m) => m.value)).toEqual(["efectivo", "transferencia", "tarjeta"]);
  });
});
