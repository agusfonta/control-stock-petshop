import type { ReactElement } from "react";
import { Badge } from "@/components/ui/badge";
import { ESTADO_PEDIDO_LABEL } from "@/features/compras/format";
import type { EstadoPedido } from "@/shared/api/types";

const ESTILO: Record<EstadoPedido, string> = {
  pendiente: "border-warning/30 bg-warning-soft text-warning",
  recibido: "border-primary/25 bg-primary/10 text-primary",
  cancelado: "border-border bg-muted text-muted-foreground",
};

/** Estado del pedido por color + texto (nunca solo color, UX7). */
export function EstadoPedidoBadge({ estado }: { estado: EstadoPedido }): ReactElement {
  return (
    <Badge variant="outline" className={ESTILO[estado]}>
      {ESTADO_PEDIDO_LABEL[estado]}
    </Badge>
  );
}
