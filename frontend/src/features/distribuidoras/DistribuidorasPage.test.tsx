import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { useSession } from "@/features/auth/session";
import { Comparador } from "@/features/distribuidoras/Comparador";
import { DistribuidoraDetallePage } from "@/features/distribuidoras/DistribuidoraDetallePage";
import { DistribuidorasPage } from "@/features/distribuidoras/DistribuidorasPage";
import { makeCuenta, makeDistribuidora, makeListaPrecio } from "@/features/distribuidoras/testData";
import type { Me } from "@/shared/api/types";
import { duena, makeProducto, mostrador, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

function sesion(user: Me): void {
  useSession.setState({ status: "authenticated", accessToken: "tok", user, expired: false });
}

const rc = makeProducto({ id: "p-1", sku: "RC-MINI-3KG", nombre: "Royal Canin Mini Adult 3 kg" });
const pp = makeProducto({ id: "p-2", sku: "PP-ADULT-15", nombre: "Pro Plan Adult 15 kg" });

function mockCatalogo(): void {
  server.use(
    http.get("/api/productos", () => HttpResponse.json(paginated([rc, pp]))),
    http.get("/api/productos/buscar", () => HttpResponse.json(paginated([rc]))),
    http.get("/api/distribuidoras", () =>
      HttpResponse.json(
        paginated([makeDistribuidora(), makeDistribuidora({ id: "d-2", nombre: "Mayorista Sur", cuit: "30-1" })]),
      ),
    ),
  );
}

function renderDetalle() {
  return renderWithProviders(
    <>
      <Toaster />
      <Routes>
        <Route path="/distribuidoras/:id" element={<DistribuidoraDetallePage />} />
      </Routes>
    </>,
    { route: "/distribuidoras/d-1" },
  );
}

describe("DistribuidorasPage", () => {
  beforeEach(() => {
    mockCatalogo();
  });

  it("la dueña ve el alta y las acciones", async () => {
    sesion(duena);
    renderWithProviders(<DistribuidorasPage />);
    expect(await screen.findByText("Distribuidora Norte")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /nueva distribuidora/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /acciones de distribuidora norte/i })).toBeInTheDocument();
  });

  it("el mostrador solo consulta: sin alta ni acciones", async () => {
    sesion(mostrador);
    renderWithProviders(<DistribuidorasPage />);
    expect(await screen.findByText("Distribuidora Norte")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /nueva distribuidora/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /acciones de/i })).not.toBeInTheDocument();
  });

  it("la dueña crea una distribuidora con el panel lateral (valida el nombre antes de enviar)", async () => {
    sesion(duena);
    let enviado: unknown = null;
    server.use(
      http.post("/api/distribuidoras", async ({ request }) => {
        enviado = await request.json();
        return HttpResponse.json(makeDistribuidora({ id: "d-9", nombre: "Pet Mayorista" }), { status: 201 });
      }),
    );
    const { user } = renderWithProviders(
      <>
        <Toaster />
        <DistribuidorasPage />
      </>,
    );
    await user.click(await screen.findByRole("button", { name: /nueva distribuidora/i }));
    const panel = await screen.findByRole("dialog", { name: /nueva distribuidora/i });
    await user.click(within(panel).getByRole("button", { name: /crear distribuidora/i }));
    expect(await within(panel).findByText("Ingresá el nombre")).toBeInTheDocument();
    expect(enviado).toBeNull();
    await user.type(within(panel).getByLabelText("Nombre"), "Pet Mayorista");
    await user.click(within(panel).getByRole("button", { name: /crear distribuidora/i }));
    expect(await screen.findByText("Distribuidora creada")).toBeInTheDocument();
    expect(enviado).toEqual({ nombre: "Pet Mayorista", contacto: null, cuit: null, condiciones: null });
  });
});

describe("DistribuidoraDetallePage", () => {
  beforeEach(() => {
    mockCatalogo();
    server.use(
      http.get("/api/distribuidoras/d-1", () => HttpResponse.json(makeDistribuidora())),
      http.get("/api/distribuidoras/d-1/listas", () => HttpResponse.json([makeListaPrecio()])),
      http.get("/api/compras/distribuidoras/d-1/cuenta", () => HttpResponse.json(makeCuenta())),
    );
  });

  it("muestra la lista con nombres desde el índice de productos y los costos", async () => {
    sesion(duena);
    renderDetalle();
    expect(await screen.findByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(screen.getByText(/18\.000,00/)).toBeInTheDocument();
  });

  it("agregar un producto repetido informa el duplicado y la lista no cambia", async () => {
    sesion(duena);
    let posts = 0;
    server.use(
      http.get("/api/distribuidoras/d-1/listas", () => HttpResponse.json([])),
      http.post("/api/distribuidoras/d-1/listas", () => {
        posts += 1;
        return HttpResponse.json({ detail: "producto ya cargado en esta lista" }, { status: 409 });
      }),
    );
    const { user } = renderDetalle();
    await user.click(await screen.findByRole("button", { name: /^agregar producto$/i }));
    const panel = await screen.findByRole("dialog", { name: /agregar producto a la lista/i });
    await user.click(within(panel).getByRole("button", { name: /buscar producto/i }));
    await user.type(await screen.findByPlaceholderText(/sku o nombre/i), "royal");
    await user.click(await screen.findByRole("option", { name: /royal canin mini/i }));
    await user.type(within(panel).getByLabelText("Costo"), "17500");
    await user.click(within(panel).getByRole("button", { name: /agregar a la lista/i }));
    expect(await within(panel).findByText("Ese producto ya está en la lista de esta distribuidora")).toBeInTheDocument();
    expect(posts).toBe(1);
    expect(screen.getByRole("dialog", { name: /agregar producto a la lista/i })).toBeInTheDocument();
  });

  it("el mostrador no ve acciones de edición ni la cuenta, pero sí puede hacer un pedido", async () => {
    sesion(mostrador);
    renderDetalle();
    expect(await screen.findByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /agregar producto/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^editar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Cuenta" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /hacer un pedido/i })).toBeInTheDocument();
  });
});

describe("Comparador", () => {
  it("lista los costos del más barato al más caro y destaca el de 17500", async () => {
    sesion(mostrador);
    mockCatalogo();
    server.use(
      http.get("/api/distribuidoras/comparar", ({ request }) => {
        expect(new URL(request.url).searchParams.get("producto_id")).toBe("p-1");
        return HttpResponse.json({
          producto_id: "p-1",
          filas: [
            { distribuidora_id: "d-1", distribuidora_nombre: "Distribuidora Norte", costo: 18000, precio_sugerido: 24300 },
            { distribuidora_id: "d-2", distribuidora_nombre: "Mayorista Sur", costo: 17500, precio_sugerido: 23625 },
          ],
        });
      }),
    );
    const { user } = renderWithProviders(<Comparador />);
    await user.click(screen.getByRole("button", { name: /elegir un producto para comparar/i }));
    await user.type(await screen.findByPlaceholderText(/sku o nombre/i), "royal");
    await user.click(await screen.findByRole("option", { name: /royal canin mini/i }));

    const tabla = await screen.findByRole("table", { name: /costos de royal canin/i });
    const filas = within(tabla).getAllByRole("row").slice(1);
    expect(filas).toHaveLength(2);
    const primera = filas[0] as HTMLElement;
    const segunda = filas[1] as HTMLElement;
    expect(within(primera).getByText("Mayorista Sur")).toBeInTheDocument();
    expect(within(primera).getByText("Más barato")).toBeInTheDocument();
    expect(within(primera).getByText(/17\.500,00/)).toBeInTheDocument();
    expect(within(primera).getByText(/23\.625,00/)).toBeInTheDocument();
    expect(within(segunda).queryByText("Más barato")).not.toBeInTheDocument();
  });
});
