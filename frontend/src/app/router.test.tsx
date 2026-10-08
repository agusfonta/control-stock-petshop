import { screen, waitFor } from "@testing-library/react";
import { act } from "react";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { PISTA_SESION, useSession } from "@/features/auth/session";
import { duena, mostrador } from "@/test/fixtures";
import { renderApp } from "@/test/renderApp";
import { server } from "@/test/server";

function loginHandlers(user: typeof duena): void {
  server.use(
    http.post("/api/auth/login", () => HttpResponse.json({ access_token: "tok-1", token_type: "bearer" })),
    http.get("/api/auth/me", () => HttpResponse.json(user)),
  );
}

describe("guards de ruta", () => {
  it("sin sesion redirige a /login y, tras el login, vuelve a la ruta pedida", async () => {
    loginHandlers(duena);
    const { user } = renderApp({ route: "/stock", user: null });

    expect(await screen.findByRole("heading", { name: /ingresá a animall/i })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Email"), duena.email);
    await user.type(screen.getByLabelText("Contraseña"), "demo-duena-2026");
    await user.click(screen.getByRole("button", { name: "Ingresar" }));

    expect(await screen.findByRole("heading", { name: "Stock", level: 1 })).toBeInTheDocument();
    expect(screen.getByText(duena.email)).toBeInTheDocument();
    expect(screen.getByText("Dueña")).toBeInTheDocument();
  });

  it("sin pista de sesion el arranque queda anonimo y muestra el login", async () => {
    renderApp({ route: "/pos", user: "loading" });
    expect(await screen.findByRole("heading", { name: /ingresá a animall/i })).toBeInTheDocument();
  });

  it("con pista restaura la sesion (refresh + me) y muestra la pantalla pedida", async () => {
    window.localStorage.setItem(PISTA_SESION, "1");
    server.use(
      http.post("/api/auth/refresh", () => HttpResponse.json({ access_token: "tok-r", token_type: "bearer" })),
      http.get("/api/auth/me", () => HttpResponse.json(duena)),
    );
    renderApp({ route: "/stock", user: "loading" });
    expect(await screen.findByRole("heading", { name: "Stock", level: 1 })).toBeInTheDocument();
  });

  it("mientras restaura la sesion muestra una pantalla de carga", async () => {
    window.localStorage.setItem(PISTA_SESION, "1");
    server.use(
      http.post("/api/auth/refresh", async () => {
        await delay("infinite");
        return HttpResponse.json({});
      }),
    );
    renderApp({ route: "/pos", user: "loading" });
    expect(await screen.findByRole("status", { name: /cargando/i })).toBeInTheDocument();
  });

  it("la ruta raiz lleva a /pos", async () => {
    renderApp({ route: "/", user: duena });
    expect(await screen.findByRole("heading", { name: "POS", level: 1 })).toBeInTheDocument();
  });

  it("la sesion expirada lleva a /login con el aviso", async () => {
    renderApp({ route: "/stock", user: duena });
    expect(await screen.findByRole("heading", { name: "Stock", level: 1 })).toBeInTheDocument();

    act(() => {
      useSession.getState().expire();
    });

    expect(await screen.findByText(/tu sesión expiró/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /ingresá a animall/i })).toBeInTheDocument();
  });

  it("mostrador en /reportes/margenes ve Sin permiso y puede volver al inicio", async () => {
    const { user } = renderApp({ route: "/reportes/margenes", user: mostrador });

    expect(await screen.findByText("Sin permiso")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Márgenes" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /volver al inicio/i }));
    expect(await screen.findByRole("heading", { name: "POS", level: 1 })).toBeInTheDocument();
  });

  it("dueña entra a /reportes/margenes", async () => {
    renderApp({ route: "/reportes/margenes", user: duena });
    expect(await screen.findByRole("heading", { name: "Márgenes", level: 1 })).toBeInTheDocument();
  });

  it("ruta desconocida muestra un 404 amistoso dentro del shell", async () => {
    renderApp({ route: "/no-existe", user: duena });
    expect(await screen.findByText(/no encontramos esta página/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /volver al inicio/i })).toBeInTheDocument();
  });

  it("cerrar sesion borra la pista y vuelve al login sin aviso de expiracion", async () => {
    window.localStorage.setItem(PISTA_SESION, "1");
    const { user } = renderApp({ route: "/pos", user: duena });

    await user.click(await screen.findByRole("button", { name: "Cerrar sesión" }));

    expect(await screen.findByRole("heading", { name: /ingresá a animall/i })).toBeInTheDocument();
    expect(screen.queryByText(/tu sesión expiró/i)).not.toBeInTheDocument();
    expect(window.localStorage.getItem(PISTA_SESION)).toBeNull();
    await waitFor(() => expect(useSession.getState().status).toBe("anonymous"));
  });
});
