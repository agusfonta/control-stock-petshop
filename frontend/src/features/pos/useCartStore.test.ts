import { beforeEach, describe, expect, it } from "vitest";
import { useCartStore } from "@/features/pos/useCartStore";
import { useSession } from "@/features/auth/session";
import { makeCliente, makeProducto } from "@/test/fixtures";

const royal = makeProducto({ id: "p-1", precio_venta: "1500.00", stock_actual: 10 });
const snack = makeProducto({ id: "p-2", sku: "SN-1", nombre: "Snack", precio_venta: "0.10", stock_actual: 50 });

beforeEach(() => {
  useCartStore.getState().clear();
});

describe("useCartStore: carrito", () => {
  it("agrega, suma y calcula el total", () => {
    const { addProduct } = useCartStore.getState();
    addProduct(royal, 2);
    addProduct(snack, 3);
    const { lineas } = useCartStore.getState();
    expect(lineas).toHaveLength(2);
    expect(useCartStore.getState().total()).toBe(300030);
  });

  it("devuelve el aviso de tope y no supera el stock", () => {
    const chico = makeProducto({ id: "p-3", stock_actual: 2 });
    const { addProduct } = useCartStore.getState();
    addProduct(chico, 2);
    expect(addProduct(chico)).toBe("Solo hay 2 unidades");
    expect(useCartStore.getState().lineas[0]?.cantidad).toBe(2);
  });

  it("conserva el carrito al desmontar la pagina (el store vive fuera del arbol)", () => {
    useCartStore.getState().addProduct(royal);
    useCartStore.getState().setCliente(makeCliente({ id: "c-9" }));
    // Otra "pagina" lee el mismo store.
    expect(useCartStore.getState().lineas).toHaveLength(1);
    expect(useCartStore.getState().cliente?.id).toBe("c-9");
  });

  it("quita lineas, cambia cantidades y vacia", () => {
    const store = useCartStore.getState();
    store.addProduct(royal);
    store.addProduct(snack);
    store.setQty("p-1", 4);
    expect(useCartStore.getState().lineas[0]?.cantidad).toBe(4);
    store.removeLine("p-2");
    expect(useCartStore.getState().lineas).toHaveLength(1);
    store.clear();
    expect(useCartStore.getState().lineas).toHaveLength(0);
    expect(useCartStore.getState().cliente).toBeNull();
  });

  it("marca faltantes y ajusta a disponible", () => {
    const store = useCartStore.getState();
    store.addProduct(royal, 3);
    store.applyFaltantes([{ producto_id: "p-1", solicitado: 3, disponible: 1 }]);
    expect(useCartStore.getState().lineas[0]?.disponible).toBe(1);
    store.clampToDisponible();
    expect(useCartStore.getState().lineas[0]).toMatchObject({ cantidad: 1, stock: 1 });
    expect(useCartStore.getState().lineas[0]?.disponible).toBeUndefined();
  });
});

describe("useCartStore: checkout idempotente (D9)", () => {
  it("reutiliza la idempotencyKey con la misma firma", () => {
    const store = useCartStore.getState();
    store.addProduct(royal, 2);
    const primero = store.prepareCheckout();
    const segundo = useCartStore.getState().prepareCheckout();
    expect(segundo.idempotencyKey).toBe(primero.idempotencyKey);
    expect(segundo.signature).toBe(primero.signature);
  });

  it("genera otra clave si cambia el carrito o el cliente", () => {
    const store = useCartStore.getState();
    store.addProduct(royal, 2);
    const base = store.prepareCheckout();

    useCartStore.getState().setQty("p-1", 3);
    const cambioCantidad = useCartStore.getState().prepareCheckout();
    expect(cambioCantidad.idempotencyKey).not.toBe(base.idempotencyKey);

    useCartStore.getState().setCliente(makeCliente({ id: "c-1" }));
    const cambioCliente = useCartStore.getState().prepareCheckout();
    expect(cambioCliente.idempotencyKey).not.toBe(cambioCantidad.idempotencyKey);
  });

  it("al cambiar la firma se descartan ventaId y pagos del intento anterior", () => {
    const store = useCartStore.getState();
    store.addProduct(royal);
    store.prepareCheckout();
    store.patchCheckout({ ventaId: "v-1", pagos: [{ metodo: "efectivo", monto: "1500.00" }] });
    expect(useCartStore.getState().checkout?.ventaId).toBe("v-1");

    useCartStore.getState().setQty("p-1", 2);
    const nuevo = useCartStore.getState().prepareCheckout();
    expect(nuevo.ventaId).toBeUndefined();
    expect(nuevo.pagos).toBeUndefined();
  });

  it("mantiene ventaId y pagos en un reintento sin cambios", () => {
    const store = useCartStore.getState();
    store.addProduct(royal);
    store.prepareCheckout();
    store.patchCheckout({ ventaId: "v-1", pagos: [{ metodo: "efectivo", monto: "1500.00" }] });
    const reintento = useCartStore.getState().prepareCheckout();
    expect(reintento.ventaId).toBe("v-1");
    expect(reintento.pagos).toEqual([{ metodo: "efectivo", monto: "1500.00" }]);
  });

  it("vaciar el carrito borra el checkout", () => {
    const store = useCartStore.getState();
    store.addProduct(royal);
    store.prepareCheckout();
    store.clear();
    expect(useCartStore.getState().checkout).toBeNull();
  });
});

describe("useCartStore: cierre de sesion", () => {
  it("se vacia al cerrar sesion", () => {
    useCartStore.getState().addProduct(royal);
    useCartStore.getState().setCliente(makeCliente());
    useSession.getState().logout();
    expect(useCartStore.getState().lineas).toHaveLength(0);
    expect(useCartStore.getState().cliente).toBeNull();
  });
});
