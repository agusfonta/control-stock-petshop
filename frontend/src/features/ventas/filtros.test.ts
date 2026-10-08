import { describe, expect, it } from "vitest";
import { hoyLocal, rangoQuery, validarRango } from "@/features/ventas/filtros";

describe("rangoQuery", () => {
  it("un dia: [inicio del dia local, inicio del dia siguiente) con zona horaria", () => {
    const q = rangoQuery("2026-10-07", "2026-10-07");
    expect(q.desde).toBe(new Date(2026, 9, 7).toISOString());
    expect(q.hasta).toBe(new Date(2026, 9, 8).toISOString());
  });

  it("cruza el fin de mes", () => {
    expect(rangoQuery("2026-10-30", "2026-10-31").hasta).toBe(new Date(2026, 10, 1).toISOString());
  });

  it("los bordes vacios se omiten", () => {
    expect(rangoQuery("", "")).toEqual({ desde: undefined, hasta: undefined });
    expect(rangoQuery("2026-10-07", "").hasta).toBeUndefined();
  });
});

describe("validarRango", () => {
  it("rechaza desde posterior a hasta", () => {
    expect(validarRango("2026-10-08", "2026-10-07")).toMatch(/posterior/);
  });
  it("acepta rangos validos o incompletos", () => {
    expect(validarRango("2026-10-07", "2026-10-07")).toBeNull();
    expect(validarRango("", "2026-10-07")).toBeNull();
  });
});

describe("hoyLocal", () => {
  it("usa la fecha local del navegador, no la UTC", () => {
    const d = new Date(2026, 0, 5, 23, 30);
    expect(hoyLocal(d)).toBe("2026-01-05");
  });
});
