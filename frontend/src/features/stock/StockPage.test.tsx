import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useSession } from "@/features/auth/session";
import { Toaster } from "@/components/ui/sonner";
import { StockPage } from "@/features/stock/StockPage";
import type { Me, StockItem } from "@/shared/api/types";
import { duena, makeProducto, mostrador, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

function sesion(user: Me): void {
  useSession.setState({ status: "authenticated", accessToken: "tok", user, expired: false });
}

function item(overrides: Partial<StockItem> = {}): StockItem {
  const base = makeProducto(overrides);
  return { ...base, bajo_minimo: base.stock_actual <= base.stock_minimo, ...overrides };
}

interface Estado {
  items: StockItem[];
  ajustes: unknown[];
  consultas: URLSearchParams[];
}

function mockStock(items: StockItem[]): Estado {
  const estado: Estado = { items: [...items], ajustes: [], consultas: [] };
  server.use(
    http.get("/api/stock", ({ request }) => {
      const params = new URL(request.url).searchParams;
      estado.consultas.push(params);
      const bajo = params.get("bajo_minimo") === "true";
      return HttpResponse.json(paginated(bajo ? estado.items.filter((i) => i.bajo_minimo) : estado.items));
    }),
    http.get("/api/stock/alertas", () => {
      const bajos = estado.items.filter((i) => i.bajo_minimo);
      return HttpResponse.json({ total_bajo_minimo: bajos.length, items: bajos });
    }),
    http.post("/api/productos/:id/ajustar", async ({ params, request }) => {
      const body = (await request.json()) as { cantidad_delta: number; motivo: string };
      estado.ajustes.push(body);
      const actual = estado.items.find((i) => i.id === params.id);
      if (actual === undefined) return HttpResponse.json({ detail: "producto no encontrado" }, { status: 404 });
      const nuevo = actual.stock_actual + body.cantidad_delta;
      const idx = estado.items.indexOf(actual);
      estado.items[idx] = item({ ...actual, stock_actual: nuevo });
      return HttpResponse.json({
        producto: estado.items[idx],
        movimiento: {
          id: "m-1",
          producto_id: actual.id,
          tipo: "ajuste",
          cantidad: body.cantidad_delta,
          stock_previo: actual.stock_actual,
          stock_nuevo: nuevo,
          ref_id: null,
          motivo: body.motivo,
          usuario_id: "u-duena",
          created_at: "2026-10-07T12:00:00Z",
        },
      });
    }),
  );
  return estado;
}

const NORMAL = item({ id: "p-1", sku: "RC-1", nombre: "Royal Canin Mini", stock_actual: 10, stock_minimo: 3 });
const BAJO = item({ id: "p-2", sku: "WH-1", nombre: "Whiskas Adulto", stock_actual: 2, stock_minimo: 5 });
const SIN = item({ id: "p-3", sku: "SN-1", nombre: "Snack Dental", stock_actual: 0, stock_minimo: 4 });

describe("StockPage", () => {
  beforeEach(() => sesion(duena));

  it("resume las alertas y marca bajo mínimo y sin stock con badges", async () => {
    mockStock([NORMAL, BAJO, SIN]);
    renderWithProviders(<><Toaster /><StockPage /></>);

    expect(await screen.findByText("Royal Canin Mini")).toBeInTheDocument();
    expect(await screen.findByText("2 productos bajo el mínimo.")).toBeInTheDocument();
    expect(screen.getByText("Bajo mínimo")).toBeInTheDocument();
    expect(screen.getByText("Sin stock")).toBeInTheDocument();
  });

  it("el filtro 'Solo bajo mínimo' lista solo productos con stock <= mínimo", async () => {
    const estado = mockStock([NORMAL, BAJO, SIN]);
    const { user } = renderWithProviders(<><Toaster /><StockPage /></>);
    await screen.findByText("Royal Canin Mini");

    await user.click(screen.getByRole("button", { name: "Solo bajo mínimo" }));

    expect(await screen.findByText("Whiskas Adulto")).toBeInTheDocument();
    expect(screen.queryByText("Royal Canin Mini")).not.toBeInTheDocument();
    expect(estado.consultas.at(-1)?.get("bajo_minimo")).toBe("true");
    expect(estado.consultas.at(-1)?.get("orden")).toBe("rotacion");
  });

  it("la dueña ajusta -2 con motivo y ve 'Stock ajustado: 10 → 8' con la fila actualizada", async () => {
    const estado = mockStock([NORMAL]);
    const { user } = renderWithProviders(<><Toaster /><StockPage /></>);
    await screen.findByText("Royal Canin Mini");

    await user.click(screen.getByRole("button", { name: /ajustar stock de royal canin mini/i }));
    const dialogo = await screen.findByRole("dialog", { name: "Ajustar stock" });
    await user.type(within(dialogo).getByLabelText("Diferencia"), "-2");
    expect(within(dialogo).getByText("Quedará en 8")).toBeInTheDocument();
    await user.type(within(dialogo).getByLabelText("Motivo"), "rotura");
    await user.click(within(dialogo).getByRole("button", { name: "Confirmar ajuste" }));

    expect(await screen.findByText("Stock ajustado: 10 → 8")).toBeInTheDocument();
    expect(estado.ajustes).toEqual([{ cantidad_delta: -2, motivo: "rotura" }]);
    const fila = (await screen.findByText("Royal Canin Mini")).closest("tr");
    expect(fila).not.toBeNull();
    expect(await within(fila as HTMLElement).findByText("8")).toBeInTheDocument();
  });

  it("sin motivo no envía y muestra 'Indicá el motivo'", async () => {
    const estado = mockStock([NORMAL]);
    const { user } = renderWithProviders(<><Toaster /><StockPage /></>);
    await screen.findByText("Royal Canin Mini");

    await user.click(screen.getByRole("button", { name: /ajustar stock de/i }));
    const dialogo = await screen.findByRole("dialog", { name: "Ajustar stock" });
    await user.type(within(dialogo).getByLabelText("Diferencia"), "-2");
    await user.click(within(dialogo).getByRole("button", { name: "Confirmar ajuste" }));

    expect(await within(dialogo).findByText("Indicá el motivo")).toBeInTheDocument();
    expect(estado.ajustes).toHaveLength(0);
  });

  it("impide dejar el stock negativo", async () => {
    const estado = mockStock([NORMAL]);
    const { user } = renderWithProviders(<><Toaster /><StockPage /></>);
    await screen.findByText("Royal Canin Mini");

    await user.click(screen.getByRole("button", { name: /ajustar stock de/i }));
    const dialogo = await screen.findByRole("dialog", { name: "Ajustar stock" });
    await user.type(within(dialogo).getByLabelText("Diferencia"), "-11");
    await user.type(within(dialogo).getByLabelText("Motivo"), "x");
    await user.click(within(dialogo).getByRole("button", { name: "Confirmar ajuste" }));

    expect(await within(dialogo).findByText("El stock no puede quedar negativo")).toBeInTheDocument();
    expect(estado.ajustes).toHaveLength(0);
  });

  it("el mostrador consulta el stock pero no ve 'Ajustar stock'", async () => {
    sesion(mostrador);
    mockStock([NORMAL, BAJO]);
    renderWithProviders(<><Toaster /><StockPage /></>);

    expect(await screen.findByText("Royal Canin Mini")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ajustar stock/i })).not.toBeInTheDocument();
  });

  it("busca vía /productos/buscar y calcula bajo mínimo con la misma regla", async () => {
    mockStock([NORMAL, BAJO]);
    server.use(
      http.get("/api/productos/buscar", () =>
        HttpResponse.json(paginated([makeProducto({ id: "p-9", sku: "WH-9", nombre: "Whiskas Gatitos", stock_actual: 2, stock_minimo: 5 })])),
      ),
    );
    const { user } = renderWithProviders(<><Toaster /><StockPage /></>);
    await screen.findByText("Royal Canin Mini");
    await user.type(screen.getByRole("searchbox", { name: "Buscar en stock" }), "whiskas");

    expect(await screen.findByText("Whiskas Gatitos")).toBeInTheDocument();
    expect(screen.queryByText("Royal Canin Mini")).not.toBeInTheDocument();
    expect(screen.getByText("Bajo mínimo")).toBeInTheDocument();
  });
});
