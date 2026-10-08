import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { ClienteSelector } from "@/features/pos/ClienteSelector";
import { useCartStore } from "@/features/pos/useCartStore";
import { makeCliente, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

beforeEach(() => {
  useCartStore.getState().clear();
});

describe("ClienteSelector", () => {
  it("crea un cliente inline con solo el nombre y lo asocia a la venta", async () => {
    let creado: unknown = null;
    server.use(
      http.get("/api/clientes/buscar", () => HttpResponse.json(paginated([]))),
      http.post("/api/clientes", async ({ request }) => {
        creado = await request.json();
        return HttpResponse.json(makeCliente({ id: "c-9", nombre: "Martina" }), { status: 201 });
      }),
    );
    const { user } = renderWithProviders(
      <>
        <ClienteSelector />
        <Toaster />
      </>,
    );
    await user.click(screen.getByRole("button", { name: /agregar cliente/i }));
    await user.type(await screen.findByPlaceholderText(/nombre, email o teléfono/i), "Martina");
    await user.click(await screen.findByRole("option", { name: /crear cliente "martina"/i }));
    await waitFor(() => expect(useCartStore.getState().cliente?.id).toBe("c-9"));
    expect(creado).toEqual({ nombre: "Martina" });
    expect(await screen.findByText("Cliente creado")).toBeInTheDocument();
  });

  it("elige un cliente existente y permite quitarlo", async () => {
    server.use(
      http.get("/api/clientes/buscar", () =>
        HttpResponse.json(paginated([makeCliente({ id: "c-1", nombre: "Ana Perez", telefono: "1155550000" })])),
      ),
    );
    const { user } = renderWithProviders(
      <>
        <ClienteSelector />
        <Toaster />
      </>,
    );
    await user.click(screen.getByRole("button", { name: /agregar cliente/i }));
    await user.type(await screen.findByPlaceholderText(/nombre, email o teléfono/i), "ana");
    await user.click(await screen.findByRole("option", { name: /ana perez/i }));
    expect(useCartStore.getState().cliente?.id).toBe("c-1");
    await user.click(await screen.findByRole("button", { name: /quitar cliente/i }));
    expect(useCartStore.getState().cliente).toBeNull();
    expect(screen.getByRole("button", { name: /agregar cliente/i })).toBeInTheDocument();
  });

  it("ofrece 'Crear cliente' antes que los resultados de la busqueda", async () => {
    server.use(
      http.get("/api/clientes/buscar", () =>
        HttpResponse.json(paginated([makeCliente({ id: "c-1", nombre: "Ana Perez", telefono: "1155550000" })])),
      ),
    );
    const { user } = renderWithProviders(<ClienteSelector />);
    await user.click(screen.getByRole("button", { name: /agregar cliente/i }));
    await user.type(await screen.findByPlaceholderText(/nombre, email o teléfono/i), "Ana");
    await screen.findByRole("option", { name: /ana perez/i });
    const nombres = screen.getAllByRole("option").map((o) => o.textContent ?? "");
    expect(nombres[0]).toMatch(/crear cliente "ana"/i);
    expect(nombres[1]).toMatch(/ana perez/i);
  });

  it("no muestra resultados viejos mientras llega la busqueda del texto nuevo", async () => {
    server.use(
      http.get("/api/clientes/buscar", async ({ request }) => {
        const q = new URL(request.url).searchParams.get("q");
        if (q === "Anabel") {
          await new Promise((resolve) => setTimeout(resolve, 400));
          return HttpResponse.json(paginated([]));
        }
        return HttpResponse.json(paginated([makeCliente({ id: "c-1", nombre: "Ana Perez" })]));
      }),
    );
    const { user } = renderWithProviders(<ClienteSelector />);
    await user.click(screen.getByRole("button", { name: /agregar cliente/i }));
    const input = await screen.findByPlaceholderText(/nombre, email o teléfono/i);
    await user.type(input, "Ana");
    await screen.findByRole("option", { name: /ana perez/i });
    await user.type(input, "bel");
    await screen.findByText(/buscando/i);
    expect(screen.queryByRole("option", { name: /ana perez/i })).not.toBeInTheDocument();
  });

  it("informa el error del servidor si el alta falla y no asocia cliente", async () => {
    server.use(
      http.get("/api/clientes/buscar", () => HttpResponse.json(paginated([]))),
      http.post("/api/clientes", () => HttpResponse.json({ detail: "Ya existe un cliente con ese nombre" }, { status: 409 })),
    );
    const { user } = renderWithProviders(
      <>
        <ClienteSelector />
        <Toaster />
      </>,
    );
    await user.click(screen.getByRole("button", { name: /agregar cliente/i }));
    await user.type(await screen.findByPlaceholderText(/nombre, email o teléfono/i), "Martina");
    await user.click(await screen.findByRole("option", { name: /crear cliente "martina"/i }));
    expect(await screen.findByText("Ya existe un cliente con ese nombre")).toBeInTheDocument();
    expect(useCartStore.getState().cliente).toBeNull();
  });
});
