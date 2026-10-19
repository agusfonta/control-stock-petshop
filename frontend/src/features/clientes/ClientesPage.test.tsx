import { act, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { Route, Routes } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { useSession } from "@/features/auth/session";
import { ClienteDetallePage } from "@/features/clientes/ClienteDetallePage";
import { ClientesPage } from "@/features/clientes/ClientesPage";
import type { Cliente, Mascota, Me, VentaResumen } from "@/shared/api/types";
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
    await user.type(within(panel).getByLabelText(/Teléfono/), "351-1112233");
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await within(panel).findByText("teléfono inválido")).toBeInTheDocument();
    expect(within(panel).getByLabelText(/Teléfono/)).toHaveFocus();
  });

  it("un teléfono inválido se marca en español sin enviar la solicitud", async () => {
    const { creados } = mockClientes([]);
    const { user } = renderLista();
    await user.click(await screen.findByRole("button", { name: /nuevo cliente/i }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo cliente" });
    await user.type(within(panel).getByLabelText("Nombre"), "Alguien");
    await user.type(within(panel).getByLabelText(/Teléfono/), "abc");
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await within(panel).findByText("Ingresá un teléfono válido (6 a 20 dígitos)")).toBeInTheDocument();
    expect(creados).toEqual([]);
  });

  it("un 422 con prefijo técnico lo muestra limpio", async () => {
    mockClientes([]);
    server.use(
      http.post("/api/clientes", () =>
        HttpResponse.json(
          { detail: [{ loc: ["body", "direccion"], msg: "Value error, dirección inválida", type: "value_error" }] },
          { status: 422 },
        ),
      ),
    );
    const { user } = renderLista();
    await user.click(await screen.findByRole("button", { name: /nuevo cliente/i }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo cliente" });
    await user.type(within(panel).getByLabelText("Nombre"), "Alguien");
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await within(panel).findByText("dirección inválida")).toBeInTheDocument();
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

describe("ClientesPage - alta con mascota", () => {
  beforeEach(() => sesion(mostrador));

  async function abrirAlta(user: ReturnType<typeof renderLista>["user"]): Promise<HTMLElement> {
    await user.click(await screen.findByRole("button", { name: /nuevo cliente/i }));
    return screen.findByRole("dialog", { name: "Nuevo cliente" });
  }

  it("el alta con mascota envía mascota y la ficha la muestra", async () => {
    const { creados } = mockClientes([]);
    server.use(
      http.get("/api/clientes/c-nuevo", () => HttpResponse.json(makeCliente({ id: "c-nuevo", nombre: "Ana" }))),
      http.get("/api/clientes/c-nuevo/ventas", () => HttpResponse.json(paginated([]))),
      http.get("/api/clientes/c-nuevo/mascotas", () =>
        HttpResponse.json([{ id: "m-1", nombre: "Firulais", tipo: "perro", activo: true }]),
      ),
    );
    const { user } = renderWithProviders(
      <>
        <Toaster />
        <Routes>
          <Route path="/clientes" element={<ClientesPage />} />
          <Route path="/clientes/:id" element={<ClienteDetallePage />} />
        </Routes>
      </>,
      { route: "/clientes" },
    );
    const panel = await abrirAlta(user);
    expect(within(panel).getByText("Mascota (opcional)")).toBeInTheDocument();
    await user.type(within(panel).getByLabelText("Nombre"), "Ana");
    await user.type(within(panel).getByLabelText("Nombre de la mascota"), "Firulais");
    await user.click(within(panel).getByRole("combobox", { name: "Tipo de mascota" }));
    await user.click(await screen.findByRole("option", { name: "Perro" }));
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect((await screen.findAllByText("Cliente creado")).length).toBeGreaterThan(0);
    expect(creados).toEqual([
      { nombre: "Ana", telefono: null, email: null, direccion: null, mascota: { nombre: "Firulais", tipo: "perro" } },
    ]);
    await user.click(await screen.findByRole("link", { name: "Ana" }));
    expect(await screen.findByText("Firulais · Perro")).toBeInTheDocument();
  });

  it("el alta sin mascota no envía la clave mascota", async () => {
    const { creados } = mockClientes([]);
    const { user } = renderLista();
    const panel = await abrirAlta(user);
    await user.type(within(panel).getByLabelText("Nombre"), "Ana");
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect((await screen.findAllByText("Cliente creado")).length).toBeGreaterThan(0);
    expect(creados).toHaveLength(1);
    expect(creados[0]).not.toHaveProperty("mascota");
  });

  it("nombre de mascota sin tipo marca el tipo y no envía", async () => {
    const { creados } = mockClientes([]);
    const { user } = renderLista();
    const panel = await abrirAlta(user);
    await user.type(within(panel).getByLabelText("Nombre"), "Ana");
    await user.type(within(panel).getByLabelText("Nombre de la mascota"), "Firulais");
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await within(panel).findByText("Elegí el tipo")).toBeInTheDocument();
    expect(creados).toEqual([]);
  });

  it("tipo de mascota sin nombre marca el nombre y no envía", async () => {
    const { creados } = mockClientes([]);
    const { user } = renderLista();
    const panel = await abrirAlta(user);
    await user.type(within(panel).getByLabelText("Nombre"), "Ana");
    await user.click(within(panel).getByRole("combobox", { name: "Tipo de mascota" }));
    await user.click(await screen.findByRole("option", { name: "Gato" }));
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await within(panel).findByText("Ingresá el nombre")).toBeInTheDocument();
    expect(creados).toEqual([]);
  });

  it("un 422 de mascota.nombre se marca en el campo de la mascota", async () => {
    mockClientes([]);
    server.use(
      http.post("/api/clientes", () =>
        HttpResponse.json(
          { detail: [{ loc: ["body", "mascota", "nombre"], msg: "Value error, nombre inválido", type: "value_error" }] },
          { status: 422 },
        ),
      ),
    );
    const { user } = renderLista();
    const panel = await abrirAlta(user);
    await user.type(within(panel).getByLabelText("Nombre"), "Ana");
    await user.type(within(panel).getByLabelText("Nombre de la mascota"), "Firulais");
    await user.click(within(panel).getByRole("combobox", { name: "Tipo de mascota" }));
    await user.click(await screen.findByRole("option", { name: "Otro" }));
    await user.click(within(panel).getByRole("button", { name: "Crear cliente" }));

    expect(await within(panel).findByText("nombre inválido")).toBeInTheDocument();
    expect(within(panel).getByLabelText("Nombre de la mascota")).toHaveFocus();
  });

  it("la edición de un cliente no muestra el bloque de mascota", async () => {
    sesion(duena);
    mockClientes([makeCliente()]);
    const { user } = renderLista();
    await user.click(await screen.findByRole("button", { name: "Acciones de Ana Perez" }));
    await user.click(await screen.findByRole("menuitem", { name: /editar/i }));
    const panel = await screen.findByRole("dialog", { name: "Editar cliente" });

    expect(within(panel).queryByText("Mascota (opcional)")).not.toBeInTheDocument();
    expect(within(panel).queryByLabelText("Nombre de la mascota")).not.toBeInTheDocument();
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

describe("ClienteDetallePage - mascotas", () => {
  const firulais: Mascota = { id: "m-1", nombre: "Firulais", tipo: "perro", activo: true };
  const mishi: Mascota = { id: "m-2", nombre: "Mishi", tipo: "gato", activo: true };

  function mockDetalle(inicial: Mascota[]): { creadas: unknown[]; editadas: unknown[]; bajas: string[] } {
    const lista = [...inicial];
    const creadas: unknown[] = [];
    const editadas: unknown[] = [];
    const bajas: string[] = [];
    server.use(
      http.get("/api/clientes/c-1", () => HttpResponse.json(makeCliente())),
      http.get("/api/clientes/c-1/ventas", () => HttpResponse.json(paginated([]))),
      http.get("/api/clientes/c-1/mascotas", () => HttpResponse.json(lista)),
      http.post("/api/clientes/c-1/mascotas", async ({ request }) => {
        const body = (await request.json()) as { nombre: string; tipo: Mascota["tipo"] };
        creadas.push(body);
        const nueva: Mascota = { id: "m-nueva", nombre: body.nombre, tipo: body.tipo, activo: true };
        lista.push(nueva);
        return HttpResponse.json(nueva, { status: 201 });
      }),
      http.put("/api/clientes/c-1/mascotas/:mid", async ({ request, params }) => {
        const body = (await request.json()) as Partial<Mascota>;
        editadas.push(body);
        const i = lista.findIndex((m) => m.id === params.mid);
        lista[i] = { ...lista[i], ...body };
        return HttpResponse.json(lista[i]);
      }),
      http.delete("/api/clientes/c-1/mascotas/:mid", ({ params }) => {
        bajas.push(String(params.mid));
        lista.splice(
          lista.findIndex((m) => m.id === params.mid),
          1,
        );
        return new HttpResponse(null, { status: 204 });
      }),
    );
    return { creadas, editadas, bajas };
  }

  function renderDetalle() {
    return renderWithProviders(
      <>
        <Toaster />
        <Routes>
          <Route path="/clientes/:id" element={<ClienteDetallePage />} />
        </Routes>
      </>,
      { route: "/clientes/c-1" },
    );
  }

  async function abrirAlta(user: ReturnType<typeof renderDetalle>["user"]) {
    await user.click(screen.getAllByRole("button", { name: "Agregar mascota" })[0]);
    return screen.findByRole("dialog", { name: "Agregar mascota" });
  }

  it("lista las mascotas con su tipo", async () => {
    sesion(mostrador);
    mockDetalle([firulais, mishi]);
    renderDetalle();
    expect(await screen.findByText("Firulais · Perro")).toBeInTheDocument();
    expect(screen.getByText("Mishi · Gato")).toBeInTheDocument();
  });

  it("sin mascotas muestra el estado vacío con la acción de agregar", async () => {
    sesion(mostrador);
    mockDetalle([]);
    renderDetalle();
    expect(await screen.findByText("Sin mascotas registradas")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Agregar mascota" }).length).toBeGreaterThan(0);
  });

  it("el mostrador agrega una mascota y ve 'Mascota agregada'", async () => {
    sesion(mostrador);
    const { creadas } = mockDetalle([]);
    const { user } = renderDetalle();
    await screen.findByText("Sin mascotas registradas");

    const panel = await abrirAlta(user);
    await user.type(within(panel).getByLabelText("Nombre"), "Firulais");
    await user.click(within(panel).getByRole("button", { name: "Guardar mascota" }));

    expect(await screen.findByText("Mascota agregada")).toBeInTheDocument();
    expect(await screen.findByText("Firulais · Perro")).toBeInTheDocument();
    expect(creadas).toEqual([{ nombre: "Firulais", tipo: "perro" }]);
  });

  it("permite elegir el tipo gato con el Select", async () => {
    sesion(mostrador);
    const { creadas } = mockDetalle([]);
    const { user } = renderDetalle();
    await screen.findByText("Sin mascotas registradas");

    const panel = await abrirAlta(user);
    await user.type(within(panel).getByLabelText("Nombre"), "Mishi");
    await user.click(within(panel).getByRole("combobox", { name: "Tipo" }));
    await user.click(await screen.findByRole("option", { name: "Gato" }));
    await user.click(within(panel).getByRole("button", { name: "Guardar mascota" }));

    expect(await screen.findByText("Mishi · Gato")).toBeInTheDocument();
    expect(creadas).toEqual([{ nombre: "Mishi", tipo: "gato" }]);
  });

  it("nombre vacío muestra el error y no envía la solicitud", async () => {
    sesion(mostrador);
    const { creadas } = mockDetalle([]);
    const { user } = renderDetalle();
    await screen.findByText("Sin mascotas registradas");

    const panel = await abrirAlta(user);
    await user.click(within(panel).getByRole("button", { name: "Guardar mascota" }));

    expect(await within(panel).findByText("Ingresá el nombre")).toBeInTheDocument();
    expect(creadas).toEqual([]);
  });

  it("un 422 del servidor se marca en el campo nombre", async () => {
    sesion(mostrador);
    mockDetalle([]);
    server.use(
      http.post("/api/clientes/c-1/mascotas", () =>
        HttpResponse.json(
          { detail: [{ loc: ["body", "nombre"], msg: "nombre inválido", type: "value_error" }] },
          { status: 422 },
        ),
      ),
    );
    const { user } = renderDetalle();
    await screen.findByText("Sin mascotas registradas");

    const panel = await abrirAlta(user);
    await user.type(within(panel).getByLabelText("Nombre"), "X");
    await user.click(within(panel).getByRole("button", { name: "Guardar mascota" }));

    expect(await within(panel).findByText("nombre inválido")).toBeInTheDocument();
  });

  it("el mostrador no ve editar ni dar de baja mascotas", async () => {
    sesion(mostrador);
    mockDetalle([firulais]);
    renderDetalle();
    await screen.findByText("Firulais · Perro");
    expect(screen.queryByRole("button", { name: /editar a firulais/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /dar de baja a firulais/i })).not.toBeInTheDocument();
  });

  it("la dueña edita una mascota", async () => {
    sesion(duena);
    const { editadas } = mockDetalle([firulais]);
    const { user } = renderDetalle();
    await user.click(await screen.findByRole("button", { name: "Editar a Firulais" }));
    const panel = await screen.findByRole("dialog", { name: "Editar mascota" });
    const nombre = within(panel).getByLabelText("Nombre");
    await user.clear(nombre);
    await user.type(nombre, "Firu");
    await user.click(within(panel).getByRole("button", { name: "Guardar cambios" }));

    expect(await screen.findByText("Mascota actualizada")).toBeInTheDocument();
    expect(await screen.findByText("Firu · Perro")).toBeInTheDocument();
    expect(editadas).toEqual([{ nombre: "Firu", tipo: "perro" }]);
  });

  it("la dueña da de baja una mascota con confirmación", async () => {
    sesion(duena);
    const { bajas } = mockDetalle([firulais, mishi]);
    const { user } = renderDetalle();
    await user.click(await screen.findByRole("button", { name: "Dar de baja a Firulais" }));
    const dialogo = await screen.findByRole("alertdialog");
    expect(bajas).toEqual([]);
    await user.click(within(dialogo).getByRole("button", { name: "Dar de baja" }));

    expect(await screen.findByText("Mascota dada de baja")).toBeInTheDocument();
    expect(bajas).toEqual(["m-1"]);
    expect(screen.queryByText("Firulais · Perro")).not.toBeInTheDocument();
    expect(screen.getByText("Mishi · Gato")).toBeInTheDocument();
  });
});

describe("ClienteDetallePage - estados de las mascotas", () => {
  const firulais: Mascota = { id: "m-1", nombre: "Firulais", tipo: "perro", activo: true };

  function renderDetalle() {
    return renderWithProviders(
      <Routes>
        <Route path="/clientes/:id" element={<ClienteDetallePage />} />
      </Routes>,
      { route: "/clientes/c-1" },
    );
  }

  function mockBase(): void {
    server.use(
      http.get("/api/clientes/c-1", () => HttpResponse.json(makeCliente())),
      http.get("/api/clientes/c-1/ventas", () => HttpResponse.json(paginated([]))),
    );
  }

  beforeEach(() => sesion(mostrador));

  it("mientras carga muestra un indicador etiquetado y 'Agregar mascota' deshabilitado", async () => {
    mockBase();
    server.use(
      http.get("/api/clientes/c-1/mascotas", async () => {
        await delay(400);
        return HttpResponse.json([firulais]);
      }),
    );
    renderDetalle();

    expect(await screen.findByLabelText("Cargando mascotas")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "Agregar mascota" })).toBeDisabled();
    expect(await screen.findByText("Firulais · Perro")).toBeInTheDocument();
    expect(screen.queryByLabelText("Cargando mascotas")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agregar mascota" })).toBeEnabled();
  });

  it("un 500 muestra el error con 'Reintentar' y al reintentar con éxito la lista", async () => {
    mockBase();
    let fallar = true;
    server.use(
      http.get("/api/clientes/c-1/mascotas", () =>
        fallar ? HttpResponse.json({ detail: "boom" }, { status: 500 }) : HttpResponse.json([firulais]),
      ),
    );
    const { user } = renderDetalle();

    expect(await screen.findByText("No pudimos cargar las mascotas")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agregar mascota" })).toBeInTheDocument();
    fallar = false;
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("Firulais · Perro")).toBeInTheDocument();
    expect(screen.queryByText("No pudimos cargar las mascotas")).not.toBeInTheDocument();
  });

  it("una recarga fallida con datos en pantalla avisa y conserva la lista", async () => {
    mockBase();
    let fallar = false;
    server.use(
      http.get("/api/clientes/c-1/mascotas", () =>
        fallar ? HttpResponse.json({ detail: "boom" }, { status: 500 }) : HttpResponse.json([firulais]),
      ),
    );
    const { user, queryClient } = renderDetalle();
    expect(await screen.findByText("Firulais · Perro")).toBeInTheDocument();

    fallar = true;
    await act(() => queryClient.invalidateQueries({ queryKey: ["clientes"] }));

    expect(await screen.findByText("No pudimos actualizar las mascotas")).toBeInTheDocument();
    expect(screen.getByText("Firulais · Perro")).toBeInTheDocument();
    fallar = false;
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(screen.queryByText("No pudimos actualizar las mascotas")).not.toBeInTheDocument());
    expect(screen.getByText("Firulais · Perro")).toBeInTheDocument();
  });
});

describe("ClienteDetallePage - cliente de baja y paginación", () => {
  const firulais: Mascota = { id: "m-1", nombre: "Firulais", tipo: "perro", activo: true };

  function renderDetalle() {
    return renderWithProviders(
      <Routes>
        <Route path="/clientes/:id" element={<ClienteDetallePage />} />
      </Routes>,
      { route: "/clientes/c-1" },
    );
  }

  it("la ficha de un cliente de baja es de solo lectura", async () => {
    sesion(duena);
    server.use(
      http.get("/api/clientes/c-1", () => HttpResponse.json(makeCliente({ activo: false }))),
      http.get("/api/clientes/c-1/ventas", () => HttpResponse.json(paginated([]))),
      http.get("/api/clientes/c-1/mascotas", () => HttpResponse.json([firulais])),
    );
    renderDetalle();

    expect(await screen.findByText("Cliente dado de baja")).toBeInTheDocument();
    expect(await screen.findByText("Firulais · Perro")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Agregar mascota" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /dar de baja a firulais/i })).not.toBeInTheDocument();
  });

  it("un cliente de baja sin mascotas no ofrece agregar", async () => {
    sesion(mostrador);
    server.use(
      http.get("/api/clientes/c-1", () => HttpResponse.json(makeCliente({ activo: false }))),
      http.get("/api/clientes/c-1/ventas", () => HttpResponse.json(paginated([]))),
      http.get("/api/clientes/c-1/mascotas", () => HttpResponse.json([])),
    );
    renderDetalle();

    expect(await screen.findByText("Sin mascotas registradas")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Agregar mascota" })).not.toBeInTheDocument();
  });

  it("el 404 dice que el cliente no existe o el enlace es incorrecto", async () => {
    sesion(duena);
    server.use(http.get("/api/clientes/c-1", () => HttpResponse.json({ detail: "cliente no encontrado" }, { status: 404 })));
    renderDetalle();

    expect(await screen.findByText("El cliente no existe o el enlace es incorrecto")).toBeInTheDocument();
    expect(screen.queryByText(/dado de baja/i)).not.toBeInTheDocument();
  });

  it("si la página del historial queda vacía vuelve a la última con datos", async () => {
    sesion(mostrador);
    const venta = (n: number): VentaResumen => ({
      id: `v-${n}`,
      estado: "confirmada",
      cliente_id: "c-1",
      usuario_id: "u-1",
      total: "100.00",
      created_at: "2026-10-06T15:00:00Z",
      confirmada_at: "2026-10-06T15:01:00Z",
      anulada_at: null,
    });
    let pagina2Pedida = false;
    server.use(
      http.get("/api/clientes/c-1", () => HttpResponse.json(makeCliente())),
      http.get("/api/clientes/c-1/mascotas", () => HttpResponse.json([])),
      http.get("/api/clientes/c-1/ventas", ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get("page"));
        if (page === 1) {
          const items = Array.from({ length: 20 }, (_, i) => venta(i));
          return HttpResponse.json({ ...paginated(items), total: pagina2Pedida ? 20 : 21 });
        }
        pagina2Pedida = true;
        return HttpResponse.json({ ...paginated([], 2), total: 20 });
      }),
    );
    const { user } = renderDetalle();
    await screen.findByText("21 resultados");

    await user.click(screen.getByRole("button", { name: /siguiente/i }));

    expect(await screen.findByText("Página 1 de 1")).toBeInTheDocument();
    expect(screen.queryByText("Todavía no compró")).not.toBeInTheDocument();
    expect(screen.getAllByRole("row").length).toBeGreaterThan(1);
  });
});

describe("ClientesPage - estados de la lista", () => {
  it("un error de carga ofrece 'Reintentar' y al reintentar muestra la lista", async () => {
    sesion(mostrador);
    let fallar = true;
    server.use(
      http.get("/api/clientes", () =>
        fallar ? HttpResponse.json({ detail: "boom" }, { status: 500 }) : HttpResponse.json(paginated([makeCliente()])),
      ),
    );
    const { user } = renderLista();

    expect(await screen.findByText("No pudimos cargar los clientes")).toBeInTheDocument();
    fallar = false;
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("Ana Perez")).toBeInTheDocument();
    expect(screen.queryByText("No pudimos cargar los clientes")).not.toBeInTheDocument();
  });

  it("una búsqueda sin resultados lo explica", async () => {
    sesion(mostrador);
    mockClientes([makeCliente()]);
    server.use(http.get("/api/clientes/buscar", () => HttpResponse.json(paginated([]))));
    const { user } = renderLista();
    await screen.findByText("Ana Perez");
    await user.type(screen.getByRole("searchbox", { name: "Buscar clientes" }), "zzz");

    expect(await screen.findByText("No encontramos clientes")).toBeInTheDocument();
    expect(screen.getByText(/Ningún cliente coincide con "zzz"/)).toBeInTheDocument();
  });

  it("la búsqueda se limita a 100 caracteres", async () => {
    sesion(mostrador);
    mockClientes([makeCliente()]);
    server.use(http.get("/api/clientes/buscar", () => HttpResponse.json(paginated([]))));
    const { user } = renderLista();
    await screen.findByText("Ana Perez");
    const buscador = screen.getByRole("searchbox", { name: "Buscar clientes" });
    await user.type(buscador, "a".repeat(120));

    expect(buscador).toHaveAttribute("maxlength", "100");
    expect(buscador).toHaveValue("a".repeat(100));
  });

  it("la dueña da de baja un cliente con confirmación y ve el aviso", async () => {
    sesion(duena);
    const bajas: string[] = [];
    mockClientes([makeCliente()]);
    server.use(
      http.delete("/api/clientes/:id", ({ params }) => {
        bajas.push(String(params.id));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderLista();
    await user.click(await screen.findByRole("button", { name: "Acciones de Ana Perez" }));
    await user.click(await screen.findByRole("menuitem", { name: /dar de baja/i }));
    const dialogo = await screen.findByRole("alertdialog");
    expect(bajas).toEqual([]);
    await user.click(within(dialogo).getByRole("button", { name: "Dar de baja" }));

    expect(await screen.findByText("Cliente dado de baja")).toBeInTheDocument();
    expect(bajas).toEqual(["c-1"]);
  });

  it("al dar de baja al único cliente de la página 2 muestra la página 1", async () => {
    sesion(duena);
    let baja = false;
    const cliente = (n: number): Cliente => makeCliente({ id: `c-${n}`, nombre: `Cliente ${n}` });
    server.use(
      http.get("/api/clientes", ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get("page"));
        if (page === 1) {
          return HttpResponse.json({ ...paginated(Array.from({ length: 20 }, (_, i) => cliente(i + 1))), total: baja ? 20 : 21 });
        }
        return HttpResponse.json(
          baja ? { ...paginated([], 2), total: 20 } : { ...paginated([cliente(21)], 2), total: 21 },
        );
      }),
      http.delete("/api/clientes/:id", () => {
        baja = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderLista();
    await screen.findByText("Cliente 1");
    await user.click(screen.getByRole("button", { name: /siguiente/i }));
    await user.click(await screen.findByRole("button", { name: "Acciones de Cliente 21" }));
    await user.click(await screen.findByRole("menuitem", { name: /dar de baja/i }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Dar de baja" }));

    expect(await screen.findByText("Página 1 de 1")).toBeInTheDocument();
    expect(screen.getByText("Cliente 1")).toBeInTheDocument();
    expect(screen.queryByText("Todavía no hay clientes")).not.toBeInTheDocument();
  });
});
