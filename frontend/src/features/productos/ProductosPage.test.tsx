import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { ProductosPage } from "@/features/productos/ProductosPage";
import { useSession } from "@/features/auth/session";
import type { Me, Producto } from "@/shared/api/types";
import { duena, makeProducto, mostrador, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

function sesion(user: Me): void {
  useSession.setState({ status: "authenticated", accessToken: "tok", user, expired: false });
}

function mockCatalogo(inicial: Producto[]): { creados: unknown[] } {
  const lista = [...inicial];
  const creados: unknown[] = [];
  server.use(
    http.get("/api/productos", () => HttpResponse.json(paginated(lista))),
    http.get("/api/distribuidoras", () => HttpResponse.json(paginated([]))),
    http.post("/api/productos", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      creados.push(body);
      const nuevo = makeProducto({
        id: "p-nuevo",
        sku: String(body.sku),
        nombre: String(body.nombre),
        costo: String(body.costo),
        margen_pct: String(body.margen_pct),
        precio_venta: "24300.00",
        stock_actual: Number(body.stock_actual),
      });
      lista.push(nuevo);
      return HttpResponse.json(nuevo, { status: 201 });
    }),
  );
  return { creados };
}

describe("ProductosPage", () => {
  beforeEach(() => sesion(duena));

  it("la dueña ve costo y margen y crea un producto con vista previa de precio", async () => {
    const { creados } = mockCatalogo([makeProducto()]);
    const { user } = renderWithProviders(<ProductosPage />);

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
    mockCatalogo([makeProducto()]);
    server.use(
      http.post("/api/productos", () => HttpResponse.json({ detail: "sku ya registrado" }, { status: 409 })),
    );
    const { user } = renderWithProviders(<ProductosPage />);
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
    const { user } = renderWithProviders(<ProductosPage />);
    await user.click(await screen.findByRole("button", { name: /nuevo producto/i, hidden: false }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo producto" });
    await user.click(within(panel).getByRole("button", { name: "Crear producto" }));

    expect(await within(panel).findByText("Ingresá el SKU")).toBeInTheDocument();
    expect(within(panel).getByText("Ingresá el nombre")).toBeInTheDocument();
    expect(creados).toHaveLength(0);
  });

  it("el mostrador no ve costo, margen ni acciones", async () => {
    sesion(mostrador);
    mockCatalogo([makeProducto()]);
    renderWithProviders(<ProductosPage />);

    expect(await screen.findByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Precio" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Costo" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Margen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /nuevo producto/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /acciones de/i })).not.toBeInTheDocument();
  });

  it("busca con /productos/buscar al tipear", async () => {
    mockCatalogo([makeProducto()]);
    server.use(
      http.get("/api/productos/buscar", ({ request }) => {
        const q = new URL(request.url).searchParams.get("q");
        return HttpResponse.json(
          paginated(q === "whiskas" ? [makeProducto({ id: "p-2", sku: "WH-1", nombre: "Whiskas Adulto" })] : []),
        );
      }),
    );
    const { user } = renderWithProviders(<ProductosPage />);
    await screen.findByText("Royal Canin Mini Adult 3 kg");
    await user.type(screen.getByRole("searchbox", { name: "Buscar productos" }), "whiskas");

    expect(await screen.findByText("Whiskas Adulto")).toBeInTheDocument();
    expect(screen.queryByText("Royal Canin Mini Adult 3 kg")).not.toBeInTheDocument();
  });
});
