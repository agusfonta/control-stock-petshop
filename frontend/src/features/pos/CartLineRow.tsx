import { Trash2, TriangleAlert } from "lucide-react";
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { type CartLine, lineSubtotalCents } from "@/features/pos/cart";
import { QtyStepper } from "@/features/pos/QtyStepper";
import { formatARS } from "@/shared/lib/money";
import { cn } from "@/shared/lib/utils";

interface CartLineRowProps {
  linea: CartLine;
  seleccionada: boolean;
  onSelect: (productoId: string) => void;
  onQty: (productoId: string, cantidad: number) => void;
  onRemove: (productoId: string) => void;
}

/** Linea compacta del carrito: nombre, precio x cantidad, stepper, subtotal y quitar. */
export function CartLineRow({ linea, seleccionada, onSelect, onQty, onRemove }: CartLineRowProps): ReactElement {
  return (
    <li
      aria-current={seleccionada ? "true" : undefined}
      onClick={() => onSelect(linea.productoId)}
      className={cn(
        "space-y-2 px-4 py-3 transition-colors",
        seleccionada && "bg-accent/50",
        linea.disponible !== undefined && "bg-warning-soft",
      )}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm leading-snug font-medium">{linea.nombre}</p>
          <p className="text-xs text-muted-foreground">
            <span className="tabular-nums">{formatARS(linea.precioCents)}</span> c/u · {linea.sku}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="-mt-1 -mr-2 text-muted-foreground hover:text-destructive"
          aria-label={`Quitar ${linea.nombre}`}
          onClick={() => onRemove(linea.productoId)}
        >
          <Trash2 aria-hidden="true" />
        </Button>
      </div>
      <div className="flex items-center justify-between gap-2">
        <QtyStepper nombre={linea.nombre} cantidad={linea.cantidad} onChange={(n) => onQty(linea.productoId, n)} />
        <span className="text-base font-semibold whitespace-nowrap tabular-nums">{formatARS(lineSubtotalCents(linea))}</span>
      </div>
      {linea.disponible !== undefined && (
        <p className="flex items-center gap-1.5 text-xs font-medium text-warning" role="status">
          <TriangleAlert aria-hidden="true" className="size-3.5" />
          Disponible: {linea.disponible}
        </p>
      )}
    </li>
  );
}
