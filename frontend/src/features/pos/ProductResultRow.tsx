import { Plus } from "lucide-react";
import type { ReactElement } from "react";
import { Badge } from "@/components/ui/badge";
import type { Producto } from "@/shared/api/types";
import { formatARS, toCents } from "@/shared/lib/money";
import { cn } from "@/shared/lib/utils";

interface ProductResultRowProps {
  producto: Producto;
  /** Unidades de este producto que ya estan en el carrito (0 si no esta). */
  enCarrito: number;
  onAdd: (producto: Producto) => void;
}

function EstadoStock({ producto }: { producto: Producto }): ReactElement {
  if (producto.stock_actual <= 0) return <Badge variant="destructive">Sin stock</Badge>;
  if (producto.stock_actual <= producto.stock_minimo) {
    return (
      <Badge variant="outline" className="border-warning/40 bg-warning-soft text-warning">
        Quedan {producto.stock_actual}
      </Badge>
    );
  }
  return <span className="text-xs text-muted-foreground">Stock {producto.stock_actual}</span>;
}

/** Resultado de busqueda como fila tactil: nombre, SKU, stock y precio (UX2). */
export function ProductResultRow({ producto, enCarrito, onAdd }: ProductResultRowProps): ReactElement {
  const sinStock = producto.stock_actual <= 0;
  return (
    <button
      type="button"
      data-result
      disabled={sinStock}
      onClick={() => onAdd(producto)}
      className={cn(
        "flex min-h-[4.5rem] w-full items-center gap-3 rounded-lg border bg-card px-4 py-2.5 text-left transition-colors outline-none",
        "hover:bg-accent/60 focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
        "disabled:cursor-not-allowed disabled:bg-muted/50 disabled:opacity-60 disabled:hover:bg-muted/50",
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 block text-base leading-snug font-medium break-words">{producto.nombre}</span>
        <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
          <span className="font-mono text-xs">{producto.sku}</span>
          <EstadoStock producto={producto} />
          {enCarrito > 0 && <Badge variant="secondary">En carrito: {enCarrito}</Badge>}
        </span>
      </span>
      <span className="text-lg font-semibold whitespace-nowrap tabular-nums">
        {formatARS(toCents(producto.precio_venta))}
      </span>
      <span
        aria-hidden="true"
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary",
          sinStock && "bg-transparent text-transparent",
        )}
      >
        <Plus className="size-5" />
      </span>
    </button>
  );
}
