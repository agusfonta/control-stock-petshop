import { describe, expect, it } from "vitest";
import {
  agregarLinea,
  cantidadValida,
  puedeEnviarPedido,
  quitarLinea,
  setCantidad,
  sugerirProductos,
  totalEstimadoCents,
} from "@/features/compras/pedidoLineas";
import type { StockItem } from "@/shared/api/types";
import { makeProducto } from "@/test/fixtures";

function item(id: string, stock: number, minimo: number): StockItem {
  return { ...makeProducto({ id, sku: id.toUpperCase(), nombre: `Producto ${id}`, stock_actual: stock, stock_minimo: minimo }), bajo_minimo: stock <= minimo };
}

describe("cantidadValida", () => {
  it("acepta enteros positivos", () => {
    expect(cantidadValida(1)).toBe(true);
    expect(cantidadValida(250)).toBe(true);
  });
  it("rechaza cero, negativos, decimales y NaN", () => {
    expect(cantidadValida(0)).toBe(false);
    expect(cantidadValida(-2)).toBe(false);
    expect(cantidadValida(1.5)).toBe(false);
    expect(cantidadValida(Number.NaN)).toBe(false);
  });
});

describe("agregarLinea", () => {
  it("agrega una linea nueva con la cantidad pedida (por defecto 1)", () => {
    expect(agregarLinea([], "p-1")).toEqual([{ producto_id: "p-1", cantidad: 1 }]);
    expect(agregarLinea([], "p-2", 6)).toEqual([{ producto_id: "p-2", cantidad: 6 }]);
  });
  it("no repite productos: suma a la linea existente", () => {
    const base = agregarLinea(agregarLinea([], "p-1", 2), "p-2", 1);
    expect(agregarLinea(base, "p-1", 3)).toEqual([
      { producto_id: "p-1", cantidad: 5 },
      { producto_id: "p-2", cantidad: 1 },
    ]);
  });
  it("ignora cantidades invalidas y no muta la entrada", () => {
    const base = [{ producto_id: "p-1", cantidad: 2 }];
    expect(agregarLinea(base, "p-9", 0)).toEqual(base);
    expect(agregarLinea(base, "p-9", 2.5)).toEqual(base);
    expect(base).toEqual([{ producto_id: "p-1", cantidad: 2 }]);
  });
});

describe("setCantidad y quitarLinea", () => {
  const base = [
    { producto_id: "p-1", cantidad: 2 },
    { producto_id: "p-2", cantidad: 4 },
  ];
  it("cambia la cantidad de una linea", () => {
    expect(setCantidad(base, "p-2", 9)).toEqual([
      { producto_id: "p-1", cantidad: 2 },
      { producto_id: "p-2", cantidad: 9 },
    ]);
  });
  it("conserva el valor invalido para marcarlo en la UI (no lo descarta)", () => {
    expect(setCantidad(base, "p-1", 0)[0]?.cantidad).toBe(0);
  });
  it("quita una linea por producto", () => {
    expect(quitarLinea(base, "p-1")).toEqual([{ producto_id: "p-2", cantidad: 4 }]);
    expect(quitarLinea(base, "p-x")).toEqual(base);
  });
});

describe("puedeEnviarPedido", () => {
  it("requiere distribuidora y al menos una linea valida", () => {
    expect(puedeEnviarPedido("d-1", [{ producto_id: "p-1", cantidad: 1 }])).toBe(true);
    expect(puedeEnviarPedido("", [{ producto_id: "p-1", cantidad: 1 }])).toBe(false);
    expect(puedeEnviarPedido("d-1", [])).toBe(false);
  });
  it("rechaza si alguna linea tiene cantidad invalida o hay repetidos", () => {
    expect(puedeEnviarPedido("d-1", [{ producto_id: "p-1", cantidad: 0 }])).toBe(false);
    expect(
      puedeEnviarPedido("d-1", [
        { producto_id: "p-1", cantidad: 1 },
        { producto_id: "p-1", cantidad: 2 },
      ]),
    ).toBe(false);
  });
  it("rechaza mas de 100 lineas (tope de la API)", () => {
    const muchas = Array.from({ length: 101 }, (_, i) => ({ producto_id: `p-${i}`, cantidad: 1 }));
    expect(puedeEnviarPedido("d-1", muchas)).toBe(false);
    expect(puedeEnviarPedido("d-1", muchas.slice(0, 100))).toBe(true);
  });
});

describe("sugerirProductos", () => {
  const alertas = [item("a", 0, 3), item("b", 1, 2)];
  it("une los productos de la lista con los bajo minimo, sin duplicados", () => {
    const lista = [item("b", 1, 2), item("c", 10, 2)];
    const ids = sugerirProductos({ lista, bajoMinimo: alertas, yaEnPedido: [] }).map((s) => s.producto.id);
    expect(ids.sort()).toEqual(["a", "b", "c"]);
  });
  it("pone primero los bajo minimo (mas urgentes antes) y marca el motivo", () => {
    const lista = [item("c", 10, 2), item("b", 1, 2)];
    const out = sugerirProductos({ lista, bajoMinimo: alertas, yaEnPedido: [] });
    expect(out.map((s) => s.producto.id)).toEqual(["a", "b", "c"]);
    expect(out.map((s) => s.bajoMinimo)).toEqual([true, true, false]);
    expect(out.map((s) => s.enLista)).toEqual([false, true, true]);
  });
  it("excluye lo que ya esta en el pedido", () => {
    const out = sugerirProductos({ lista: [item("c", 10, 2)], bajoMinimo: alertas, yaEnPedido: ["a", "c"] });
    expect(out.map((s) => s.producto.id)).toEqual(["b"]);
  });
  it("sugiere reponer hasta el doble del minimo, al menos 1", () => {
    const out = sugerirProductos({ lista: [item("c", 10, 2)], bajoMinimo: [item("a", 1, 3)], yaEnPedido: [] });
    expect(out.find((s) => s.producto.id === "a")?.cantidadSugerida).toBe(5);
    expect(out.find((s) => s.producto.id === "c")?.cantidadSugerida).toBe(1);
  });
});

describe("totalEstimadoCents", () => {
  it("suma cantidad por costo en centavos sin errores de float", () => {
    const costos = new Map<string, string | number>([
      ["p-1", "17500.00"],
      ["p-2", 0.1],
    ]);
    const total = totalEstimadoCents(
      [
        { producto_id: "p-1", cantidad: 2 },
        { producto_id: "p-2", cantidad: 3 },
        { producto_id: "p-3", cantidad: 5 },
      ],
      costos,
    );
    expect(total).toBe(3500000 + 30);
  });
});
