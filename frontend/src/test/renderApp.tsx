import { http, HttpResponse } from "msw";
import { AppRoutes } from "@/app/router";
import { useSession } from "@/features/auth/session";
import type { Me } from "@/shared/api/types";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

interface RenderAppOptions {
  route?: string;
  /** Usuario con sesion iniciada; `null` = anonimo; `"loading"` = arranque sin resolver (corre `init`). */
  user?: Me | null | "loading";
  /** Cantidad de productos bajo minimo que devuelve `GET /api/stock/alertas`. */
  alertas?: number;
}

/** Renderiza el arbol de rutas real con la sesion precargada (sin pasar por el login). */
export function renderApp({ route = "/", user = null, alertas = 0 }: RenderAppOptions = {}) {
  server.use(
    http.get("/api/stock/alertas", () => HttpResponse.json({ total_bajo_minimo: alertas, items: [] })),
  );
  if (user === "loading") {
    useSession.setState({ status: "loading", accessToken: null, user: null, expired: false });
  } else if (user === null) {
    useSession.setState({ status: "anonymous", accessToken: null, user: null, expired: false });
  } else {
    useSession.setState({ status: "authenticated", accessToken: "tok-test", user, expired: false });
  }
  return renderWithProviders(<AppRoutes />, { route });
}
