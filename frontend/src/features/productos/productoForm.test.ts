import { describe, expect, it } from "vitest";
import {
  aPayload,
  aPayloadAlta,
  parseMontoCents,
  productoSchema,
  valoresDesdeProducto,
  valoresVacios,
} from "@/features/productos/productoForm";
import { makeProducto } from "@/test/fixtures";

describe("parseMontoCents", () => {
  it("acepta enteros y decimales con coma o punto", () => {
    expect(parseMontoCents("18000")).toBe(1_800_000);
    expect(parseMontoCents("18000,50")).toBe(1_800_050);
    expect(parseMontoCents(" 15.5 ")).toBe(1550);
  });

  it("rechaza separadores de miles, vacio, cero y texto", () => {
    expect(parseMontoCents("18.000,50")).toBeNull();
    expect(parseMontoCents("")).toBeNull();
    expect(parseMontoCents("0")).toBeNull();
    expect(parseMontoCents("abc")).toBeNull();
  });
});

describe("productoSchema", () => {
  const valido = { ...valoresVacios(), sku: "RC-1", nombre: "Alimento", costo: "18000", margen: "35" };

  it("acepta un formulario completo", () => {
    expect(productoSchema.safeParse(valido).success).toBe(true);
  });

  it("marca los campos invalidos con mensaje en español", () => {
    const res = productoSchema.safeParse({ ...valido, sku: "mal sku", costo: "0", margen: "", stockMinimo: "-1" });
    expect(res.success).toBe(false);
    if (!res.success) {
      const campos = res.error.issues.map((i) => i.path[0]);
      expect(campos).toEqual(expect.arrayContaining(["sku", "costo", "margen", "stockMinimo"]));
    }
  });
});

describe("payloads", () => {
  it("envia costo como string con 2 decimales y margen como fraccion", () => {
    const v = { ...valoresVacios(), sku: " RC-1 ", nombre: "Alimento", costo: "18000", margen: "35", stockMinimo: "3" };
    expect(aPayload(v)).toEqual({
      sku: "RC-1",
      nombre: "Alimento",
      marca: null,
      categoria: null,
      unidad: "unidad",
      costo: "18000.00",
      margen_pct: "0.35",
      stock_minimo: 3,
      distribuidora_default_id: null,
    });
  });

  it("el alta suma stock inicial y la edicion no lo incluye", () => {
    const v = { ...valoresVacios(), sku: "A", nombre: "A", costo: "10", margen: "0", stockInicial: "12" };
    expect(aPayloadAlta(v).stock_actual).toBe(12);
    expect("stock_actual" in aPayload(v)).toBe(false);
  });

  it("round-trip desde un producto del servidor", () => {
    const v = valoresDesdeProducto(makeProducto({ distribuidora_default_id: "d-1" }));
    expect(v.margen).toBe("35");
    expect(v.costo).toBe("18000");
    expect(aPayload(v)).toMatchObject({ costo: "18000.00", margen_pct: "0.35", distribuidora_default_id: "d-1" });
  });
});
