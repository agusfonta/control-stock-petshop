import { Banknote, CreditCard, Landmark, type LucideIcon, X } from "lucide-react";
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { PagoRow } from "@/features/pos/pagoRows";
import { MEDIOS_PAGO, type MedioPago, parseMontoInput } from "@/features/pos/payments";

const ICONOS: Record<MedioPago, LucideIcon> = { efectivo: Banknote, transferencia: Landmark, tarjeta: CreditCard };

interface PagoRowEditorProps {
  row: PagoRow;
  disabled: boolean;
  puedeQuitar: boolean;
  /** Lo que falta cobrar (centavos); si es > 0 se ofrece "Completar". */
  faltaCents: number;
  onChange: (patch: Partial<Omit<PagoRow, "id">>) => void;
  onCompletar: () => void;
  onQuitar: () => void;
}

/** Una fila del cobro: medio (botones grandes) + monto. */
export function PagoRowEditor({
  row,
  disabled,
  puedeQuitar,
  faltaCents,
  onChange,
  onCompletar,
  onQuitar,
}: PagoRowEditorProps): ReactElement {
  const label = MEDIOS_PAGO.find((m) => m.value === row.metodo)?.label ?? row.metodo;
  const invalido = row.texto.trim() !== "" && parseMontoInput(row.texto) === null;
  return (
    <div className="space-y-2 rounded-xl border bg-card p-3">
      <ToggleGroup
        type="single"
        variant="outline"
        value={row.metodo}
        disabled={disabled}
        aria-label="Medio de pago"
        className="w-full"
        onValueChange={(v) => {
          if (v !== "") onChange({ metodo: v as MedioPago });
        }}
      >
        {MEDIOS_PAGO.map((m) => {
          const Icono = ICONOS[m.value];
          return (
            <ToggleGroupItem key={m.value} value={m.value} className="h-11 flex-1 gap-1.5 px-2 text-sm">
              <Icono aria-hidden="true" className="size-4" />
              {m.label}
            </ToggleGroupItem>
          );
        })}
      </ToggleGroup>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <span aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground">
            $
          </span>
          <Input
            type="text"
            inputMode="decimal"
            autoComplete="off"
            aria-label={`Monto ${label.toLowerCase()}`}
            aria-invalid={invalido}
            disabled={disabled}
            value={row.texto}
            onChange={(e) => onChange({ texto: e.target.value })}
            onFocus={(e) => e.currentTarget.select()}
            className="h-12 pl-7 text-right text-lg font-semibold tabular-nums"
          />
        </div>
        {faltaCents > 0 && (
          <Button type="button" variant="outline" className="h-12" disabled={disabled} onClick={onCompletar}>
            Completar
          </Button>
        )}
        {puedeQuitar && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-12"
            disabled={disabled}
            aria-label={`Quitar pago ${label.toLowerCase()}`}
            onClick={onQuitar}
          >
            <X aria-hidden="true" />
          </Button>
        )}
      </div>
      {invalido && <p className="text-sm text-destructive">Ingresá un monto con hasta dos decimales.</p>}
    </div>
  );
}
