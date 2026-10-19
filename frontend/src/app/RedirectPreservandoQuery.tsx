import type { ReactElement } from "react";
import { Navigate, useLocation } from "react-router";

/** Redirige (con `replace`) a otra ruta conservando el query string y el hash de la URL original. */
export function RedirectPreservandoQuery({ to }: { to: string }): ReactElement {
  const { search, hash } = useLocation();
  return <Navigate to={{ pathname: to, search, hash }} replace />;
}
