import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { ProductosPage } from "@/features/productos/ProductosPage";
import { useSession } from "@/features/auth/session";
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
  creados: unknown[];
  ajustes: unknown[];
  consultas: URLSearchParams[];
}

/** Mock del backend de la pantalla unificada: `/stock` (tabla), alertas, alta y ajuste. */
function mockCatalogo(inicial: StockItem[]): Estado {
  const estado: Estado = { items: [...inicial], creados: [], ajustes: [], consultas: [] };
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
    http.get("/api/distribuidoras", () => HttpResponse.json(paginated([]))),
    http.post("/api/productos", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      estado.creados.push(body);
      const nuevo = item({
        id: "p-nuevo",
        sku: String(body.sku),
        nombre: String(body.nombre),
        costo: String(body.costo),
        margen_pct: String(body.margen_pct),
        precio_venta: "24300.00",
        stock_actual: Number(body.stock_actual),
      });
      estado.items.push(nuevo);
      return HttpResponse.json(nuevo, { status: 201 });
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

function renderPagina() {
  return renderWithProviders(
    <>
      <Toaster />
      <ProductosPage />
    </>,
  );
}

describe("ProductosPage", () => {
  beforeEach(() => sesion(duena));

  it("la dueña ve costo y margen y crea un producto con vista previa de precio", async () => {
    const { creados } = mockCatalogo([item()]);
    const { user } = renderPagina();

    expect(await screen.findByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Costo" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Margen" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /nuevo producto/i }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo producto" });
    await user.type(within(panel).getByLabelText("SKU"), "PP-ADULT-15");
    await user.type(within(panel).getByLabelText("Nombre"), "Pro Plan Adulto 15 kg");
    await user.type(within(panel).getByLabelText("Costo ($)"), "18000");
    await user.type(within(panel).getByLabelText("Margen (%)"), "35");

    expect(within(panel).getByTestId("precio-preview").textContent?.replace(/\s/g, " ")).toBe("$ 24.300,00");

    await user.click(within(panel).getByRole("button", { name: "Crear producto" }));

    expect(await screen.findByText("Pro Plan Adulto 15 kg")).toBeInTheDocument();
    expect(creados).toHaveLength(1);
    expect(creados[0]).toMatchObject({ sku: "PP-ADULT-15", costo: "18000.00", margen_pct: "0.35", stock_actual: 0 });
  });

  it("un SKU repetido (409) se marca en el campo SKU", async () => {
    mockCatalogo([item()]);
    server.use(
      http.post("/api/productos", () => HttpResponse.json({ detail: "sku ya registrado" }, { status: 409 })),
    );
    const { user } = renderPagina();
    await screen.findByText("Royal Canin Mini Adult 3 kg");
    await user.click(screen.getByRole("button", { name: /nuevo producto/i }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo producto" });
    await user.type(within(panel).getByLabelText("SKU"), "RC-MINI-3KG");
    await user.type(within(panel).getByLabelText("Nombre"), "Duplicado");
    await user.type(within(panel).getByLabelText("Costo ($)"), "100");
    await user.type(within(panel).getByLabelText("Margen (%)"), "10");
    await user.click(within(panel).getByRole("button", { name: "Crear producto" }));

    expect(await within(panel).findByText("Ya existe un producto con ese SKU")).toBeInTheDocument();
  });

  it("valida en linea antes de enviar", async () => {
    const { creados } = mockCatalogo([]);
    const { user } = renderPagina();
    await user.click(await screen.findByRole("button", { name: /nuevo producto/i, hidden: false }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo producto" });
    await user.click(within(panel).getByRole("button", { name: "Crear producto" }));

    expect(await within(panel).findByText("Ingresá el SKU")).toBeInTheDocument();
    expect(within(panel).getByText("Ingresá el nombre")).toBeInTheDocument();
    expect(creados).toHaveLength(0);
  });

  it("el mostrador no ve costo, margen ni acciones", async () => {
    sesion(mostrador);
    mockCatalogo([item()]);
    renderPagina();

    expect(await screen.findByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Precio" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Costo" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Margen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /nuevo producto/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /acciones de/i })).not.toBeInTheDocument();
  });

  it("busca con /productos/buscar al tipear", async () => {
    mockCatalogo([item()]);
    server.use(
      http.get("/api/productos/buscar", ({ request }) => {
        const q = new URL(request.url).searchParams.get("q");
        return HttpResponse.json(
          paginated(q === "whiskas" ? [makeProducto({ id: "p-2", sku: "WH-1", nombre: "Whiskas Adulto" })] : []),
        );
      }),
    );
    const { user } = renderPagina();
    await screen.findByText("Royal Canin Mini Adult 3 kg");
    await user.type(screen.getByRole("searchbox", { name: "Buscar productos" }), "whiskas");

    expect(await screen.findByText("Whiskas Adulto")).toBeInTheDocument();
    expect(screen.queryByText("Royal Canin Mini Adult 3 kg")).not.toBeInTheDocument();
  });

  it("la dueña ve costo, margen, precio, stock, mínimo y estado con todas las acciones en la misma fila", async () => {
    mockCatalogo([NORMAL, BAJO]);
    const { user } = renderPagina();
    await screen.findByText("Whiskas Adulto");

    for (const col of ["SKU", "Producto", "Costo", "Margen", "Precio", "Stock", "Mínimo", "Estado"]) {
      expect(screen.getByRole("columnheader", { name: col })).toBeInTheDocument();
    }
    const fila = screen.getByText("Whiskas Adulto").closest("tr") as HTMLElement;
    expect(within(fila).getByText("Bajo mínimo")).toBeInTheDocument();

    await user.click(within(fila).getByRole("button", { name: "Acciones de Whiskas Adulto" }));
    for (const accion of ["Editar", "Margen y mínimo", "Ajustar stock", "Dar de baja"]) {
      expect(await screen.findByRole("menuitem", { name: accion })).toBeInTheDocument();
    }
  });

  it("el mostrador ve precio, stock, mínimo y estado, sin costo, margen ni acciones", async () => {
    sesion(mostrador);
    mockCatalogo([BAJO]);
    renderPagina();
    await screen.findByText("Whiskas Adulto");

    for (const col of ["Precio", "Stock", "Mínimo", "Estado"]) {
      expect(screen.getByRole("columnheader", { name: col })).toBeInTheDocument();
    }
    expect(screen.getByText("Bajo mínimo")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Costo" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Margen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /acciones de|ajustar stock/i })).not.toBeInTheDocument();
  });

  it("resume las alertas y marca bajo mínimo y sin stock con badges", async () => {
    mockCatalogo([NORMAL, BAJO, SIN]);
    renderPagina();

    expect(await screen.findByText("Royal Canin Mini")).toBeInTheDocument();
    expect(await screen.findByText("2 productos bajo el mínimo.")).toBeInTheDocument();
    expect(screen.getByText("Bajo mínimo")).toBeInTheDocument();
    expect(screen.getByText("Sin stock")).toBeInTheDocument();
  });

  it("el filtro 'Solo bajo mínimo' pide bajo_minimo=true y lista solo esos productos", async () => {
    const estado = mockCatalogo([NORMAL, BAJO, SIN]);
    const { user } = renderPagina();
    await screen.findByText("Royal Canin Mini");

    await user.click(screen.getByRole("button", { name: "Solo bajo mínimo" }));

    expect(await screen.findByText("Whiskas Adulto")).toBeInTheDocument();
    expect(screen.queryByText("Royal Canin Mini")).not.toBeInTheDocument();
    expect(estado.consultas.at(-1)?.get("bajo_minimo")).toBe("true");
    expect(estado.consultas.at(-1)?.get("orden")).toBe("rotacion");
  });

  it("la dueña ajusta -2 con motivo y ve 'Stock ajustado: 10 → 8' con la fila actualizada", async () => {
    const estado = mockCatalogo([NORMAL]);
    const { user } = renderPagina();
    await screen.findByText("Royal Canin Mini");

    await user.click(screen.getByRole("button", { name: "Acciones de Royal Canin Mini" }));
    await user.click(await screen.findByRole("menuitem", { name: "Ajustar stock" }));
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

  it("sin motivo no envía el ajuste y muestra 'Indicá el motivo'", async () => {
    const estado = mockCatalogo([NORMAL]);
    const { user } = renderPagina();
    await screen.findByText("Royal Canin Mini");

    await user.click(screen.getByRole("button", { name: /acciones de/i }));
    await user.click(await screen.findByRole("menuitem", { name: "Ajustar stock" }));
    const dialogo = await screen.findByRole("dialog", { name: "Ajustar stock" });
    await user.type(within(dialogo).getByLabelText("Diferencia"), "-2");
    await user.click(within(dialogo).getByRole("button", { name: "Confirmar ajuste" }));

    expect(await within(dialogo).findByText("Indicá el motivo")).toBeInTheDocument();
    expect(estado.ajustes).toHaveLength(0);
  });

  it("impide dejar el stock negativo", async () => {
    const estado = mockCatalogo([NORMAL]);
    const { user } = renderPagina();
    await screen.findByText("Royal Canin Mini");

    await user.click(screen.getByRole("button", { name: /acciones de/i }));
    await user.click(await screen.findByRole("menuitem", { name: "Ajustar stock" }));
    const dialogo = await screen.findByRole("dialog", { name: "Ajustar stock" });
    await user.type(within(dialogo).getByLabelText("Diferencia"), "-11");
    await user.type(within(dialogo).getByLabelText("Motivo"), "x");
    await user.click(within(dialogo).getByRole("button", { name: "Confirmar ajuste" }));

    expect(await within(dialogo).findByText("El stock no puede quedar negativo")).toBeInTheDocument();
    expect(estado.ajustes).toHaveLength(0);
  });

  it("la búsqueda calcula bajo mínimo con la misma regla que la tabla", async () => {
    mockCatalogo([NORMAL, BAJO]);
    server.use(
      http.get("/api/productos/buscar", () =>
        HttpResponse.json(
          paginated([makeProducto({ id: "p-9", sku: "WH-9", nombre: "Whiskas Gatitos", stock_actual: 2, stock_minimo: 5 })]),
        ),
      ),
    );
    const { user } = renderPagina();
    await screen.findByText("Royal Canin Mini");
    await user.type(screen.getByRole("searchbox", { name: "Buscar productos" }), "whiskas");

    expect(await screen.findByText("Whiskas Gatitos")).toBeInTheDocument();
    expect(screen.queryByText("Royal Canin Mini")).not.toBeInTheDocument();
    expect(screen.getByText("Bajo mínimo")).toBeInTheDocument();
  });
});
