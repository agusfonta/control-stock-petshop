import type { ReactElement } from "react";
import { Badge } from "@/components/ui/badge";
import type { EstadoVenta } from "@/shared/api/types";

const ESTILO: Record<EstadoVenta, { label: string; className: string }> = {
  confirmada: { label: "Confirmada", className: "border-success/30 bg-success/10 text-success" },
  anulada: { label: "Anulada", className: "border-destructive/30 bg-destructive/10 text-destructive" },
  borrador: { label: "Borrador", className: "text-muted-foreground" },
};

/** Estado por color + texto (UX7). */
export function EstadoVentaBadge({ estado }: { estado: EstadoVenta }): ReactElement {
  const { label, className } = ESTILO[estado];
  return (
    <Badge variant="outline" className={className}>
      {label}
    </Badge>
  );
}
