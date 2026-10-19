import { Banknote, CreditCard, Landmark, type LucideIcon, X } from "lucide-react";
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { type PagoRow, centsToInput } from "@/features/pos/pagoRows";
import { MEDIOS_PAGO, type MedioPago, parseMontoInput, quickCashOptions } from "@/features/pos/payments";
import { formatARS } from "@/shared/lib/money";

const ICONOS: Record<MedioPago, LucideIcon> = { efectivo: Banknote, transferencia: Landmark, tarjeta: CreditCard };

interface PagoRowEditorProps {
  row: PagoRow;
  disabled: boolean;
  puedeQuitar: boolean;
  /** Medios que ya usan las otras filas: cada medio se usa una sola vez, asi que quedan deshabilitados. */
  mediosUsados: readonly MedioPago[];
  /** Lo que falta cobrar (centavos); si es > 0 se ofrece "Completar" en los medios que no son efectivo. */
  faltaCents: number;
  /** Efectivo a cobrar derivado (total - otros medios). Solo aplica a la fila de efectivo. */
  efectivoCents: number;
  /** Lo que escribio la persona en "Paga con" (solo aplica al efectivo). */
  pagaCon: string;
  /** Vuelto ya calculado por el formulario; 0 si no corresponde. */
  vueltoCents: number;
  onPagaConChange: (texto: string) => void;
  onChange: (patch: Partial<Omit<PagoRow, "id">>) => void;
  onCompletar: () => void;
  onQuitar: () => void;
}

/** Una fila del cobro: medio (botones grandes) + monto; el efectivo solo tiene "Paga con" (el monto se deriva). */
export function PagoRowEditor({
  row,
  disabled,
  puedeQuitar,
  mediosUsados,
  faltaCents,
  efectivoCents,
  pagaCon,
  vueltoCents,
  onPagaConChange,
  onChange,
  onCompletar,
  onQuitar,
}: PagoRowEditorProps): ReactElement {
  const label = MEDIOS_PAGO.find((m) => m.value === row.metodo)?.label ?? row.metodo;
  const esEfectivo = row.metodo === "efectivo";
  const montoCents = parseMontoInput(row.texto);
  const invalido = !esEfectivo && row.texto.trim() !== "" && montoCents === null;
  const pagaConCents = parseMontoInput(pagaCon);
  const botonQuitar = puedeQuitar ? (
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
  ) : null;
  return (
    <div data-pago-row className="space-y-2 rounded-xl border bg-card p-3">
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
            <ToggleGroupItem
              key={m.value}
              value={m.value}
              disabled={m.value !== row.metodo && mediosUsados.includes(m.value)}
              className="h-11 flex-1 gap-1.5 px-2 text-sm"
            >
              <Icono aria-hidden="true" className="size-4" />
              {m.label}
            </ToggleGroupItem>
          );
        })}
      </ToggleGroup>
      {esEfectivo ? (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Efectivo a cobrar{" "}
            <span className="font-semibold text-foreground tabular-nums">{formatARS(efectivoCents)}</span>
          </p>
          <label htmlFor="paga-con" className="text-sm font-medium">
            Paga con
          </label>
          <div className="flex items-center gap-2">
            <Input
              id="paga-con"
              data-paga-con
              type="text"
              inputMode="decimal"
              autoComplete="off"
              aria-label="Paga con"
              disabled={disabled}
              value={pagaCon}
              onChange={(e) => onPagaConChange(e.target.value)}
              onFocus={(e) => e.currentTarget.select()}
              placeholder={formatARS(efectivoCents)}
              className="h-12 flex-1 text-right text-lg font-semibold tabular-nums"
            />
            {botonQuitar}
          </div>
          <div className="flex flex-wrap gap-2">
            {quickCashOptions(efectivoCents).map((c) => (
              <Button
                key={c}
                type="button"
                variant="secondary"
                className="h-11 flex-1 tabular-nums"
                disabled={disabled}
                onClick={() => onPagaConChange(centsToInput(c))}
              >
                {formatARS(c)}
              </Button>
            ))}
          </div>
          {vueltoCents > 0 && (
            <div className="rounded-lg bg-success/10 px-3 py-2 text-success">
              <p className="text-sm font-medium">Vuelto</p>
              <p className="text-3xl font-bold tabular-nums">{formatARS(vueltoCents)}</p>
            </div>
          )}
          {pagaConCents !== null && pagaConCents < efectivoCents && (
            <p className="text-sm text-warning">Lo que recibís es menos que el efectivo a cobrar.</p>
          )}
        </div>
      ) : (
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
          {botonQuitar}
        </div>
      )}
      {invalido && <p className="text-sm text-destructive">Ingresá un monto con hasta dos decimales.</p>}
    </div>
  );
}
