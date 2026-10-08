import type { ReactElement } from "react";
import { Badge } from "@/components/ui/badge";

interface StockBadgeProps {
  stockActual: number;
  stockMinimo: number;
}

/** Estado de stock por color + texto (UX7): rojo "Sin stock", ambar "Bajo mínimo", nada si esta bien. */
export function StockBadge({ stockActual, stockMinimo }: StockBadgeProps): ReactElement | null {
  if (stockActual <= 0) {
    return (
      <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-destructive">
        Sin stock
      </Badge>
    );
  }
  if (stockActual <= stockMinimo) {
    return (
      <Badge variant="outline" className="border-warning/30 bg-warning-soft text-warning">
        Bajo mínimo
      </Badge>
    );
  }
  return null;
}
