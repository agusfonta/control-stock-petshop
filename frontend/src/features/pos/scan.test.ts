import { describe, expect, it } from "vitest";
import { resolveScan } from "@/features/pos/scan";
import { makeProducto } from "@/test/fixtures";

const royal = makeProducto({ id: "p-1", sku: "RC-MINI-3KG", nombre: "Royal Canin Mini 3 kg" });
const otro = makeProducto({ id: "p-2", sku: "RC-MAXI-3KG", nombre: "Royal Canin Maxi 3 kg" });

describe("resolveScan", () => {
  it("SKU exacto agrega, sin distinguir mayusculas ni espacios", () => {
    expect(resolveScan("rc-mini-3kg", [royal, otro])).toEqual({ kind: "agregar", producto: royal });
    expect(resolveScan("  RC-MAXI-3KG \n", [royal, otro])).toEqual({ kind: "agregar", producto: otro });
  });

  it("el SKU exacto gana aunque haya mas resultados parciales", () => {
    const parcial = makeProducto({ id: "p-3", sku: "RC-MINI-3KG-X", nombre: "Mini 3kg extra" });
    expect(resolveScan("RC-MINI-3KG", [parcial, royal])).toEqual({ kind: "agregar", producto: royal });
  });

  it("un unico resultado se agrega aunque el texto no sea el SKU", () => {
    expect(resolveScan("royal mini", [royal])).toEqual({ kind: "agregar", producto: royal });
  });

  it("varios resultados sin SKU exacto no agregan: la persona elige", () => {
    expect(resolveScan("royal", [royal, otro])).toEqual({ kind: "varios" });
  });

  it("sin resultados avisa con el texto recortado", () => {
    expect(resolveScan(" 7790000999999 ", [])).toEqual({ kind: "sin-resultados", texto: "7790000999999" });
  });

  it("texto vacio no hace nada", () => {
    expect(resolveScan("   ", [royal])).toEqual({ kind: "vacio" });
  });
});
