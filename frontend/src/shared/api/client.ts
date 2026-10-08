import { ApiError, parseApiError } from "@/shared/api/errors";

/** Puente hacia el store de sesion: evita una dependencia circular client <-> session. */
export interface AuthBridge {
  getAccessToken: () => string | null;
  setAccessToken: (token: string) => void;
  /** Sesion vencida: limpia el estado y lleva a `/login`. Debe ser idempotente. */
  expire: () => void;
}

type QueryValue = string | number | boolean | null | undefined;

export interface ApiOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, QueryValue>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

interface TokenResponse {
  access_token: string;
}

const SIN_REFRESH = new Set(["/auth/login", "/auth/refresh"]);

let bridge: AuthBridge = {
  getAccessToken: () => null,
  setAccessToken: () => undefined,
  expire: () => undefined,
};
let refreshEnCurso: Promise<string> | null = null;
let expiracionManejada = new WeakSet<Promise<string>>();

export function configureAuth(next: AuthBridge): void {
  bridge = next;
}

/** Descarta el refresh en vuelo (uso exclusivo de tests y de `logout`). */
export function resetRefreshState(): void {
  refreshEnCurso = null;
  expiracionManejada = new WeakSet<Promise<string>>();
}

function baseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return base !== undefined && base !== "" ? base.replace(/\/$/, "") : "/api";
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = new URL(`${baseUrl()}${path}`, window.location.origin);
  for (const [clave, valor] of Object.entries(query ?? {})) {
    if (valor !== undefined && valor !== null) url.searchParams.set(clave, String(valor));
  }
  return url.toString();
}

async function readBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (text === "") return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

async function request<T>(path: string, options: ApiOptions, token: string | null): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (token !== null) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "include",
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw parseApiError(0, null);
  }

  if (res.status === 204) return undefined as T;
  const body = await readBody(res);
  if (!res.ok) throw parseApiError(res.status, body);
  return body as T;
}

async function pedirRefresh(): Promise<string> {
  const data = await request<TokenResponse>("/auth/refresh", { method: "POST" }, null);
  bridge.setAccessToken(data.access_token);
  return data.access_token;
}

/**
 * Renueva el access token con la cookie de refresh. Una unica promesa en vuelo
 * se comparte entre todas las solicitudes concurrentes (D3).
 */
export function refreshSession(): Promise<string> {
  if (refreshEnCurso === null) {
    const promesa = pedirRefresh().finally(() => {
      if (refreshEnCurso === promesa) refreshEnCurso = null;
    });
    refreshEnCurso = promesa;
  }
  return refreshEnCurso;
}

async function reintentarTrasRefresh<T>(path: string, options: ApiOptions, original: ApiError): Promise<T> {
  const promesa = refreshSession();
  let nuevoToken: string;
  try {
    nuevoToken = await promesa;
  } catch (error) {
    // Solo un rechazo explicito del servidor cierra la sesion; un corte de red no.
    if (error instanceof ApiError && error.status === 401 && !expiracionManejada.has(promesa)) {
      expiracionManejada.add(promesa);
      bridge.expire();
    }
    throw original;
  }
  return request<T>(path, options, nuevoToken);
}

/** Cliente HTTP tipado: Bearer, JSON in/out, 204 -> undefined y refresh transparente ante 401. */
export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  try {
    return await request<T>(path, options, bridge.getAccessToken());
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401 || SIN_REFRESH.has(path)) throw error;
    return reintentarTrasRefresh<T>(path, options, error);
  }
}
