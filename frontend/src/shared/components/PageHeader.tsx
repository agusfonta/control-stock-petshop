import type { ReactElement, ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  /** Acciones principales de la pantalla (botones); se alinean a la derecha desde `sm`. */
  actions?: ReactNode;
  className?: string;
}

/** Encabezado de pantalla: un unico `h1` por pagina (jerarquia accesible). */
export function PageHeader({ title, description, actions, className }: PageHeaderProps): ReactElement {
  return (
    <header className={cn("flex flex-col gap-3 pb-6 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0 space-y-1">
        <h1 className="truncate text-[1.75rem] leading-tight font-semibold tracking-tight">{title}</h1>
        {description !== undefined && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions !== undefined && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
