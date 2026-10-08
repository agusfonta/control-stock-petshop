import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { type ReactElement, useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CheckoutSheet } from "@/features/pos/CheckoutSheet";
import { useCartStore } from "@/features/pos/useCartStore";
import { makeVenta } from "@/features/ventas/testData";
import type { Venta } from "@/shared/api/types";
import { makeProducto } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const royal = makeProducto({ id: "p-1", precio_venta: "3800.00", stock_actual: 5 });
const onSuccess = vi.fn<(venta: Venta, vuelto: number | null) => void>();
const onOpenChange = vi.fn<(open: boolean) => void>();

function Host(): ReactElement {
  const [open, setOpen] = useState(true);
  return (
    <CheckoutSheet
      open={open}
      onOpenChange={(v) => {
        onOpenChange(v);
        setOpen(v);
      }}
      onSuccess={onSuccess}
    />
  );
}

interface Capturas {
  borradores: number;
  confirmaciones: unknown[];
}

function montarApi(confirmar?: (n: number) => Response): Capturas {
  const c: Capturas = { borradores: 0, confirmaciones: [] };
  server.use(
    http.post("/api/ventas", () => {
      c.borradores += 1;
      return HttpResponse.json(makeVenta({ id: "v-1", estado: "borrador" }), { status: 201 });
    }),
    http.post("/api/ventas/:id/confirmar", async ({ request }) => {
      c.confirmaciones.push(await request.json());
      return confirmar?.(c.confirmaciones.length) ?? HttpResponse.json(makeVenta({ id: "v-1" }));
    }),
    http.get("/api/stock/alertas", () => HttpResponse.json({ total_bajo_minimo: 0, items: [] })),
  );
  return c;
}

const ESPERA = { timeout: 4000 };

beforeEach(() => {
  onSuccess.mockReset();
  onOpenChange.mockReset();
  useCartStore.getState().clear();
  useCartStore.getState().addProduct(royal, 1);
});

describe("CheckoutSheet: pagos", () => {
  it("propone efectivo por el total y habilita Confirmar venta", async () => {
    renderWithProviders(<Host />);
    expect(await screen.findByRole("textbox", { name: /monto efectivo/i })).toHaveValue("3800");
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeEnabled();
  });

  it("ofrece solo efectivo, transferencia y tarjeta", async () => {
    renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: /monto efectivo/i });
    const medios = screen.getAllByRole("radio").map((r) => r.textContent?.trim());
    expect(medios).toEqual(["Efectivo", "Transferencia", "Tarjeta"]);
  });

  it("paga con $ 5.000 muestra el vuelto y confirma con un pago efectivo de 3800", async () => {
    const api = montarApi();
    const { user } = renderWithProviders(<Host />);
    await user.type(await screen.findByRole("textbox", { name: /paga con/i }), "5000");
    expect(screen.getByText(/vuelto/i).closest("div")).toHaveTextContent(/1\.200,00/);
    await user.click(screen.getByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), ESPERA);
    expect(api.confirmaciones).toEqual([{ pagos: [{ metodo: "efectivo", monto: "3800.00" }] }]);
    expect(onSuccess.mock.calls[0]?.[1]).toBe(120000);
    expect(useCartStore.getState().lineas).toHaveLength(0);
  });

  it("pago dividido incompleto muestra 'Faltan' y deshabilita la confirmacion", async () => {
    const { user } = renderWithProviders(<Host />);
    const efectivo = await screen.findByRole("textbox", { name: /monto efectivo/i });
    await user.clear(efectivo);
    await user.type(efectivo, "1800");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    const segundo = screen.getByRole("textbox", { name: /monto transferencia/i });
    expect(segundo).toHaveValue("2000");
    await user.clear(segundo);
    await user.type(segundo, "1500");
    expect(screen.getByText(/faltan/i)).toHaveTextContent("$ 500,00");
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeDisabled();
  });

  it("muestra 'Sobran' cuando los pagos superan el total", async () => {
    const { user } = renderWithProviders(<Host />);
    const efectivo = await screen.findByRole("textbox", { name: /monto efectivo/i });
    await user.clear(efectivo);
    await user.type(efectivo, "4000");
    expect(screen.getByText(/sobran/i)).toHaveTextContent("$ 200,00");
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeDisabled();
  });

  it("no permite agregar mas de 5 medios", async () => {
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: /monto efectivo/i });
    for (let i = 0; i < 4; i += 1) {
      await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    }
    expect(screen.getByRole("button", { name: /agregar otro medio/i })).toBeDisabled();
  });
});

describe("CheckoutSheet: confirmacion", () => {
  it("409 con faltantes marca 'Disponible' en el carrito, conserva las lineas y cierra el panel", async () => {
    montarApi(() =>
      HttpResponse.json(
        { detail: { mensaje: "Stock insuficiente", faltantes: [{ producto_id: "p-1", solicitado: 3, disponible: 1 }] } },
        { status: 409 },
      ),
    );
    const { user } = renderWithProviders(<Host />);
    await user.click(await screen.findByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false), ESPERA);
    expect(useCartStore.getState().lineas[0]).toMatchObject({ productoId: "p-1", disponible: 1 });
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("error de red + Reintentar envia la misma idempotency_key y los mismos pagos: una sola venta", async () => {
    const api = montarApi((n) => (n === 1 ? HttpResponse.error() : HttpResponse.json(makeVenta({ id: "v-1" }))));
    const { user } = renderWithProviders(<Host />);
    await user.click(await screen.findByRole("button", { name: /confirmar venta/i }));
    const reintentar = await screen.findByRole("button", { name: /reintentar/i }, ESPERA);
    const clave = useCartStore.getState().checkout?.idempotencyKey;
    await user.click(reintentar);
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1), ESPERA);
    expect(api.borradores).toBe(1);
    expect(api.confirmaciones).toHaveLength(2);
    expect(api.confirmaciones[1]).toEqual(api.confirmaciones[0]);
    expect(useCartStore.getState().checkout).toBeNull();
    expect(clave).toBeDefined();
  });

  it("un 422 se muestra en el panel y deja corregir los pagos", async () => {
    montarApi(() => HttpResponse.json({ detail: "La suma de pagos no coincide" }, { status: 422 }));
    const { user } = renderWithProviders(<Host />);
    await user.click(await screen.findByRole("button", { name: /confirmar venta/i }));
    expect(await screen.findByText("La suma de pagos no coincide", undefined, ESPERA)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeEnabled();
  });
});
