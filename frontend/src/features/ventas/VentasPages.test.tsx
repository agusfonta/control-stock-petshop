import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { hoyLocal, rangoQuery } from "@/features/ventas/filtros";
import { makeVenta, makeVentaResumen } from "@/features/ventas/testData";
import type { Me, Venta } from "@/shared/api/types";
import { duena, makeCliente, mostrador, paginated } from "@/test/fixtures";
import { renderApp } from "@/test/renderApp";
import { server } from "@/test/server";

const ESPERA = { timeout: 4000 };

function montarListado(): { consultas: URLSearchParams[] } {
  const consultas: URLSearchParams[] = [];
  server.use(
    http.get("/api/ventas", ({ request }) => {
      consultas.push(new URL(request.url).searchParams);
      return HttpResponse.json(
        paginated([
          makeVentaResumen({ id: "aaaaaaaa-0000-4000-8000-000000000001", usuario_id: duena.id, cliente_id: "c-1", total: "5300.00" }),
          makeVentaResumen({ id: "bbbbbbbb-0000-4000-8000-000000000002", usuario_id: mostrador.id, estado: "anulada", total: "1200.00" }),
        ]),
      );
    }),
    http.get("/api/clientes", () => HttpResponse.json(paginated([makeCliente({ id: "c-1", nombre: "Ana Perez" })]))),
  );
  return { consultas };
}

describe("VentasPage (listado)", () => {
  it("por defecto pide el dia de hoy y muestra cliente, vendedor ('Vos' / 'Otro usuario'), total y estado", async () => {
    const { consultas } = montarListado();
    renderApp({ route: "/ventas", user: duena });
    const tabla = await screen.findByRole("table", { name: /ventas/i }, ESPERA);
    const hoy = hoyLocal();
    await waitFor(() => expect(consultas.length).toBeGreaterThan(0));
    const q = consultas[0];
    expect(q?.get("desde")).toBe(rangoQuery(hoy, hoy).desde);
    expect(q?.get("hasta")).toBe(rangoQuery(hoy, hoy).hasta);
    expect(q?.get("estado")).toBeNull();

    const filas = within(tabla).getAllByRole("row");
    const primera = filas[1];
    expect(primera).toHaveTextContent("AAAAAAAA");
    expect(await within(tabla).findByText("Ana Perez")).toBeInTheDocument();
    expect(primera).toHaveTextContent("Vos");
    expect(primera).toHaveTextContent("5.300,00");
    expect(primera).toHaveTextContent("Confirmada");
    expect(filas[2]).toHaveTextContent("Otro usuario");
    expect(filas[2]).toHaveTextContent("Anulada");
  });

  it("filtrar por estado Anuladas envia estado=anulada", async () => {
    const { consultas } = montarListado();
    const { user } = renderApp({ route: "/ventas", user: duena });
    await screen.findByRole("table", { name: /ventas/i }, ESPERA);
    await user.click(screen.getByRole("combobox", { name: /estado/i }));
    await user.click(await screen.findByRole("option", { name: "Anuladas" }));
    await waitFor(() => expect(consultas.some((p) => p.get("estado") === "anulada")).toBe(true), ESPERA);
  });

  it("sin ventas muestra un estado vacio con el dia consultado", async () => {
    server.use(
      http.get("/api/ventas", () => HttpResponse.json(paginated([]))),
      http.get("/api/clientes", () => HttpResponse.json(paginated([]))),
    );
    renderApp({ route: "/ventas", user: mostrador });
    expect(await screen.findByText(/no hay ventas/i, undefined, ESPERA)).toBeInTheDocument();
  });
});

function montarDetalle(inicial: Venta): { anulaciones: unknown[] } {
  let actual = inicial;
  const anulaciones: unknown[] = [];
  server.use(
    http.get("/api/ventas/:id", () => HttpResponse.json(actual)),
    http.post("/api/ventas/:id/anular", async ({ request }) => {
      const body = (await request.json()) as { motivo: string };
      anulaciones.push(body);
      actual = { ...actual, estado: "anulada", anulada_at: "2026-10-01T16:00:00Z", motivo_anulacion: body.motivo };
      return HttpResponse.json(actual);
    }),
    http.get("/api/clientes", () => HttpResponse.json(paginated([]))),
  );
  return { anulaciones };
}

function abrirDetalle(user: Me): ReturnType<typeof renderApp> {
  return renderApp({ route: "/ventas/a1b2c3d4-0000-4000-8000-000000000001", user });
}

describe("VentaDetallePage", () => {
  beforeEach(() => undefined);

  it("la duena anula con motivo y la venta pasa a Anulada con ese motivo", async () => {
    const { anulaciones } = montarDetalle(makeVenta({ usuario_id: mostrador.id }));
    const { user } = abrirDetalle(duena);
    await user.click(await screen.findByRole("button", { name: "Anular venta" }, ESPERA));
    const dialogo = await screen.findByRole("alertdialog");
    await user.type(within(dialogo).getByRole("textbox", { name: /motivo/i }), "cliente se arrepintió");
    await user.click(within(dialogo).getByRole("button", { name: "Anular venta" }));
    expect(await screen.findByText("cliente se arrepintió", undefined, ESPERA)).toBeInTheDocument();
    expect(anulaciones).toEqual([{ motivo: "cliente se arrepintió" }]);
    expect(screen.getAllByText("Anulada").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Anular venta" })).not.toBeInTheDocument();
  });

  it("sin motivo no se envia y el campo muestra 'Indicá el motivo'", async () => {
    const { anulaciones } = montarDetalle(makeVenta());
    const { user } = abrirDetalle(duena);
    await user.click(await screen.findByRole("button", { name: "Anular venta" }, ESPERA));
    const dialogo = await screen.findByRole("alertdialog");
    await user.click(within(dialogo).getByRole("button", { name: "Anular venta" }));
    expect(await within(dialogo).findByText("Indicá el motivo")).toBeInTheDocument();
    expect(anulaciones).toHaveLength(0);
  });

  it("el mostrador no ve 'Anular venta' en su venta confirmada", async () => {
    montarDetalle(makeVenta({ usuario_id: mostrador.id }));
    abrirDetalle(mostrador);
    await screen.findByRole("table", { name: /productos de la venta/i }, ESPERA);
    expect(screen.queryByRole("button", { name: "Anular venta" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reimprimir/i })).toBeInTheDocument();
  });

  it("muestra lineas, pagos y vendedor", async () => {
    montarDetalle(makeVenta({ usuario_id: duena.id }));
    abrirDetalle(duena);
    await screen.findByRole("table", { name: /productos de la venta/i }, ESPERA);
    expect(screen.getByText("Vos")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /pagos/i })).toHaveTextContent("Efectivo");
  });

  it("una venta ajena (404) muestra que no se encontro", async () => {
    server.use(
      http.get("/api/ventas/:id", () => HttpResponse.json({ detail: "venta no encontrada" }, { status: 404 })),
      http.get("/api/clientes", () => HttpResponse.json(paginated([]))),
    );
    abrirDetalle(mostrador);
    expect(await screen.findByText(/no encontramos esta venta/i, undefined, ESPERA)).toBeInTheDocument();
  });
});
