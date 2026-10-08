import { describe, expect, it } from "vitest";
import {
  diasDelPeriodo,
  fechaLegible,
  formatMargenPct,
  formatUnidadesDia,
  pedidoUrl,
  periodoPreset,
  periodoQuery,
  toIsoDate,
  validarPeriodo,
} from "@/features/reportes/params";

describe("toIsoDate", () => {
  it("usa la fecha local del navegador, no la UTC", () => {
    expect(toIsoDate(new Date(2026, 9, 7, 23, 59))).toBe("2026-10-07");
    expect(toIsoDate(new Date(2026, 0, 2, 0, 1))).toBe("2026-01-02");
  });
});

describe("periodoQuery", () => {
  it("omite los bordes vacios para usar el default del servidor", () => {
    expect(periodoQuery({ desde: "", hasta: "" })).toEqual({ desde: undefined, hasta: undefined });
  });
  it("envia solo los bordes elegidos", () => {
    expect(periodoQuery({ desde: "2026-10-01", hasta: "" })).toEqual({ desde: "2026-10-01", hasta: undefined });
    expect(periodoQuery({ desde: "2026-10-01", hasta: "2026-10-07" })).toEqual({
      desde: "2026-10-01",
      hasta: "2026-10-07",
    });
  });
});

describe("diasDelPeriodo", () => {
  it("cuenta ambos bordes inclusive", () => {
    expect(diasDelPeriodo("2026-10-01", "2026-10-01")).toBe(1);
    expect(diasDelPeriodo("2026-10-01", "2026-10-07")).toBe(7);
    expect(diasDelPeriodo("2026-02-28", "2026-03-01")).toBe(2);
  });
});

describe("validarPeriodo", () => {
  it("acepta periodos vacios, parciales y ordenados", () => {
    expect(validarPeriodo({ desde: "", hasta: "" })).toBeNull();
    expect(validarPeriodo({ desde: "2026-10-01", hasta: "" })).toBeNull();
    expect(validarPeriodo({ desde: "2026-10-01", hasta: "2026-10-07" })).toBeNull();
  });
  it("rechaza desde posterior a hasta", () => {
    expect(validarPeriodo({ desde: "2026-10-08", hasta: "2026-10-07" })).toMatch(/posterior/);
  });
  it("rechaza mas de 366 dias y acepta exactamente 366", () => {
    expect(validarPeriodo({ desde: "2025-10-06", hasta: "2026-10-07" })).toMatch(/366/);
    expect(validarPeriodo({ desde: "2025-10-07", hasta: "2026-10-07" })).toBeNull();
  });
});

describe("periodoPreset", () => {
  const hoy = new Date(2026, 9, 7);
  it("ultimos 7 dias incluye hoy", () => {
    expect(periodoPreset("7d", hoy)).toEqual({ desde: "2026-10-01", hasta: "2026-10-07" });
  });
  it("ultimos 30 dias", () => {
    expect(periodoPreset("30d", hoy)).toEqual({ desde: "2026-09-08", hasta: "2026-10-07" });
  });
  it("este mes arranca el dia 1", () => {
    expect(periodoPreset("mes", hoy)).toEqual({ desde: "2026-10-01", hasta: "2026-10-07" });
  });
});

describe("fechaLegible", () => {
  it("formatea YYYY-MM-DD en es-AR sin correrse por zona horaria", () => {
    expect(fechaLegible("2026-10-07")).toBe("7/10/2026");
  });
});

describe("pedidoUrl", () => {
  it("preselecciona la distribuidora por defecto y el producto", () => {
    expect(pedidoUrl({ producto_id: "p1", distribuidora_default_id: "d1" })).toBe(
      "/compras?nuevo=1&distribuidora=d1&producto=p1",
    );
  });
  it("sin distribuidora por defecto solo lleva el producto", () => {
    expect(pedidoUrl({ producto_id: "p2", distribuidora_default_id: null })).toBe("/compras?nuevo=1&producto=p2");
  });
});

describe("formatUnidadesDia", () => {
  it("formatea con coma y sin ceros de relleno", () => {
    expect(formatUnidadesDia("1.50")).toBe("1,5");
    expect(formatUnidadesDia(2)).toBe("2");
    expect(formatUnidadesDia("0.33")).toBe("0,33");
  });
});

describe("formatMargenPct", () => {
  it("convierte la fraccion de la API en porcentaje", () => {
    expect(formatMargenPct("0.3500")).toBe("35%");
    expect(formatMargenPct(0.4234)).toBe("42,3%");
  });
  it("null se muestra como raya", () => {
    expect(formatMargenPct(null)).toBe("—");
  });
});
