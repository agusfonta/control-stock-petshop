import { ShoppingCart, Trash2, TriangleAlert } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { totalCents, unidadesTotales } from "@/features/pos/cart";
import { CartLineRow } from "@/features/pos/CartLineRow";
import { ClienteSelector } from "@/features/pos/ClienteSelector";
import { useCartStore } from "@/features/pos/useCartStore";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { formatARS } from "@/shared/lib/money";

interface CartPanelProps {
  seleccionada: string | null;
  onSelect: (productoId: string | null) => void;
  onAviso: (mensaje: string | null) => void;
  onCobrar: () => void;
}

/** Carrito fijo del POS: cliente opcional, lineas, total grande y "Cobrar" (UX2). */
export function CartPanel({ seleccionada, onSelect, onAviso, onCobrar }: CartPanelProps): ReactElement {
  const lineas = useCartStore((s) => s.lineas);
  const setQty = useCartStore((s) => s.setQty);
  const removeLine = useCartStore((s) => s.removeLine);
  const clear = useCartStore((s) => s.clear);
  const clamp = useCartStore((s) => s.clampToDisponible);
  const [confirmandoVaciar, setConfirmandoVaciar] = useState(false);

  const total = totalCents(lineas);
  const unidades = unidadesTotales(lineas);
  const hayFaltantes = lineas.some((l) => l.disponible !== undefined);

  return (
    <section aria-label="Carrito" className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-card">
      <header className="flex items-center justify-between gap-2 border-b px-4 py-3">
        <h2 className="text-base font-semibold">
          Carrito
          {unidades > 0 && <span className="ml-2 text-sm font-normal text-muted-foreground">{unidades} u.</span>}
        </h2>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={lineas.length === 0}
          onClick={() => setConfirmandoVaciar(true)}
        >
          <Trash2 aria-hidden="true" />
          Vaciar carrito
        </Button>
      </header>

      <div className="border-b p-3">
        <ClienteSelector />
      </div>

      {hayFaltantes && (
        <div role="alert" className="flex flex-wrap items-center gap-2 border-b bg-warning-soft px-4 py-2.5 text-sm text-warning">
          <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
          <span className="flex-1 font-medium">Algunos productos tienen menos stock del pedido.</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              onAviso(clamp());
            }}
          >
            Ajustar a disponible
          </Button>
        </div>
      )}

      {lineas.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-10 text-center">
          <ShoppingCart aria-hidden="true" className="size-8 text-muted-foreground/60" />
          <p className="text-sm font-medium">El carrito está vacío</p>
          <p className="text-sm text-muted-foreground">Escaneá un código o buscá un producto para empezar.</p>
        </div>
      ) : (
        <ul className="min-h-0 flex-1 divide-y overflow-y-auto">
          {lineas.map((linea) => (
            <CartLineRow
              key={linea.productoId}
              linea={linea}
              seleccionada={seleccionada === linea.productoId}
              onSelect={onSelect}
              onQty={(id, n) => {
                onSelect(id);
                onAviso(setQty(id, n));
              }}
              onRemove={(id) => {
                removeLine(id);
                if (seleccionada === id) onSelect(null);
              }}
            />
          ))}
        </ul>
      )}

      <footer className="space-y-3 border-t bg-card p-4">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm font-medium text-muted-foreground">Total</span>
          <output aria-live="polite" aria-label="Total a cobrar" className="text-4xl leading-none font-bold tracking-tight tabular-nums">
            {formatARS(total)}
          </output>
        </div>
        <Button
          type="button"
          size="lg"
          className="h-14 w-full text-lg font-semibold"
          disabled={lineas.length === 0 || hayFaltantes}
          onClick={onCobrar}
        >
          Cobrar
          <Kbd className="ml-1 bg-primary-foreground/20 text-primary-foreground">F9</Kbd>
        </Button>
      </footer>

      <ConfirmDialog
        open={confirmandoVaciar}
        onOpenChange={setConfirmandoVaciar}
        title="¿Vaciar el carrito?"
        description="Se quitan todos los productos y el cliente de esta venta."
        confirmLabel="Vaciar"
        destructive
        onConfirm={() => {
          clear();
          onSelect(null);
        }}
      />
    </section>
  );
}
