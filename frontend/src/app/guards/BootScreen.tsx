import type { ReactElement } from "react";
import { Spinner } from "@/components/ui/spinner";

/** Carga a pantalla completa mientras se restaura la sesion (refresh + me). */
export function BootScreen(): ReactElement {
  return (
    <div
      role="status"
      aria-label="Cargando"
      className="flex min-h-svh flex-col items-center justify-center gap-4 bg-background"
    >
      <img src="/logo.png" alt="" width={96} height={96} className="size-24 rounded-2xl" />
      <Spinner className="size-5 text-primary" aria-hidden="true" />
      <span className="sr-only">Cargando…</span>
    </div>
  );
}
