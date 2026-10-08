import { useSession } from "@/features/auth/session";
import type { Rol } from "@/shared/api/types";

/**
 * Mapa unico de permisos, espejo de la matriz RBAC (spec `auth-rbac`, D5).
 * El servidor sigue siendo la autoridad: un 403 se muestra como aviso, sin cerrar sesion.
 */
export type Permiso =
  | "productos.editar"
  | "stock.ajustar"
  | "ventas.anular"
  | "clientes.editar"
  | "distribuidoras.editar"
  | "compras.cancelar"
  | "compras.pagos"
  | "reportes.completos";

export const PERMISOS: Record<Permiso, readonly Rol[]> = {
  "productos.editar": ["duena"],
  "stock.ajustar": ["duena"],
  "ventas.anular": ["duena"],
  "clientes.editar": ["duena"],
  "distribuidoras.editar": ["duena"],
  "compras.cancelar": ["duena"],
  "compras.pagos": ["duena"],
  "reportes.completos": ["duena"],
};

/** `true` si el rol tiene el permiso; sin rol (anonimo) nunca. */
export function can(rol: Rol | null | undefined, permiso: Permiso): boolean {
  return rol !== null && rol !== undefined && PERMISOS[permiso].includes(rol);
}

/** Hook reactivo: `useCan("ventas.anular")`. */
export function useCan(permiso: Permiso): boolean {
  return useSession((s) => can(s.user?.rol, permiso));
}

/** Nombre visible de cada rol (navegacion, encabezados). */
export const ROL_LABEL: Record<Rol, string> = {
  duena: "Dueña",
  mostrador: "Mostrador",
};
