import type { ReactElement, ReactNode } from "react";
import { NavLink } from "react-router";
import { PageHeader } from "@/shared/components/PageHeader";
import { type Permiso, useCan } from "@/shared/lib/permissions";
import { cn } from "@/shared/lib/utils";

interface SeccionReporte {
  to: string;
  label: string;
  permiso?: Permiso;
}

export const SECCIONES_REPORTES: SeccionReporte[] = [
  { to: "/reportes/ventas-dia", label: "Ventas del día" },
  { to: "/reportes/reposicion", label: "Reposición" },
  { to: "/reportes/mas-vendidos", label: "Más vendidos", permiso: "reportes.completos" },
  { to: "/reportes/margenes", label: "Márgenes", permiso: "reportes.completos" },
];

function SeccionLink({ seccion }: { seccion: SeccionReporte }): ReactElement | null {
  const permitido = useCan(seccion.permiso ?? "reportes.completos");
  if (seccion.permiso !== undefined && !permitido) return null;
  return (
    <NavLink
      to={seccion.to}
      className={({ isActive }) =>
        cn(
          "inline-flex h-10 shrink-0 items-center rounded-lg px-4 text-sm font-medium whitespace-nowrap transition-colors pointer-coarse:h-11",
          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )
      }
    >
      {seccion.label}
    </NavLink>
  );
}

interface ReportesLayoutProps {
  title: string;
  description: string;
  /** Controles de filtro de la seccion (fecha, periodo, orden...). */
  filtros?: ReactNode;
  children: ReactNode;
}

/** Marco comun de los reportes: encabezado, secciones segun el rol y filtros (UX7, UX11). */
export function ReportesLayout({ title, description, filtros, children }: ReportesLayoutProps): ReactElement {
  return (
    <div>
      <PageHeader title={title} description={description} className="pb-4" />
      <nav aria-label="Secciones de reportes" className="-mx-1 mb-5 flex gap-1 overflow-x-auto px-1 pb-1">
        {SECCIONES_REPORTES.map((s) => (
          <SeccionLink key={s.to} seccion={s} />
        ))}
      </nav>
      {filtros !== undefined && (
        <div className="mb-5 flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4">{filtros}</div>
      )}
      <div className="space-y-5">{children}</div>
    </div>
  );
}
