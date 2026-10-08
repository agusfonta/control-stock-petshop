import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { duena, mostrador } from "@/test/fixtures";
import { renderApp } from "@/test/renderApp";

const anchoOriginal = window.innerWidth;
afterEach(() => {
  window.innerWidth = anchoOriginal;
});

function itemDe(link: HTMLElement): HTMLElement {
  const li = link.closest("li");
  if (li === null) throw new Error("La entrada de navegacion no esta dentro de un <li>");
  return li;
}

describe("AppShell", () => {
  it("muestra 3 en la entrada Stock cuando hay 3 alertas", async () => {
    renderApp({ route: "/pos", user: duena, alertas: 3 });

    const stock = await screen.findByRole("link", { name: /^stock/i });
    expect(await within(itemDe(stock)).findByText("3")).toBeInTheDocument();
  });

  it("no muestra badge cuando no hay alertas", async () => {
    renderApp({ route: "/pos", user: duena, alertas: 0 });

    const stock = await screen.findByRole("link", { name: /^stock/i });
    expect(within(itemDe(stock)).queryByText("0")).not.toBeInTheDocument();
  });

  it("dueña ve todas las entradas, incluidas las de reportes completos", async () => {
    renderApp({ route: "/pos", user: duena });

    for (const nombre of ["POS", "Ventas", "Productos", "Stock", "Distribuidoras", "Pedidos", "Clientes", "Ventas del día", "Reposición", "Más vendidos", "Márgenes"]) {
      expect(await screen.findByRole("link", { name: nombre })).toBeInTheDocument();
    }
  });

  it("mostrador no ve las entradas exclusivas de dueña", async () => {
    renderApp({ route: "/pos", user: mostrador });

    expect(await screen.findByRole("link", { name: /^Reposición/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Más vendidos/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Márgenes/ })).not.toBeInTheDocument();
  });

  it("muestra email y rol del usuario y el boton de cerrar sesion", async () => {
    renderApp({ route: "/pos", user: mostrador });

    expect(await screen.findByText(mostrador.email)).toBeInTheDocument();
    expect(screen.getByText("Mostrador")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  });

  it("marca la entrada activa con aria-current", async () => {
    renderApp({ route: "/stock", user: duena });

    expect(await screen.findByRole("link", { name: /^Stock/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /^POS/ })).not.toHaveAttribute("aria-current");
  });

  it("en telefono la navegacion queda tras un boton de menu (Sheet)", async () => {
    window.innerWidth = 375;
    const { user } = renderApp({ route: "/pos", user: duena });

    const menu = await screen.findByRole("button", { name: /abrir menú/i });
    expect(screen.queryByRole("link", { name: /^Productos/ })).not.toBeInTheDocument();

    await user.click(menu);

    expect(await screen.findByRole("link", { name: /^Productos/ })).toBeInTheDocument();
  });
});
