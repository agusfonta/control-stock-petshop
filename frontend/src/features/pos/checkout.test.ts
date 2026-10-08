import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { cobrarVenta } from "@/features/pos/checkout";
import type { PagoDraft } from "@/features/pos/payments";
import { useCartStore } from "@/features/pos/useCartStore";
import { makeLineaVenta, makeVenta } from "@/features/ventas/testData";
import { makeCliente, makeProducto } from "@/test/fixtures";
import { server } from "@/test/server";

const royal = makeProducto({ id: "p-1", precio_venta: "3800.00", stock_actual: 5 });
const pagoEfectivo: PagoDraft[] = [{ id: "x1", metodo: "efectivo", montoCents: 380000 }];

interface Capturas {
  borradores: unknown[];
  confirmaciones: { id: string; body: unknown }[];
}

function montarApi(opts: { confirmar?: () => Response; crear?: () => Response; totalServidor?: string } = {}): Capturas {
  const c: Capturas = { borradores: [], confirmaciones: [] };
  const venta = makeVenta({ id: "v-1", estado: "borrador", total: opts.totalServidor ?? "3800.00" });
  server.use(
    http.post("/api/ventas", async ({ request }) => {
      c.borradores.push(await request.json());
      return opts.crear?.() ?? HttpResponse.json(venta, { status: 201 });
    }),
    http.post("/api/ventas/:id/confirmar", async ({ request, params }) => {
      c.confirmaciones.push({ id: String(params.id), body: await request.json() });
      return opts.confirmar?.() ?? HttpResponse.json(makeVenta({ id: "v-1" }));
    }),
  );
  return c;
}

const conflicto409 = (): Response =>
  HttpResponse.json(
    { detail: { mensaje: "Stock insuficiente", faltantes: [{ producto_id: "p-1", solicitado: 3, disponible: 1 }] } },
    { status: 409 },
  );

beforeEach(() => {
  useCartStore.getState().clear();
  useCartStore.getState().addProduct(royal, 1);
});

describe("cobrarVenta", () => {
  it("crea el borrador con idempotency_key, cliente y lineas sin precios, y confirma con pagos en string", async () => {
    const api = montarApi();
    useCartStore.getState().setCliente(makeCliente({ id: "c-9" }));
    const res = await cobrarVenta(pagoEfectivo);
    expect(res.tipo).toBe("ok");
    expect(api.borradores).toHaveLength(1);
    expect(api.borradores[0]).toEqual({
      idempotency_key: useCartStore.getState().checkout?.idempotencyKey,
      cliente_id: "c-9",
      lineas: [{ producto_id: "p-1", cantidad: 1 }],
    });
    expect(api.confirmaciones).toEqual([{ id: "v-1", body: { pagos: [{ metodo: "efectivo", monto: "3800.00" }] } }]);
  });

  it("un error de red al confirmar y el reintento reenvian el mismo id y los mismos pagos sin duplicar el borrador", async () => {
    let intentos = 0;
    const api = montarApi({
      confirmar: () => {
        intentos += 1;
        return intentos === 1 ? HttpResponse.error() : HttpResponse.json(makeVenta({ id: "v-1" }));
      },
    });
    const primero = await cobrarVenta(pagoEfectivo);
    expect(primero).toMatchObject({ tipo: "error", reintentable: true });
    const clave = useCartStore.getState().checkout?.idempotencyKey;

    const segundo = await cobrarVenta([], { reintento: true });
    expect(segundo.tipo).toBe("ok");
    expect(api.borradores).toHaveLength(1);
    expect(api.confirmaciones).toHaveLength(2);
    expect(api.confirmaciones[1]).toEqual(api.confirmaciones[0]);
    expect(useCartStore.getState().checkout?.idempotencyKey).toBe(clave);
  });

  it("un error de red al crear el borrador reintenta con la misma idempotency_key", async () => {
    let intentos = 0;
    const api = montarApi({
      crear: () => {
        intentos += 1;
        return intentos === 1 ? HttpResponse.error() : HttpResponse.json(makeVenta({ id: "v-1", estado: "borrador" }), { status: 200 });
      },
    });
    expect((await cobrarVenta(pagoEfectivo)).tipo).toBe("error");
    expect((await cobrarVenta(pagoEfectivo)).tipo).toBe("ok");
    expect(api.borradores).toHaveLength(2);
    expect(api.borradores[1]).toEqual(api.borradores[0]);
  });

  it("409 con faltantes al confirmar marca la linea con lo disponible y conserva el carrito", async () => {
    montarApi({ confirmar: conflicto409 });
    const res = await cobrarVenta(pagoEfectivo);
    expect(res.tipo).toBe("faltantes");
    const { lineas } = useCartStore.getState();
    expect(lineas).toHaveLength(1);
    expect(lineas[0]).toMatchObject({ productoId: "p-1", cantidad: 1, disponible: 1 });
    // No queda un "reintento" pendiente: al reabrir el cobro los pagos se editan normalmente.
    expect(useCartStore.getState().checkout?.pagos).toBeUndefined();
  });

  it("409 con faltantes al crear el borrador tambien marca las lineas", async () => {
    montarApi({ crear: conflicto409 });
    const res = await cobrarVenta(pagoEfectivo);
    expect(res.tipo).toBe("faltantes");
    expect(useCartStore.getState().lineas[0]?.disponible).toBe(1);
  });

  it("si el total del servidor difiere, actualiza precios y pide reconfirmar sin confirmar todavia", async () => {
    const api = montarApi({ totalServidor: "4000.00" });
    server.use(
      http.post("/api/ventas", () =>
        HttpResponse.json(
          makeVenta({
            id: "v-1",
            estado: "borrador",
            total: "4000.00",
            lineas: [makeLineaVenta({ precio_unit: "4000.00", subtotal: "4000.00" })],
          }),
          { status: 201 },
        ),
      ),
    );
    const res = await cobrarVenta(pagoEfectivo);
    expect(res).toEqual({ tipo: "precio-cambio", totalCents: 400000 });
    expect(api.confirmaciones).toHaveLength(0);
    expect(useCartStore.getState().total()).toBe(400000);
    expect(useCartStore.getState().checkout?.ventaId).toBe("v-1");

    const nuevo: PagoDraft[] = [{ id: "x1", metodo: "efectivo", montoCents: 400000 }];
    expect((await cobrarVenta(nuevo)).tipo).toBe("ok");
    expect(api.borradores).toHaveLength(0);
    expect(api.confirmaciones[0]?.body).toEqual({ pagos: [{ metodo: "efectivo", monto: "4000.00" }] });
  });

  it("422 devuelve el mensaje del servidor, no es reintentable y olvida los pagos enviados", async () => {
    montarApi({ confirmar: () => HttpResponse.json({ detail: "La suma de pagos no coincide" }, { status: 422 }) });
    const res = await cobrarVenta(pagoEfectivo);
    expect(res).toMatchObject({ tipo: "error", reintentable: false });
    expect(res.tipo === "error" && res.mensaje).toBe("La suma de pagos no coincide");
    expect(useCartStore.getState().checkout?.pagos).toBeUndefined();
  });

  it("404 al crear el borrador pide refrescar y no es reintentable", async () => {
    montarApi({ crear: () => HttpResponse.json({ detail: "producto no encontrado" }, { status: 404 }) });
    const res = await cobrarVenta(pagoEfectivo);
    expect(res).toMatchObject({ tipo: "error", reintentable: false, refrescar: true });
  });
});
