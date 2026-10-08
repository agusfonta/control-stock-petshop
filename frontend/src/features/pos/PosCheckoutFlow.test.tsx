import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PosPage } from "@/features/pos/PosPage";
import { useCartStore } from "@/features/pos/useCartStore";
import { makeLineaVenta, makePagoVenta, makeVenta } from "@/features/ventas/testData";
import { makeProducto, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const royal = makeProducto({ id: "p-1", sku: "RC-MINI-3KG", precio_venta: "24300.00", stock_actual: 10 });
const ESPERA = { timeout: 4000 };

const confirmada = makeVenta({
  id: "f0e1d2c3-0000-4000-8000-000000000009",
  total: "24300.00",
  lineas: [makeLineaVenta({ producto_id: "p-1", producto_nombre: royal.nombre, cantidad: 1, precio_unit: "24300.00", subtotal: "24300.00" })],
  pagos: [makePagoVenta({ monto: "24300.00" })],
});

beforeEach(() => {
  useCartStore.getState().clear();
  server.use(
    http.get("/api/productos/buscar", () => HttpResponse.json(paginated([royal]))),
    http.post("/api/ventas", () => HttpResponse.json({ ...confirmada, estado: "borrador" }, { status: 201 })),
    http.post("/api/ventas/:id/confirmar", () => HttpResponse.json(confirmada)),
  );
});

describe("POS: de la busqueda al comprobante", () => {
  it("escanear, cobrar con vuelto y volver a vender usando solo el teclado", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    const { user } = renderWithProviders(<PosPage />);

    await user.type(screen.getByRole("searchbox", { name: /buscar producto/i }), "RC-MINI-3KG{Enter}");
    await waitFor(() => expect(useCartStore.getState().lineas).toHaveLength(1), ESPERA);

    await user.keyboard("{F9}");
    const panel = await screen.findByRole("dialog", { name: /cobrar/i });
    const pagaCon = within(panel).getByRole("textbox", { name: /paga con/i });
    await waitFor(() => expect(pagaCon).toHaveFocus());
    await user.type(pagaCon, "30000{Enter}");

    const exito = await screen.findByRole("dialog", { name: /venta registrada/i }, ESPERA);
    expect(within(exito).getByText(/F0E1D2C3/)).toBeInTheDocument();
    expect(within(exito).getByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(within(exito).getByText("Total").closest("div")).toHaveTextContent("24.300,00");
    expect(within(exito).getByText("Efectivo").closest("div")).toHaveTextContent("24.300,00");
    expect(within(exito).getByText("Vuelto").closest("div")).toHaveTextContent("5.700,00");
    expect(within(exito).getByText("Comprobante no válido como factura")).toBeInTheDocument();
    expect(useCartStore.getState().lineas).toHaveLength(0);

    await user.click(within(exito).getByRole("button", { name: /imprimir/i }));
    expect(print).toHaveBeenCalledTimes(1);
    expect(document.querySelector("#print-root")).toHaveTextContent("Comprobante no válido como factura");

    expect(within(exito).getByRole("button", { name: /nueva venta/i })).toHaveFocus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /venta registrada/i })).not.toBeInTheDocument(), ESPERA);
    await waitFor(() => expect(screen.getByRole("searchbox", { name: /buscar producto/i })).toHaveFocus());
    expect(document.querySelector("#print-root")).toBeEmptyDOMElement();
  });
});
