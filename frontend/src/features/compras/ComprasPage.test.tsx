import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { type ReactElement } from "react";
import { Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { useSession } from "@/features/auth/session";
import { ComprasPage } from "@/features/compras/ComprasPage";
import {
  makeCuenta,
  makeDistribuidora,
  makeListaPrecio,
  makePago,
  makePedido,
} from "@/features/distribuidoras/testData";
import type { Me, PagoDistribuidora } from "@/shared/api/types";
import { duena, makeProducto, mostrador, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

function sesion(user: Me): void {
  useSession.setState({ status: "authenticated", accessToken: "tok", user, expired: false });
}

function Sonda(): ReactElement {
  const { pathname, search } = useLocation();
  return <output data-testid="ubicacion">{`${pathname}${search}`}</output>;
}

function renderCompras(route: string) {
  return renderWithProviders(
    <>
      <Toaster />
      <Sonda />
      <Routes>
        <Route path="/compras" element={<ComprasPage />} />
        <Route path="/compras/pedidos/:id" element={<p>Detalle del pedido</p>} />
      </Routes>
    </>,
    { route },
  );
}

const rc = makeProducto({ id: "p-1", sku: "RC-MINI-3KG", nombre: "Royal Canin Mini Adult 3 kg", stock_actual: 1, stock_minimo: 3 });
const norte = makeDistribuidora({ id: "d-1", nombre: "Distribuidora Norte" });
const sur = makeDistribuidora({ id: "d-2", nombre: "Mayorista Sur" });

function mockBase(): void {
  server.use(
    http.get("/api/distribuidoras", () => HttpResponse.json(paginated([norte, sur]))),
    http.get("/api/productos", () => HttpResponse.json(paginated([rc]))),
    http.get("/api/productos/buscar", () => HttpResponse.json(paginated([rc]))),
    http.get("/api/stock/alertas", () =>
      HttpResponse.json({ total_bajo_minimo: 1, items: [{ ...rc, bajo_minimo: true }] }),
    ),
    http.get("/api/distribuidoras/:id/listas", ({ params }) =>
      HttpResponse.json(
        params.id === "d-1" ? [makeListaPrecio({ producto_id: "p-1", costo: "18000.00" })] : [],
      ),
    ),
    http.get("/api/compras/pedidos", () => HttpResponse.json(paginated([makePedido()]))),
  );
}

describe("ComprasPage - pedidos", () => {
  beforeEach(() => {
    sesion(mostrador);
    mockBase();
  });

  it("lista pedidos con distribuidora, estado y total, y filtra por estado", async () => {
    const estados: (string | null)[] = [];
    server.use(
      http.get("/api/compras/pedidos", ({ request }) => {
        estados.push(new URL(request.url).searchParams.get("estado"));
        return HttpResponse.json(paginated([makePedido()]));
      }),
    );
    const { user } = renderCompras("/compras");
    expect(await screen.findByText("Distribuidora Norte")).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    expect(screen.getByText(/180\.000,00/)).toBeInTheDocument();
    await user.click(screen.getByRole("combobox", { name: /filtrar por estado/i }));
    await user.click(await screen.findByRole("option", { name: "Recibido" }));
    await waitFor(() => expect(estados).toContain("recibido"));
  });

  it("el mostrador no ve las pestañas de pagos y cuentas", async () => {
    renderCompras("/compras");
    await screen.findByText("Distribuidora Norte");
    expect(screen.getByRole("tab", { name: "Pedidos" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Pagos" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Cuentas" })).not.toBeInTheDocument();
  });

  it("crea un pedido eligiendo distribuidora y productos (el cliente no envía costos)", async () => {
    let enviado: unknown = null;
    server.use(
      http.post("/api/compras/pedidos", async ({ request }) => {
        enviado = await request.json();
        return HttpResponse.json(makePedido({ id: "ped-nuevo" }), { status: 201 });
      }),
    );
    const { user } = renderCompras("/compras");
    await user.click(await screen.findByRole("button", { name: /nuevo pedido/i }));
    const panel = await screen.findByRole("dialog", { name: /nuevo pedido/i });
    await user.click(within(panel).getByRole("button", { name: /^crear pedido$/i }));
    expect(await within(panel).findByText("Elegí una distribuidora")).toBeInTheDocument();
    await user.click(within(panel).getByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "Distribuidora Norte" }));
    await user.click(await within(panel).findByRole("button", { name: /agregar royal canin mini/i }));
    const cantidad = within(panel).getByLabelText(/cantidad de royal canin/i);
    expect(cantidad).toHaveValue(5);
    await user.clear(cantidad);
    await user.type(cantidad, "10");
    expect(within(panel).getByText(/180\.000,00/)).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: /^crear pedido$/i }));
    expect(await screen.findByText("Pedido creado")).toBeInTheDocument();
    expect(enviado).toEqual({
      distribuidora_id: "d-1",
      lineas: [{ producto_id: "p-1", cantidad: 10 }],
      notas: null,
    });
    expect(await screen.findByText("Detalle del pedido")).toBeInTheDocument();
  });

  it("desde Reposición (?nuevo=1&distribuidora&producto) abre el alta con todo preparado y limpia la URL al cerrar", async () => {
    const { user } = renderCompras("/compras?nuevo=1&distribuidora=d-1&producto=p-1");
    const panel = await screen.findByRole("dialog", { name: /nuevo pedido/i });
    expect(await within(panel).findByRole("combobox")).toHaveTextContent("Distribuidora Norte");
    // Cantidad razonable: reponer hasta el doble del mínimo (3*2 - 1 = 5).
    expect(await within(panel).findByLabelText(/cantidad de royal canin/i)).toHaveValue(5);
    await user.click(within(panel).getByRole("button", { name: /^cancelar$/i }));
    await waitFor(() => expect(screen.getByTestId("ubicacion")).toHaveTextContent(/^\/compras\?tab=pedidos$/));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /nuevo pedido/i })).not.toBeInTheDocument());
  });

  it("sin producto en la URL abre el alta solo con la distribuidora elegida", async () => {
    renderCompras("/compras?nuevo=1&distribuidora=d-2");
    const panel = await screen.findByRole("dialog", { name: /nuevo pedido/i });
    expect(await within(panel).findByRole("combobox")).toHaveTextContent("Mayorista Sur");
    expect(within(panel).getByText("Todavía no agregaste productos.")).toBeInTheDocument();
  });
});

describe("ComprasPage - pagos y cuentas (dueña)", () => {
  beforeEach(() => {
    sesion(duena);
    mockBase();
  });

  it("registra un pago de 50000 y la cuenta muestra pagado $ 50.000,00 y saldo $ 70.000,00", async () => {
    const pagos: PagoDistribuidora[] = [];
    let enviado: Record<string, unknown> | null = null;
    server.use(
      http.get("/api/compras/pagos", () => HttpResponse.json(paginated(pagos))),
      http.post("/api/compras/pagos", async ({ request }) => {
        enviado = (await request.json()) as Record<string, unknown>;
        pagos.push(makePago({ monto: "50000.00" }));
        return HttpResponse.json(pagos[0], { status: 201 });
      }),
      http.get("/api/compras/distribuidoras/:id/cuenta", ({ params }) => {
        const pagado = params.id === "d-1" && pagos.length > 0 ? "50000.00" : "0.00";
        const saldo = params.id === "d-1" ? (pagos.length > 0 ? "70000.00" : "120000.00") : "0.00";
        return HttpResponse.json(
          makeCuenta({
            distribuidora_id: String(params.id),
            total_recibido: params.id === "d-1" ? "120000.00" : "0.00",
            total_pagado: pagado,
            saldo,
          }),
        );
      }),
    );
    const { user } = renderCompras("/compras?tab=pagos");
    expect(await screen.findByText("Todavía no registraste pagos")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /registrar pago/i })[0] as HTMLElement);
    const panel = await screen.findByRole("dialog", { name: /registrar pago/i });
    await user.click(within(panel).getByRole("button", { name: /^registrar pago$/i }));
    expect(await within(panel).findByText("Elegí una distribuidora")).toBeInTheDocument();
    await user.click(within(panel).getByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "Distribuidora Norte" }));
    await user.type(within(panel).getByLabelText("Monto"), "50000");
    await user.click(within(panel).getByRole("button", { name: /^registrar pago$/i }));
    expect(await screen.findByText("Pago registrado")).toBeInTheDocument();
    expect(enviado).toMatchObject({ distribuidora_id: "d-1", monto: "50000.00", metodo: "transferencia" });
    expect(String(enviado === null ? "" : (enviado as Record<string, unknown>).fecha)).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    await waitFor(() => expect(screen.queryByRole("dialog", { name: /registrar pago/i })).not.toBeInTheDocument(), {
      timeout: 5000,
    });
    await user.click(await screen.findByRole("tab", { name: "Cuentas" }));
    const tarjeta = (await screen.findByText("Distribuidora Norte")).closest("[data-slot='card']") as HTMLElement;
    expect(await within(tarjeta).findByText(/70\.000,00/)).toBeInTheDocument();
    expect(within(tarjeta).getByText(/50\.000,00/)).toBeInTheDocument();
    expect(within(tarjeta).getByText("Saldo deudor")).toBeInTheDocument();
  }, 20_000);

  it("anula un pago con confirmación", async () => {
    let anulado = false;
    server.use(
      http.get("/api/compras/pagos", () => HttpResponse.json(paginated(anulado ? [] : [makePago()]))),
      http.delete("/api/compras/pagos/pg-1", () => {
        anulado = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderCompras("/compras?tab=pagos");
    await user.click(await screen.findByRole("button", { name: /acciones del pago/i }));
    await user.click(await screen.findByRole("menuitem", { name: /anular pago/i }));
    const dialogo = await screen.findByRole("alertdialog");
    expect(anulado).toBe(false);
    await user.click(within(dialogo).getByRole("button", { name: /^anular pago$/i }));
    expect(await screen.findByText("Pago anulado")).toBeInTheDocument();
    expect(await screen.findByText("Todavía no registraste pagos")).toBeInTheDocument();
  });
});
