import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { PosPage } from "@/features/pos/PosPage";
import { useCartStore } from "@/features/pos/useCartStore";
import { makeProducto, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const royal = makeProducto({
  id: "p-1",
  sku: "RC-MINI-3KG",
  nombre: "Royal Canin Mini Adult 3 kg",
  precio_venta: "24300.00",
  stock_actual: 10,
});
const agotado = makeProducto({ id: "p-2", sku: "AG-1", nombre: "Alimento agotado", precio_venta: "1000.00", stock_actual: 0 });
const chico = makeProducto({ id: "p-3", sku: "CH-1", nombre: "Pelota chica", precio_venta: "500.00", stock_actual: 2 });
const catalogo = [royal, agotado, chico];

/** El debounce de 250 ms + la red de MSW pueden tardar si la maquina esta cargada. */
const ESPERA = { timeout: 4000 };

beforeEach(() => {
  useCartStore.getState().clear();
  server.use(
    http.get("/api/productos/buscar", ({ request }) => {
      const q = (new URL(request.url).searchParams.get("q") ?? "").toLowerCase();
      const items = catalogo.filter((p) => p.sku.toLowerCase() === q || p.nombre.toLowerCase().includes(q));
      return HttpResponse.json(paginated(items));
    }),
  );
});

function buscador(): HTMLElement {
  return screen.getByRole("searchbox", { name: /buscar producto/i });
}

describe("PosPage: busqueda", () => {
  it("arranca con el foco en el buscador", () => {
    renderWithProviders(<PosPage />);
    expect(buscador()).toHaveFocus();
  });

  it("lista resultados con precio y stock tras una pausa", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(buscador(), "royal");
    const fila = await screen.findByRole("button", { name: /royal canin mini adult 3 kg/i }, ESPERA);
    expect(fila).toHaveTextContent("RC-MINI-3KG");
    expect(fila).toHaveTextContent("24.300,00");
  });

  it("muestra 'Sin stock' deshabilitado y no lo agrega", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(buscador(), "agotado");
    const fila = await screen.findByRole("button", { name: /alimento agotado/i }, ESPERA);
    expect(fila).toBeDisabled();
    expect(fila).toHaveTextContent("Sin stock");
    await user.click(fila);
    expect(useCartStore.getState().lineas).toHaveLength(0);
  });
});

describe("PosPage: lector de codigo de barras", () => {
  it("escanear un SKU + Enter agrega 1 unidad, limpia el buscador y mantiene el foco", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(buscador(), "RC-MINI-3KG{Enter}");
    await waitFor(() => expect(useCartStore.getState().lineas).toHaveLength(1));
    expect(useCartStore.getState().lineas[0]).toMatchObject({ productoId: "p-1", cantidad: 1 });
    expect(buscador()).toHaveValue("");
    expect(buscador()).toHaveFocus();
  });

  it("escanear dos veces el mismo codigo suma cantidad en una sola linea", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(buscador(), "RC-MINI-3KG{Enter}");
    await waitFor(() => expect(useCartStore.getState().lineas).toHaveLength(1));
    await user.type(buscador(), "rc-mini-3kg{Enter}");
    await waitFor(() => expect(useCartStore.getState().lineas[0]?.cantidad).toBe(2));
    expect(useCartStore.getState().lineas).toHaveLength(1);
  });

  it("un codigo inexistente avisa y no cambia el carrito", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(buscador(), "7790000999999{Enter}");
    expect(await screen.findByText(/No encontramos el código 7790000999999/)).toBeInTheDocument();
    expect(useCartStore.getState().lineas).toHaveLength(0);
  });

  it("una tecla con el foco fuera de un campo va al buscador y conserva el caracter", async () => {
    const { user } = renderWithProviders(<PosPage />);
    (document.activeElement as HTMLElement).blur();
    await user.keyboard("r");
    expect(buscador()).toHaveFocus();
    expect(buscador()).toHaveValue("r");
  });

  it("F2 devuelve el foco al buscador", async () => {
    const { user } = renderWithProviders(<PosPage />);
    (document.activeElement as HTMLElement).blur();
    await user.keyboard("{F2}");
    expect(buscador()).toHaveFocus();
  });
});

describe("PosPage: carrito", () => {
  it("topa en el stock con el aviso 'Solo hay N unidades'", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(buscador(), "pelota");
    const fila = await screen.findByRole("button", { name: /pelota chica/i }, ESPERA);
    await user.click(fila);
    await user.click(fila);
    await user.click(fila);
    expect(useCartStore.getState().lineas[0]?.cantidad).toBe(2);
    expect(await screen.findByText("Solo hay 2 unidades")).toBeInTheDocument();
  });

  it("calcula el total y habilita Cobrar solo con productos", async () => {
    const { user } = renderWithProviders(<PosPage />);
    expect(screen.getByRole("button", { name: /cobrar/i })).toBeDisabled();
    await user.type(buscador(), "RC-MINI-3KG{Enter}");
    const carrito = await screen.findByRole("region", { name: /carrito/i });
    await waitFor(() => expect(within(carrito).getAllByText(/24\.300,00/).length).toBeGreaterThan(0));
    expect(screen.getByRole("button", { name: /cobrar/i })).toBeEnabled();
  });

  it("cambia la cantidad con el stepper y quita la linea", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(buscador(), "RC-MINI-3KG{Enter}");
    await user.click(await screen.findByRole("button", { name: /sumar una unidad/i }));
    expect(useCartStore.getState().lineas[0]?.cantidad).toBe(2);
    await user.click(screen.getByRole("button", { name: /quitar royal canin/i }));
    expect(useCartStore.getState().lineas).toHaveLength(0);
  });

  it("vaciar pide confirmacion", async () => {
    const { user } = renderWithProviders(<PosPage />);
    await user.type(buscador(), "RC-MINI-3KG{Enter}");
    await user.click(await screen.findByRole("button", { name: /vaciar carrito/i }));
    await user.click(await screen.findByRole("button", { name: /^vaciar$/i }));
    expect(useCartStore.getState().lineas).toHaveLength(0);
  });

  it("conserva el carrito al salir de la pantalla y volver", async () => {
    const primero = renderWithProviders(<PosPage />);
    await primero.user.type(buscador(), "RC-MINI-3KG{Enter}");
    await waitFor(() => expect(useCartStore.getState().lineas).toHaveLength(1));
    primero.unmount();
    renderWithProviders(<PosPage />);
    expect(await screen.findByText(/royal canin mini adult 3 kg/i)).toBeInTheDocument();
  });

  it("marca las lineas con faltantes y ofrece 'Ajustar a disponible'", async () => {
    const { user } = renderWithProviders(<PosPage />);
    useCartStore.getState().addProduct(royal, 3);
    useCartStore.getState().applyFaltantes([{ producto_id: "p-1", solicitado: 3, disponible: 1 }]);
    expect(await screen.findByText("Disponible: 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cobrar/i })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /ajustar a disponible/i }));
    expect(useCartStore.getState().lineas[0]?.cantidad).toBe(1);
    expect(screen.queryByText("Disponible: 1")).not.toBeInTheDocument();
  });
});
