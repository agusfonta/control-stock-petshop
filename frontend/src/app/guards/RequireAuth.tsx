import type { ReactElement } from "react";
import { Navigate, Outlet, useLocation } from "react-router";
import { BootScreen } from "@/app/guards/BootScreen";
import { useSession } from "@/features/auth/session";

/** Exige sesion; si no hay, lleva a `/login?next=<ruta>` (con `expired=1` si vencio). */
export function RequireAuth(): ReactElement {
  const status = useSession((s) => s.status);
  const expired = useSession((s) => s.expired);
  const location = useLocation();

  if (status === "loading") return <BootScreen />;
  if (status === "anonymous") {
    const params = new URLSearchParams({ next: `${location.pathname}${location.search}` });
    if (expired) params.set("expired", "1");
    return <Navigate to={`/login?${params.toString()}`} replace />;
  }
  return <Outlet />;
}
