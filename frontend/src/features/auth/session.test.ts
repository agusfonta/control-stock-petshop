import { QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  PISTA_SESION,
  registerLogoutCleanup,
  useSession,
} from "@/features/auth/session";
import { resetRefreshState } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { queryClient } from "@/shared/api/queryClient";
import type { Me } from "@/shared/api/types";
import { server } from "@/test/server";

const duena: Me = { id: "u1", email: "duena@petshop.local", rol: "duena", activo: true };

function handlersLoginOk(): void {
  server.use(
    http.post("/api/auth/login", () => HttpResponse.json({ access_token: "tok-1", token_type: "bearer" })),
    http.get("/api/auth/me", ({ request }) =>
      request.headers.get("Authorization") === "Bearer tok-1" || request.headers.get("Authorization") === "Bearer tok-r"
        ? HttpResponse.json(duena)
        : HttpResponse.json({ detail: "no autenticado" }, { status: 401 }),
    ),
  );
}

beforeEach(() => {
  resetRefreshState();
  useSession.setState({ status: "loading", accessToken: null, user: null, expired: false });
});

describe("useSession.login", () => {
  it("guarda token en memoria, user y la pista de sesion", async () => {
    handlersLoginOk();

    await useSession.getState().login({ email: duena.email, password: "x" });

    const s = useSession.getState();
    expect(s.status).toBe("authenticated");
    expect(s.accessToken).toBe("tok-1");
    expect(s.user).toEqual(duena);
    expect(window.localStorage.getItem(PISTA_SESION)).toBe("1");
    expect(JSON.stringify(window.localStorage)).not.toContain("tok-1");
    expect(JSON.stringify(window.sessionStorage)).not.toContain("tok-1");
  });

  it("con credenciales invalidas propaga el error y no guarda nada", async () => {
    server.use(http.post("/api/auth/login", () => HttpResponse.json({ detail: "credenciales invalidas" }, { status: 401 })));

    await expect(useSession.getState().login({ email: "a@b.co", password: "mal" })).rejects.toMatchObject({
      status: 401,
    });

    const s = useSession.getState();
    expect(s.accessToken).toBeNull();
    expect(s.user).toBeNull();
    expect(s.status).not.toBe("authenticated");
    expect(window.localStorage.getItem(PISTA_SESION)).toBeNull();
  });

  it("si /me falla tras el login no deja sesion a medias", async () => {
    server.use(
      http.post("/api/auth/login", () => HttpResponse.json({ access_token: "tok-1", token_type: "bearer" })),
      http.get("/api/auth/me", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );

    await expect(useSession.getState().login({ email: "a@b.co", password: "x" })).rejects.toMatchObject({
      status: 500,
    });

    expect(useSession.getState().accessToken).toBeNull();
    expect(window.localStorage.getItem(PISTA_SESION)).toBeNull();
  });
});

describe("useSession.logout", () => {
  it("borra token, pista, cache de React Query y ejecuta limpiezas registradas (carrito)", async () => {
    handlersLoginOk();
    await useSession.getState().login({ email: duena.email, password: "x" });
    const limpiarCarrito = vi.fn();
    const baja = registerLogoutCleanup(limpiarCarrito);
    queryClient.setQueryData(["productos"], [1, 2, 3]);

    useSession.getState().logout();

    const s = useSession.getState();
    expect(s.status).toBe("anonymous");
    expect(s.accessToken).toBeNull();
    expect(s.user).toBeNull();
    expect(s.expired).toBe(false);
    expect(window.localStorage.getItem(PISTA_SESION)).toBeNull();
    expect(queryClient.getQueryData(["productos"])).toBeUndefined();
    expect(limpiarCarrito).toHaveBeenCalledTimes(1);
    baja();
  });

  it("una limpieza dada de baja ya no se ejecuta", () => {
    const fn = vi.fn();
    registerLogoutCleanup(fn)();

    useSession.getState().logout();

    expect(fn).not.toHaveBeenCalled();
  });
});

describe("useSession.expire", () => {
  it("limpia la sesion y marca expired para el aviso en /login", async () => {
    handlersLoginOk();
    await useSession.getState().login({ email: duena.email, password: "x" });

    useSession.getState().expire();
    useSession.getState().expire();

    const s = useSession.getState();
    expect(s.status).toBe("anonymous");
    expect(s.expired).toBe(true);
    expect(s.accessToken).toBeNull();
    expect(window.localStorage.getItem(PISTA_SESION)).toBeNull();
  });
});

describe("useSession.init (arranque)", () => {
  it("con pista hace refresh + me y queda authenticated", async () => {
    window.localStorage.setItem(PISTA_SESION, "1");
    let refreshes = 0;
    server.use(
      http.post("/api/auth/refresh", () => {
        refreshes += 1;
        return HttpResponse.json({ access_token: "tok-r", token_type: "bearer" });
      }),
      http.get("/api/auth/me", ({ request }) =>
        request.headers.get("Authorization") === "Bearer tok-r"
          ? HttpResponse.json(duena)
          : HttpResponse.json({ detail: "no" }, { status: 401 }),
      ),
    );

    await Promise.all([useSession.getState().init(), useSession.getState().init()]);

    expect(refreshes).toBe(1);
    expect(useSession.getState().status).toBe("authenticated");
    expect(useSession.getState().user).toEqual(duena);
  });

  it("sin pista queda anonymous sin llamar a la API", async () => {
    // onUnhandledRequest: "error" haria fallar cualquier llamada de red.
    await useSession.getState().init();

    expect(useSession.getState().status).toBe("anonymous");
    expect(useSession.getState().expired).toBe(false);
  });

  it("si el refresh es rechazado queda anonymous y borra la pista", async () => {
    window.localStorage.setItem(PISTA_SESION, "1");
    server.use(http.post("/api/auth/refresh", () => HttpResponse.json({ detail: "x" }, { status: 401 })));

    await useSession.getState().init();

    expect(useSession.getState().status).toBe("anonymous");
    expect(window.localStorage.getItem(PISTA_SESION)).toBeNull();
    expect(useSession.getState().expired).toBe(false);
  });

  it("si el servidor no responde queda anonymous pero conserva la pista", async () => {
    window.localStorage.setItem(PISTA_SESION, "1");
    server.use(http.post("/api/auth/refresh", () => HttpResponse.error()));

    await useSession.getState().init();

    expect(useSession.getState().status).toBe("anonymous");
    expect(window.localStorage.getItem(PISTA_SESION)).toBe("1");
  });
});

describe("localStorage no disponible", () => {
  it("no rompe login, init ni logout si getItem/setItem lanzan", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    handlersLoginOk();

    await useSession.getState().init();
    expect(useSession.getState().status).toBe("anonymous");

    await useSession.getState().login({ email: duena.email, password: "x" });
    expect(useSession.getState().status).toBe("authenticated");

    expect(() => useSession.getState().logout()).not.toThrow();
    expect(useSession.getState().status).toBe("anonymous");
  });
});

describe("queryClient por defecto (D6)", () => {
  it("no reintenta errores 4xx pero si errores de red o 5xx, una sola vez", () => {
    const retry = queryClient.getDefaultOptions().queries?.retry;
    expect(typeof retry).toBe("function");
    if (typeof retry !== "function") return;
    const mk = (status: number) => new ApiError(status, "x");
    expect(retry(0, mk(404))).toBe(false);
    expect(retry(0, mk(422))).toBe(false);
    expect(retry(0, mk(500))).toBe(true);
    expect(retry(0, mk(0))).toBe(true);
    expect(retry(1, mk(500))).toBe(false);
    expect(queryClient).toBeInstanceOf(QueryClient);
  });
});
