import { describe, expect, it } from "vitest";
import {
  type Cart,
  addProduct,
  applyFaltantes,
  cartSignature,
  clampToDisponible,
  lineSubtotalCents,
  removeLine,
  setQty,
  syncPrecios,
  totalCents,
  unidadesTotales,
} from "@/features/pos/cart";
import { makeProducto } from "@/test/fixtures";

const royal = makeProducto({ id: "p-1", precio_venta: "1500.00", stock_actual: 10 });
const snack = makeProducto({ id: "p-2", sku: "SN-1", nombre: "Snack", precio_venta: "0.10", stock_actual: 50 });
const vacio: Cart = [];

describe("addProduct", () => {
  it("agrega una linea nueva con precio en centavos y stock conocido", () => {
    const { cart, aviso } = addProduct(vacio, royal);
    expect(aviso).toBeNull();
    expect(cart).toHaveLength(1);
    expect(cart[0]).toMatchObject({ productoId: "p-1", sku: "RC-MINI-3KG", precioCents: 150000, cantidad: 1, stock: 10 });
  });

  it("suma cantidad si el producto ya esta en el carrito", () => {
    const una = addProduct(vacio, royal).cart;
    const { cart } = addProduct(una, royal, 2);
    expect(cart).toHaveLength(1);
    expect(cart[0]?.cantidad).toBe(3);
  });

  it("topa en el stock y avisa 'Solo hay N unidades'", () => {
    const chico = makeProducto({ id: "p-3", stock_actual: 2 });
    const dos = addProduct(vacio, chico, 2).cart;
    const { cart, aviso } = addProduct(dos, chico);
    expect(cart[0]?.cantidad).toBe(2);
    expect(aviso).toBe("Solo hay 2 unidades");
  });

  it("usa el singular con una sola unidad disponible", () => {
    const una = makeProducto({ id: "p-4", stock_actual: 1 });
    const base = addProduct(vacio, una).cart;
    expect(addProduct(base, una).aviso).toBe("Solo hay 1 unidad");
  });

  it("no agrega un producto sin stock", () => {
    const sin = makeProducto({ id: "p-5", stock_actual: 0 });
    const { cart, aviso } = addProduct(vacio, sin);
    expect(cart).toHaveLength(0);
    expect(aviso).toBe("Sin stock");
  });

  it("refresca precio y stock con los datos mas recientes del producto", () => {
    const base = addProduct(vacio, royal).cart;
    const { cart } = addProduct(base, makeProducto({ id: "p-1", precio_venta: "1600.00", stock_actual: 8 }));
    expect(cart[0]).toMatchObject({ precioCents: 160000, stock: 8, cantidad: 2 });
  });

  it("no muta el carrito original", () => {
    const base = addProduct(vacio, royal).cart;
    addProduct(base, royal);
    expect(base[0]?.cantidad).toBe(1);
  });
});

describe("setQty y removeLine", () => {
  const base = addProduct(vacio, royal).cart;

  it("cambia la cantidad dentro del rango", () => {
    expect(setQty(base, "p-1", 4).cart[0]?.cantidad).toBe(4);
  });

  it("nunca baja de 1", () => {
    expect(setQty(base, "p-1", 0).cart[0]?.cantidad).toBe(1);
    expect(setQty(base, "p-1", -3).cart[0]?.cantidad).toBe(1);
  });

  it("topa en stock_actual con aviso", () => {
    const { cart, aviso } = setQty(base, "p-1", 99);
    expect(cart[0]?.cantidad).toBe(10);
    expect(aviso).toBe("Solo hay 10 unidades");
  });

  it("trunca cantidades no enteras e ignora NaN", () => {
    expect(setQty(base, "p-1", 3.9).cart[0]?.cantidad).toBe(3);
    expect(setQty(base, "p-1", Number.NaN).cart[0]?.cantidad).toBe(1);
  });

  it("quita la linea", () => {
    expect(removeLine(base, "p-1")).toHaveLength(0);
    expect(removeLine(base, "otro")).toHaveLength(1);
  });
});

describe("totales", () => {
  it("suma exacta en centavos: 2 x 1500 + 3 x 0,10 = 3000,30", () => {
    let cart = addProduct(vacio, royal, 2).cart;
    cart = addProduct(cart, snack, 3).cart;
    expect(totalCents(cart)).toBe(300030);
    expect(lineSubtotalCents(cart[1]!)).toBe(30);
    expect(unidadesTotales(cart)).toBe(5);
  });

  it("carrito vacio suma cero", () => {
    expect(totalCents(vacio)).toBe(0);
  });
});

describe("applyFaltantes y clampToDisponible", () => {
  const base = addProduct(addProduct(vacio, royal, 3).cart, snack, 2).cart;

  it("marca disponible solo en las lineas afectadas", () => {
    const marcado = applyFaltantes(base, [{ producto_id: "p-1", solicitado: 3, disponible: 1 }]);
    expect(marcado[0]?.disponible).toBe(1);
    expect(marcado[1]?.disponible).toBeUndefined();
  });

  it("clampToDisponible ajusta la cantidad, limpia la marca y avisa", () => {
    const marcado = applyFaltantes(base, [{ producto_id: "p-1", solicitado: 3, disponible: 1 }]);
    const { cart, aviso } = clampToDisponible(marcado);
    expect(cart[0]).toMatchObject({ cantidad: 1, stock: 1 });
    expect(cart[0]?.disponible).toBeUndefined();
    expect(cart[1]?.cantidad).toBe(2);
    expect(aviso).toContain("Ajustamos");
  });

  it("clampToDisponible quita las lineas sin ninguna unidad disponible", () => {
    const marcado = applyFaltantes(base, [{ producto_id: "p-2", solicitado: 2, disponible: 0 }]);
    const { cart } = clampToDisponible(marcado);
    expect(cart.map((l) => l.productoId)).toEqual(["p-1"]);
  });

  it("sin marcas no cambia nada ni avisa", () => {
    const { cart, aviso } = clampToDisponible(base);
    expect(cart).toEqual(base);
    expect(aviso).toBeNull();
  });
});

describe("cartSignature", () => {
  const a = addProduct(addProduct(vacio, royal, 2).cart, snack, 1).cart;
  const b = addProduct(addProduct(vacio, snack, 1).cart, royal, 2).cart;

  it("es estable ante distinto orden de lineas", () => {
    expect(cartSignature(a, null)).toBe(cartSignature(b, null));
  });

  it("cambia con otro cliente, otra cantidad u otro producto", () => {
    expect(cartSignature(a, "c-1")).not.toBe(cartSignature(a, null));
    expect(cartSignature(a, "c-1")).not.toBe(cartSignature(a, "c-2"));
    expect(cartSignature(setQty(a, "p-1", 3).cart, null)).not.toBe(cartSignature(a, null));
    expect(cartSignature(removeLine(a, "p-2"), null)).not.toBe(cartSignature(a, null));
  });
});

describe("syncPrecios", () => {
  it("actualiza el precio unitario de las lineas con el precio del servidor y recalcula el total", () => {
    const cart = addProduct(addProduct(vacio, royal, 2).cart, snack, 3).cart;
    const next = syncPrecios(cart, [
      { producto_id: "p-1", precio_unit: "1600.00" },
      { producto_id: "p-9", precio_unit: "5.00" },
    ]);
    expect(next.find((l) => l.productoId === "p-1")?.precioCents).toBe(160000);
    expect(next.find((l) => l.productoId === "p-2")?.precioCents).toBe(10);
    expect(totalCents(next)).toBe(2 * 160000 + 3 * 10);
  });
});
