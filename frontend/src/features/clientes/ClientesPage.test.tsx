import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { useSession } from "@/features/auth/session";
import { ClienteDetallePage } from "@/features/clientes/ClienteDetallePage";
import { ClientesPage } from "@/features/clientes/ClientesPage";
import type { Cliente, Me, VentaResumen } from "@/shared/api/types";
import { duena, makeCliente, mostrador, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

function sesion(user: Me): void {
  useSession.setState({ status: "authenticated", accessToken: "tok", user, expired: false });
}

function mockClientes(inicial: Cliente[]): { creados: unknown[] } {
  const lista = [...inicial];
  const creados: unknown[] = [];
  server.use(
    http.get("/api/clientes", () => HttpResponse.json(paginated(lista))),
    http.post("/api/clientes", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      creados.push(body);
      const nuevo = makeCliente({
        id: "c-nuevo",
        nombre: String(body.nombre),
        telefono: (body.telefono as string | null) ?? null,
      });
      lista.push(nuevo);
      return HttpResponse.json(nuevo, { status: 201 });
    }),
  );
  return { creados };
}

function renderLista() {
  return renderWithProviders(
    <>
      <Toaster />
      <ClientesPage />
    </>,
  );
}

describe("ClientesPage", () => {
  beforeEach(() => sesion(mostrador));

  it("el mostrador da de alta un cliente y ve 'Cliente creado'", async () => {
    const { creados } = mockClientes([makeCliente()]);
    const { user } = renderLista();
    expect(await screen.findByText("Ana Perez")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /nuevo cliente/i }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo cliente" });
    await user.type(within(panel).getByLabelText("Nombre"), "Lucía Herrera");
    await user.type(within(panel).getByLabelText(/Teléfono/), "351-8901234");
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await screen.findByText("Cliente creado")).toBeInTheDocument();
    expect(await screen.findByText("Lucía Herrera")).toBeInTheDocument();
    expect(creados).toEqual([{ nombre: "Lucía Herrera", telefono: "351-8901234", email: null, direccion: null }]);
  });

  it("el mostrador no ve acciones de edición ni baja", async () => {
    mockClientes([makeCliente()]);
    renderLista();
    expect(await screen.findByText("Ana Perez")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /acciones de/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /nuevo cliente/i })).toBeInTheDocument();
  });

  it("la dueña ve el menú de acciones", async () => {
    sesion(duena);
    mockClientes([makeCliente()]);
    const { user } = renderLista();
    await user.click(await screen.findByRole("button", { name: "Acciones de Ana Perez" }));
    expect(await screen.findByRole("menuitem", { name: /editar/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /dar de baja/i })).toBeInTheDocument();
  });

  it("un email repetido (409) se marca en el campo email", async () => {
    mockClientes([]);
    server.use(http.post("/api/clientes", () => HttpResponse.json({ detail: "email ya registrado" }, { status: 409 })));
    const { user } = renderLista();
    await user.click(await screen.findByRole("button", { name: /nuevo cliente/i }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo cliente" });
    await user.type(within(panel).getByLabelText("Nombre"), "Otra Persona");
    await user.type(within(panel).getByLabelText(/Email/), "ana@mail.com");
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await within(panel).findByText("Ya existe un cliente con ese email")).toBeInTheDocument();
  });

  it("un 422 del servidor se marca en su campo", async () => {
    mockClientes([]);
    server.use(
      http.post("/api/clientes", () =>
        HttpResponse.json(
          { detail: [{ loc: ["body", "telefono"], msg: "teléfono inválido", type: "value_error" }] },
          { status: 422 },
        ),
      ),
    );
    const { user } = renderLista();
    await user.click(await screen.findByRole("button", { name: /nuevo cliente/i }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo cliente" });
    await user.type(within(panel).getByLabelText("Nombre"), "Alguien");
    await user.type(within(panel).getByLabelText(/Teléfono/), "abc");
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await within(panel).findByText("teléfono inválido")).toBeInTheDocument();
  });

  it("busca con /clientes/buscar", async () => {
    mockClientes([makeCliente()]);
    server.use(
      http.get("/api/clientes/buscar", ({ request }) =>
        HttpResponse.json(
          paginated(
            new URL(request.url).searchParams.get("q") === "lucia" ? [makeCliente({ id: "c-9", nombre: "Lucía Herrera" })] : [],
          ),
        ),
      ),
    );
    const { user } = renderLista();
    await screen.findByText("Ana Perez");
    await user.type(screen.getByRole("searchbox", { name: "Buscar clientes" }), "lucia");

    expect(await screen.findByText("Lucía Herrera")).toBeInTheDocument();
    expect(screen.queryByText("Ana Perez")).not.toBeInTheDocument();
  });
});

describe("ClienteDetallePage", () => {
  const ventas: VentaResumen[] = [
    {
      id: "v-nueva",
      estado: "confirmada",
      cliente_id: "c-1",
      usuario_id: "u-duena",
      total: "5300.00",
      created_at: "2026-10-06T15:00:00Z",
      confirmada_at: "2026-10-06T15:01:00Z",
      anulada_at: null,
    },
    {
      id: "v-vieja",
      estado: "anulada",
      cliente_id: "c-1",
      usuario_id: "u-duena",
      total: "2650.00",
      created_at: "2026-10-01T15:00:00Z",
      confirmada_at: "2026-10-01T15:01:00Z",
      anulada_at: "2026-10-02T10:00:00Z",
    },
  ];

  function renderDetalle() {
    return renderWithProviders(
      <Routes>
        <Route path="/clientes/:id" element={<ClienteDetallePage />} />
      </Routes>,
      { route: "/clientes/c-1" },
    );
  }

  it("muestra los datos y el historial con la venta más reciente primero y enlaces al detalle", async () => {
    sesion(duena);
    server.use(
      http.get("/api/clientes/c-1", () => HttpResponse.json(makeCliente({ telefono: "351-1112233", email: "ana@mail.com" }))),
      http.get("/api/clientes/c-1/ventas", () => HttpResponse.json(paginated(ventas))),
    );
    renderDetalle();

    expect(await screen.findByRole("heading", { level: 1, name: "Ana Perez" })).toBeInTheDocument();
    expect(screen.getByText("351-1112233")).toBeInTheDocument();
    const filas = await screen.findAllByRole("row");
    // filas[0] = encabezado; luego mas reciente primero (orden del servidor).
    expect(within(filas[1]).getByText(/5\.300,00/)).toBeInTheDocument();
    expect(within(filas[1]).getByText("Confirmada")).toBeInTheDocument();
    expect(within(filas[2]).getByText(/2\.650,00/)).toBeInTheDocument();
    expect(within(filas[2]).getByText("Anulada")).toBeInTheDocument();
    expect(within(filas[1]).getByRole("link")).toHaveAttribute("href", "/ventas/v-nueva");
    expect(screen.getByRole("button", { name: /editar/i })).toBeInTheDocument();
  });

  it("el mostrador no ve 'Editar' y el historial vacío explica el estado", async () => {
    sesion(mostrador);
    server.use(
      http.get("/api/clientes/c-1", () => HttpResponse.json(makeCliente())),
      http.get("/api/clientes/c-1/ventas", () => HttpResponse.json(paginated([]))),
    );
    renderDetalle();

    expect(await screen.findByText("Todavía no compró")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
  });

  it("un cliente inexistente muestra un estado claro", async () => {
    sesion(duena);
    server.use(http.get("/api/clientes/c-1", () => HttpResponse.json({ detail: "cliente no encontrado" }, { status: 404 })));
    renderDetalle();
    expect(await screen.findByText("No encontramos al cliente")).toBeInTheDocument();
  });
});
