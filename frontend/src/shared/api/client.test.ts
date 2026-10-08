import { http, HttpResponse } from "msw";
import { type Mock, beforeEach, describe, expect, it, vi } from "vitest";
import { type AuthBridge, apiFetch, configureAuth, resetRefreshState } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { server } from "@/test/server";

let token: string | null;
let expire: Mock;

function instalarBridge(inicial: string | null): void {
  token = inicial;
  expire = vi.fn();
  const bridge: AuthBridge = {
    getAccessToken: () => token,
    setAccessToken: (t) => {
      token = t;
    },
    expire: () => expire(),
  };
  configureAuth(bridge);
}

async function capturar(promesa: Promise<unknown>): Promise<ApiError> {
  const resultado = await promesa.then(
    () => null,
    (e: unknown) => e,
  );
  expect(resultado).toBeInstanceOf(ApiError);
  return resultado as ApiError;
}

beforeEach(() => {
  resetRefreshState();
  instalarBridge("access-viejo");
});

describe("apiFetch", () => {
  it("agrega Authorization Bearer y devuelve el JSON", async () => {
    let auth: string | null = null;
    server.use(
      http.get("/api/productos", ({ request }) => {
        auth = request.headers.get("Authorization");
        return HttpResponse.json({ ok: true });
      }),
    );

    const data = await apiFetch<{ ok: boolean }>("/productos");

    expect(auth).toBe("Bearer access-viejo");
    expect(data).toEqual({ ok: true });
  });

  it("serializa query (omitiendo undefined/null) y body JSON", async () => {
    let url = "";
    let body: unknown = null;
    server.use(
      http.post("/api/clientes", async ({ request }) => {
        url = request.url;
        body = await request.json();
        return HttpResponse.json({ id: "c1" }, { status: 201 });
      }),
    );

    await apiFetch("/clientes", {
      method: "POST",
      query: { q: "ana", page: 2, vacio: undefined, nulo: null },
      body: { nombre: "Ana" },
    });

    expect(new URL(url).search).toBe("?q=ana&page=2");
    expect(body).toEqual({ nombre: "Ana" });
  });

  it("devuelve undefined ante 204", async () => {
    server.use(http.delete("/api/clientes/1", () => new HttpResponse(null, { status: 204 })));

    await expect(apiFetch("/clientes/1", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("detail string -> ApiError con mensaje", async () => {
    server.use(http.get("/api/x", () => HttpResponse.json({ detail: "permiso denegado" }, { status: 403 })));

    const err = await capturar(apiFetch("/x"));

    expect(err.status).toBe(403);
    expect(err.message).toBe("permiso denegado");
  });

  it("422 de Pydantic -> fieldErrors", async () => {
    server.use(
      http.post("/api/x", () =>
        HttpResponse.json(
          { detail: [{ loc: ["body", "nombre"], msg: "requerido", type: "missing" }] },
          { status: 422 },
        ),
      ),
    );

    const err = await capturar(apiFetch("/x", { method: "POST", body: {} }));

    expect(err.fieldErrors).toEqual({ nombre: "requerido" });
  });

  it("409 con faltantes -> ApiError.faltantes", async () => {
    const faltantes = [{ producto_id: "p1", solicitado: 3, disponible: 1 }];
    server.use(
      http.post("/api/x", () =>
        HttpResponse.json({ detail: { mensaje: "stock insuficiente", faltantes } }, { status: 409 }),
      ),
    );

    const err = await capturar(apiFetch("/x", { method: "POST", body: {} }));

    expect(err.status).toBe(409);
    expect(err.faltantes).toEqual(faltantes);
  });

  it("error de red -> ApiError status 0", async () => {
    server.use(http.get("/api/x", () => HttpResponse.error()));

    const err = await capturar(apiFetch("/x"));

    expect(err.status).toBe(0);
  });
});

describe("refresh single-flight", () => {
  it("dos 401 concurrentes producen UN refresh y ambos reintentan con el token nuevo", async () => {
    let refreshes = 0;
    const vistos: string[] = [];
    const rutaProtegida = (nombre: string) =>
      http.get(`/api/${nombre}`, ({ request }) => {
        const auth = request.headers.get("Authorization");
        if (auth === "Bearer access-viejo") {
          return HttpResponse.json({ detail: "no autenticado" }, { status: 401 });
        }
        vistos.push(`${nombre}:${auth}`);
        return HttpResponse.json({ r: nombre });
      });
    server.use(
      http.post("/api/auth/refresh", async () => {
        refreshes += 1;
        await new Promise((resolve) => setTimeout(resolve, 20));
        return HttpResponse.json({ access_token: "access-nuevo", token_type: "bearer" });
      }),
      rutaProtegida("a"),
      rutaProtegida("b"),
    );

    const [a, b] = await Promise.all([apiFetch<{ r: string }>("/a"), apiFetch<{ r: string }>("/b")]);

    expect(refreshes).toBe(1);
    expect(a.r).toBe("a");
    expect(b.r).toBe("b");
    expect([...vistos].sort()).toEqual(["a:Bearer access-nuevo", "b:Bearer access-nuevo"]);
    expect(token).toBe("access-nuevo");
    expect(expire).not.toHaveBeenCalled();
  });

  it("reintenta una sola vez: si el reintento tambien da 401 no hace otro refresh", async () => {
    let refreshes = 0;
    server.use(
      http.post("/api/auth/refresh", () => {
        refreshes += 1;
        return HttpResponse.json({ access_token: "access-nuevo", token_type: "bearer" });
      }),
      http.get("/api/a", () => HttpResponse.json({ detail: "no autenticado" }, { status: 401 })),
    );

    const err = await capturar(apiFetch("/a"));

    expect(err.status).toBe(401);
    expect(refreshes).toBe(1);
  });

  it("refresh 401 llama a expire() y propaga el 401 original", async () => {
    server.use(
      http.post("/api/auth/refresh", () => HttpResponse.json({ detail: "credenciales invalidas" }, { status: 401 })),
      http.get("/api/a", () => HttpResponse.json({ detail: "no autenticado" }, { status: 401 })),
    );

    const err = await capturar(apiFetch("/a"));

    expect(err.status).toBe(401);
    expect(expire).toHaveBeenCalledTimes(1);
  });

  it("un 401 en /auth/login no dispara refresh ni expire", async () => {
    let refreshes = 0;
    server.use(
      http.post("/api/auth/refresh", () => {
        refreshes += 1;
        return HttpResponse.json({ access_token: "x", token_type: "bearer" });
      }),
      http.post("/api/auth/login", () => HttpResponse.json({ detail: "credenciales invalidas" }, { status: 401 })),
    );

    const err = await capturar(apiFetch("/auth/login", { method: "POST", body: { email: "a@b.c", password: "x" } }));

    expect(err.status).toBe(401);
    expect(refreshes).toBe(0);
    expect(expire).not.toHaveBeenCalled();
  });

  it("si el refresh falla por red no cierra la sesion", async () => {
    server.use(
      http.post("/api/auth/refresh", () => HttpResponse.error()),
      http.get("/api/a", () => HttpResponse.json({ detail: "no autenticado" }, { status: 401 })),
    );

    await capturar(apiFetch("/a"));

    expect(expire).not.toHaveBeenCalled();
  });
});
