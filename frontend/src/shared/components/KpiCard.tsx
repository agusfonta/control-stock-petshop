import type { LucideIcon } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/shared/lib/utils";

interface KpiCardProps {
  label: string;
  /** Valor ya formateado (usar `MoneyText` para importes). */
  value: ReactNode;
  hint?: string;
  icon?: LucideIcon;
  className?: string;
}

/** Tarjeta de indicador: etiqueta chica, valor grande, sin sombra (borde, UX8). */
export function KpiCard({ label, value, hint, icon: Icon, className }: KpiCardProps): ReactElement {
  return (
    <Card className={cn("gap-0 py-0 shadow-none", className)}>
      <CardContent className="flex items-start justify-between gap-3 p-5">
        <div className="min-w-0 space-y-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-[1.75rem] leading-tight font-semibold tracking-tight tabular-nums">{value}</p>
          {hint !== undefined && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
        {Icon !== undefined && (
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <Icon className="size-5" aria-hidden="true" />
          </span>
        )}
      </CardContent>
    </Card>
  );
}
