import { create } from "zustand";
import { apiFetch, configureAuth, refreshSession } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { queryClient } from "@/shared/api/queryClient";
import type { LoginRequest, Me, TokenResponse } from "@/shared/api/types";

/** Pista de sesion (D4): sin endpoint de logout, evita restaurar una sesion cerrada. */
export const PISTA_SESION = "animall.session";

type SessionStatus = "loading" | "authenticated" | "anonymous";

interface SessionState {
  status: SessionStatus;
  /** Solo en memoria: nunca se persiste. */
  accessToken: string | null;
  user: Me | null;
  /** `true` si la sesion se cerro por vencimiento (aviso "Tu sesión expiró"). */
  expired: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  expire: () => void;
  setAccess: (token: string) => void;
  init: () => Promise<void>;
}

// localStorage siempre en try/catch: modo privado o datos bloqueados.
function leerPista(): boolean {
  try {
    return window.localStorage.getItem(PISTA_SESION) === "1";
  } catch {
    return false;
  }
}
function escribirPista(): void {
  try {
    window.localStorage.setItem(PISTA_SESION, "1");
  } catch {
    // Sin persistencia: la sesion vive hasta recargar.
  }
}
function borrarPista(): void {
  try {
    window.localStorage.removeItem(PISTA_SESION);
  } catch {
    // Nada que borrar.
  }
}

const limpiezas = new Set<() => void>();

/** Registra una limpieza que corre al cerrar/expirar la sesion (ej. vaciar el carrito). Devuelve la baja. */
export function registerLogoutCleanup(cleanup: () => void): () => void {
  limpiezas.add(cleanup);
  return () => {
    limpiezas.delete(cleanup);
  };
}

function limpiarDatosDeSesion(): void {
  queryClient.clear();
  for (const limpiar of limpiezas) limpiar();
}

let initEnCurso: Promise<void> | null = null;

export const useSession = create<SessionState>()((set, get) => ({
  status: "loading",
  accessToken: null,
  user: null,
  expired: false,

  async login(credentials) {
    const token = await apiFetch<TokenResponse>("/auth/login", { method: "POST", body: credentials });
    set({ accessToken: token.access_token });
    try {
      const user = await apiFetch<Me>("/auth/me");
      escribirPista();
      set({ status: "authenticated", user, expired: false });
    } catch (error) {
      set({ accessToken: null, user: null });
      throw error;
    }
  },

  logout() {
    borrarPista();
    set({ status: "anonymous", accessToken: null, user: null, expired: false });
    limpiarDatosDeSesion();
  },

  expire() {
    if (get().status === "anonymous" && get().expired) return;
    borrarPista();
    set({ status: "anonymous", accessToken: null, user: null, expired: true });
    limpiarDatosDeSesion();
  },

  setAccess(token) {
    set({ accessToken: token });
  },

  init() {
    if (initEnCurso !== null) return initEnCurso;
    initEnCurso = restaurarSesion().finally(() => {
      initEnCurso = null;
    });
    return initEnCurso;
  },
}));

async function restaurarSesion(): Promise<void> {
  if (!leerPista()) {
    useSession.setState({ status: "anonymous", accessToken: null, user: null });
    return;
  }
  try {
    await refreshSession();
    const user = await apiFetch<Me>("/auth/me");
    useSession.setState({ status: "authenticated", user, expired: false });
  } catch (error) {
    // Rechazo del servidor: la cookie ya no sirve. Corte de red: se conserva la pista.
    if (error instanceof ApiError && error.status === 401) borrarPista();
    useSession.setState({ status: "anonymous", accessToken: null, user: null });
  }
}

configureAuth({
  getAccessToken: () => useSession.getState().accessToken,
  setAccessToken: (token) => useSession.getState().setAccess(token),
  expire: () => useSession.getState().expire(),
});
