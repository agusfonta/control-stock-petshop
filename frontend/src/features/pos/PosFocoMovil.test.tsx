import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PosPage } from "@/features/pos/PosPage";
import { useCartStore } from "@/features/pos/useCartStore";
import { makeProducto, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

vi.mock("@/shared/hooks/use-mobile", () => ({ useIsMobile: () => true }));

const royal = makeProducto({ id: "p-1", sku: "RC-MINI-3KG", precio_venta: "24300.00", stock_actual: 10 });
const ESPERA = { timeout: 4000 };

beforeEach(() => {
  useCartStore.getState().clear();
  server.use(http.get("/api/productos/buscar", () => HttpResponse.json(paginated([royal]))));
});

describe("POS en telefono: foco al cerrar el cobro (UX12)", () => {
  it("Escape en el panel de cobro devuelve el foco a 'Ver carrito', no a la pagina", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(screen.getByRole("searchbox", { name: /buscar producto/i }), "RC-MINI-3KG{Enter}");
    await waitFor(() => expect(useCartStore.getState().lineas).toHaveLength(1), ESPERA);

    await user.click(screen.getByRole("button", { name: /ver carrito/i }));
    const carrito = await screen.findByRole("dialog", { name: /carrito/i });
    await user.click(within(carrito).getByRole("button", { name: /^cobrar/i }));
    await screen.findByRole("dialog", { name: /cobrar/i });

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /cobrar/i })).not.toBeInTheDocument(), ESPERA);
    await waitFor(() => expect(screen.getByRole("button", { name: /ver carrito/i })).toHaveFocus());
  });
});
