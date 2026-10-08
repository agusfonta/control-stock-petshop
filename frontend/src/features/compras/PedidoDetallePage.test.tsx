import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { useSession } from "@/features/auth/session";
import { PedidoDetallePage } from "@/features/compras/PedidoDetallePage";
import { makeDistribuidora, makePedido } from "@/features/distribuidoras/testData";
import type { Me, Pedido } from "@/shared/api/types";
import { duena, makeProducto, mostrador, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

function sesion(user: Me): void {
  useSession.setState({ status: "authenticated", accessToken: "tok", user, expired: false });
}

interface Estado {
  pedido: Pedido;
  stock: number;
  recibirCalls: number;
  cancelarCalls: number;
}

/** Backend en memoria: recibir suma 10 unidades al producto (stock 4 -> 14). */
function mockBackend(inicial: Partial<Pedido> = {}): Estado {
  const estado: Estado = {
    pedido: makePedido({
      lineas: [{ id: "l-1", producto_id: "p-1", cantidad: 10, costo_unitario: "18000.00", subtotal: "180000.00" }],
      ...inicial,
    }),
    stock: 4,
    recibirCalls: 0,
    cancelarCalls: 0,
  };
  server.use(
    http.get("/api/compras/pedidos/ped-1", () => HttpResponse.json(estado.pedido)),
    http.get("/api/distribuidoras/d-1", () => HttpResponse.json(makeDistribuidora())),
    http.get("/api/distribuidoras", () => HttpResponse.json(paginated([makeDistribuidora()]))),
    http.get("/api/productos", () =>
      HttpResponse.json(paginated([makeProducto({ id: "p-1", nombre: "Royal Canin Mini Adult 3 kg", stock_actual: estado.stock })])),
    ),
    http.post("/api/compras/pedidos/ped-1/recibir", () => {
      estado.recibirCalls += 1;
      estado.stock += 10;
      estado.pedido = { ...estado.pedido, estado: "recibido", recibido_at: "2026-10-07T15:00:00Z" };
      return HttpResponse.json(estado.pedido);
    }),
    http.post("/api/compras/pedidos/ped-1/cancelar", () => {
      estado.cancelarCalls += 1;
      estado.pedido = { ...estado.pedido, estado: "cancelado" };
      return HttpResponse.json(estado.pedido);
    }),
  );
  return estado;
}

function renderDetalle() {
  return renderWithProviders(
    <>
      <Toaster />
      <Routes>
        <Route path="/compras/pedidos/:id" element={<PedidoDetallePage />} />
      </Routes>
    </>,
    { route: "/compras/pedidos/ped-1" },
  );
}

describe("PedidoDetallePage", () => {
  beforeEach(() => sesion(mostrador));

  it("muestra líneas con costo unitario, subtotal, total estimado y stock actual", async () => {
    mockBackend();
    renderDetalle();
    const tabla = await screen.findByRole("table", { name: /líneas del pedido/i });
    const fila = within(tabla).getAllByRole("row")[1] as HTMLElement;
    expect(await within(fila).findByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(within(fila).getByText(/18\.000,00/)).toBeInTheDocument();
    expect(within(fila).getByText(/180\.000,00/)).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    expect(screen.getByText(/Total estimado/i)).toBeInTheDocument();
  });

  it("el mostrador recibe el pedido: confirma, queda Recibido y el stock pasa de 4 a 14", async () => {
    const backend = mockBackend();
    const { user } = renderDetalle();
    await screen.findByText("Royal Canin Mini Adult 3 kg");
    expect(screen.queryByRole("button", { name: /cancelar pedido/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /recibir pedido/i }));
    const dialogo = await screen.findByRole("alertdialog");
    expect(within(dialogo).getByText(/suma todo el stock/i)).toBeInTheDocument();
    expect(backend.recibirCalls).toBe(0);
    await user.click(within(dialogo).getByRole("button", { name: /^recibir pedido$/i }));
    expect(await screen.findByText("Pedido recibido, stock actualizado")).toBeInTheDocument();
    expect(await screen.findByText("Recibido")).toBeInTheDocument();
    const tabla = screen.getByRole("table", { name: /líneas del pedido/i });
    expect(await within(tabla).findByText("14")).toBeInTheDocument();
    expect(backend.recibirCalls).toBe(1);
    expect(screen.queryByRole("button", { name: /recibir pedido/i })).not.toBeInTheDocument();
  });

  it("un 409 al recibir informa que ya no está pendiente y recarga el estado", async () => {
    const backend = mockBackend();
    server.use(
      http.post("/api/compras/pedidos/ped-1/recibir", () => {
        // Otra persona lo recibió justo antes.
        backend.pedido = { ...backend.pedido, estado: "recibido" };
        return HttpResponse.json({ detail: "el pedido esta recibido, no pendiente" }, { status: 409 });
      }),
    );
    const { user } = renderDetalle();
    await screen.findByText("Pendiente");
    await user.click(screen.getByRole("button", { name: /recibir pedido/i }));
    await user.click(await within(await screen.findByRole("alertdialog")).findByRole("button", { name: /^recibir pedido$/i }));
    expect(await screen.findByText("El pedido ya no está pendiente")).toBeInTheDocument();
    expect(await screen.findByText("Recibido")).toBeInTheDocument();
  });

  it("la dueña cancela el pedido con confirmación", async () => {
    sesion(duena);
    const backend = mockBackend();
    const { user } = renderDetalle();
    await screen.findByText("Royal Canin Mini Adult 3 kg");
    await user.click(screen.getByRole("button", { name: /cancelar pedido/i }));
    const dialogo = await screen.findByRole("alertdialog");
    await user.click(within(dialogo).getByRole("button", { name: /^cancelar pedido$/i }));
    expect(await screen.findByText("Pedido cancelado")).toBeInTheDocument();
    expect(await screen.findByText("Cancelado")).toBeInTheDocument();
    expect(backend.cancelarCalls).toBe(1);
    expect(backend.recibirCalls).toBe(0);
  });

  it("un pedido recibido no ofrece acciones", async () => {
    sesion(duena);
    mockBackend({ estado: "recibido" });
    renderDetalle();
    expect(await screen.findByText("Recibido")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /recibir pedido/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancelar pedido/i })).not.toBeInTheDocument();
  });
});
