import type { ReactElement } from "react";
import { Outlet } from "react-router";
import { Forbidden } from "@/app/guards/Forbidden";
import { type Permiso, useCan } from "@/shared/lib/permissions";

interface RequireRoleProps {
  /** Permiso del mapa unico (`PERMISOS`) que habilita la ruta. */
  permiso: Permiso;
}

/** Layout de ruta: renderiza las rutas hijas solo si el rol tiene el permiso; si no, "Sin permiso". */
export function RequireRole({ permiso }: RequireRoleProps): ReactElement {
  const allowed = useCan(permiso);
  return allowed ? <Outlet /> : <Forbidden />;
}
