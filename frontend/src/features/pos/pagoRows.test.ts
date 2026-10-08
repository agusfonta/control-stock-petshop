import { describe, expect, it } from "vitest";
import { centsToInput, rowsToDrafts, siguienteMedio } from "@/features/pos/pagoRows";

describe("centsToInput", () => {
  it("enteros sin decimales y fracciones con coma", () => {
    expect(centsToInput(380000)).toBe("3800");
    expect(centsToInput(380050)).toBe("3800,50");
    expect(centsToInput(5)).toBe("0,05");
  });
});

describe("rowsToDrafts", () => {
  it("convierte el texto a centavos y usa 0 para lo invalido", () => {
    const drafts = rowsToDrafts([
      { id: "a", metodo: "efectivo", texto: "1.800" },
      { id: "b", metodo: "tarjeta", texto: "abc" },
      { id: "c", metodo: "transferencia", texto: "12,345" },
    ]);
    expect(drafts.map((d) => d.montoCents)).toEqual([180000, 0, 0]);
  });
});

describe("siguienteMedio", () => {
  it("prefiere el primer medio no usado y, si estan todos, repite efectivo", () => {
    expect(siguienteMedio([{ metodo: "efectivo" }])).toBe("transferencia");
    expect(siguienteMedio([{ metodo: "efectivo" }, { metodo: "transferencia" }])).toBe("tarjeta");
    expect(siguienteMedio([{ metodo: "efectivo" }, { metodo: "transferencia" }, { metodo: "tarjeta" }])).toBe("efectivo");
  });
});
