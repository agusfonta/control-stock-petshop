import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { PISTA_SESION, useSession } from "@/features/auth/session";
import { duena } from "@/test/fixtures";
import { renderApp } from "@/test/renderApp";
import { server } from "@/test/server";

type User = ReturnType<typeof renderApp>["user"];

async function completarYEnviar(user: User, email = "duena@petshop.local", password = "clave-incorrecta"): Promise<void> {
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Contraseña"), password);
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
}

function loginOk(): void {
  server.use(
    http.post("/api/auth/login", () => HttpResponse.json({ access_token: "t", token_type: "bearer" })),
    http.get("/api/auth/me", () => HttpResponse.json(duena)),
  );
}

describe("LoginPage", () => {
  it("401 muestra un mensaje generico y no guarda token ni pista", async () => {
    server.use(http.post("/api/auth/login", () => HttpResponse.json({ detail: "credenciales invalidas" }, { status: 401 })));
    const { user } = renderApp({ route: "/login" });

    await completarYEnviar(user);

    expect(await screen.findByText("Email o contraseña incorrectos")).toBeInTheDocument();
    expect(useSession.getState().accessToken).toBeNull();
    expect(window.localStorage.getItem(PISTA_SESION)).toBeNull();
    expect(screen.getByRole("heading", { name: /ingresá a animall/i })).toBeInTheDocument();
  });

  it("429 indica demasiados intentos", async () => {
    server.use(http.post("/api/auth/login", () => HttpResponse.json({ detail: "rate" }, { status: 429 })));
    const { user } = renderApp({ route: "/login" });

    await completarYEnviar(user);

    expect(await screen.findByText(/demasiados intentos/i)).toBeInTheDocument();
    expect(screen.getByText(/en unos minutos/i)).toBeInTheDocument();
  });

  it.each([
    ["503", () => HttpResponse.json({ detail: "redis" }, { status: 503 })],
    ["error de red", () => HttpResponse.error()],
  ])("%s indica que el servidor no esta disponible", async (_nombre, resolver) => {
    server.use(http.post("/api/auth/login", resolver));
    const { user } = renderApp({ route: "/login" });

    await completarYEnviar(user);

    expect(await screen.findByText(/el servidor no está disponible/i)).toBeInTheDocument();
  });

  it("422 marca el campo invalido", async () => {
    server.use(
      http.post("/api/auth/login", () =>
        HttpResponse.json(
          { detail: [{ loc: ["body", "email"], msg: "value is not a valid email address", type: "value_error" }] },
          { status: 422 },
        ),
      ),
    );
    const { user } = renderApp({ route: "/login" });

    await completarYEnviar(user, "ana@dominio.com", "algo");

    expect(await screen.findByText("value is not a valid email address")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });

  it("valida campos vacios en el cliente sin llamar a la API", async () => {
    const { user } = renderApp({ route: "/login" });

    await user.click(screen.getByRole("button", { name: "Ingresar" }));

    expect(await screen.findByText("Ingresá tu email")).toBeInTheDocument();
    expect(screen.getByText("Ingresá tu contraseña")).toBeInTheDocument();
  });

  it("deshabilita el boton con indicador de carga mientras envia", async () => {
    server.use(
      http.post("/api/auth/login", async () => {
        await new Promise((resolve) => setTimeout(resolve, 150));
        return HttpResponse.json({ access_token: "t", token_type: "bearer" });
      }),
      http.get("/api/auth/me", () => HttpResponse.json(duena)),
    );
    const { user } = renderApp({ route: "/login" });

    await completarYEnviar(user, duena.email, "demo-duena-2026");

    expect(screen.getByRole("button", { name: /ingresando/i })).toBeDisabled();
    expect(await screen.findByRole("heading", { name: "POS", level: 1 })).toBeInTheDocument();
  });

  it("login sin ruta pedida va a /pos y guarda la pista", async () => {
    loginOk();
    const { user } = renderApp({ route: "/login" });

    await completarYEnviar(user, duena.email, "demo-duena-2026");

    expect(await screen.findByRole("heading", { name: "POS", level: 1 })).toBeInTheDocument();
    expect(window.localStorage.getItem(PISTA_SESION)).toBe("1");
  });

  it("ignora un next externo", async () => {
    loginOk();
    const { user } = renderApp({ route: "/login?next=//evil.example" });

    await completarYEnviar(user, duena.email, "demo-duena-2026");

    expect(await screen.findByRole("heading", { name: "POS", level: 1 })).toBeInTheDocument();
  });

  it("con ?expired=1 muestra el aviso de sesion vencida", () => {
    renderApp({ route: "/login?expired=1" });
    expect(screen.getByText(/tu sesión expiró/i)).toBeInTheDocument();
  });

  it("una sesion ya iniciada en /login redirige a /pos", async () => {
    renderApp({ route: "/login", user: duena });
    expect(await screen.findByRole("heading", { name: "POS", level: 1 })).toBeInTheDocument();
  });
});
