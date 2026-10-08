import { CircleAlert, Loader2, Plus } from "lucide-react";
import { type FormEvent, type ReactElement, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { cartSignature, totalCents } from "@/features/pos/cart";
import { PagoRowEditor } from "@/features/pos/PagoRowEditor";
import { type PagoRow, centsToInput, nuevoRowId, rowsToDrafts, siguienteMedio } from "@/features/pos/pagoRows";
import { MAX_PAGOS, canConfirm, parseMontoInput, quickCashOptions, remainingCents, vueltoCents } from "@/features/pos/payments";
import { useCartStore } from "@/features/pos/useCartStore";
import { useCheckout } from "@/features/pos/useCheckout";
import type { Venta } from "@/shared/api/types";
import { formatARS, toCents } from "@/shared/lib/money";
import { notifyError, notifyInfo, notifySuccess } from "@/shared/lib/toast";

interface CheckoutFormProps {
  onCerrar: () => void;
  onSuccess: (venta: Venta, vueltoCents: number | null, clienteNombre: string | null) => void;
}

function filaEfectivo(cents: number): PagoRow {
  return { id: nuevoRowId(), metodo: "efectivo", texto: centsToInput(cents) };
}

/** Si quedo un cobro a medias con el mismo carrito (corte de red), se restaura para reintentarlo igual. */
function estadoInicial(): { rows: PagoRow[]; reintento: boolean } {
  const { lineas, cliente, checkout } = useCartStore.getState();
  const firma = cartSignature(lineas, cliente?.id ?? null);
  if (checkout !== null && checkout.signature === firma && checkout.ventaId !== undefined && checkout.pagos !== undefined) {
    const rows = checkout.pagos.map((p) => ({
      id: nuevoRowId(),
      metodo: p.metodo === "mp" ? ("tarjeta" as const) : p.metodo,
      texto: centsToInput(toCents(p.monto)),
    }));
    return { rows, reintento: true };
  }
  return { rows: [filaEfectivo(totalCents(lineas))], reintento: false };
}

export function CheckoutForm({ onCerrar, onSuccess }: CheckoutFormProps): ReactElement {
  // El total se congela al abrir (el carrito se vacia al cobrar, antes de que termine la animacion de cierre).
  const [total, setTotal] = useState(() => totalCents(useCartStore.getState().lineas));
  const [inicial] = useState(estadoInicial);
  const [rows, setRows] = useState<PagoRow[]>(inicial.rows);
  const [reintento, setReintento] = useState(inicial.reintento);
  const [pagaCon, setPagaCon] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { enviando, cobrar } = useCheckout();

  const drafts = rowsToDrafts(rows);
  const falta = remainingCents(total, drafts);
  const puedeConfirmar = canConfirm(total, drafts);
  const efectivo = drafts.filter((d) => d.metodo === "efectivo").reduce((acc, d) => acc + d.montoCents, 0);
  const hayEfectivo = rows.some((r) => r.metodo === "efectivo");
  const pagaConCents = parseMontoInput(pagaCon);
  const vuelto = pagaConCents === null ? 0 : vueltoCents(pagaConCents, efectivo);

  function editar(id: string, patch: Partial<Omit<PagoRow, "id">>): void {
    setError(null);
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function agregarMedio(): void {
    setRows((prev) => [
      ...prev,
      { id: nuevoRowId(), metodo: siguienteMedio(prev), texto: falta > 0 ? centsToInput(falta) : "" },
    ]);
  }

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (!puedeConfirmar || enviando) return;
    const res = await cobrar(drafts, { reintento });
    if (res === null) return;
    if (res.tipo === "ok") {
      const conVuelto = pagaConCents !== null && vuelto > 0 ? vuelto : null;
      const clienteNombre = useCartStore.getState().cliente?.nombre ?? null;
      useCartStore.getState().clear();
      notifySuccess("Venta registrada");
      onSuccess(res.venta, conVuelto, clienteNombre);
      onCerrar();
    } else if (res.tipo === "precio-cambio") {
      setTotal(res.totalCents);
      setRows([filaEfectivo(res.totalCents)]);
      setPagaCon("");
      setError(null);
      notifyInfo("El precio cambió. Revisá el total y confirmá de nuevo.");
    } else if (res.tipo === "faltantes") {
      notifyError("Hay productos con menos stock del pedido. Ajustá las cantidades en el carrito.");
      onCerrar();
    } else {
      setError(res.refrescar ? `${res.mensaje}. Actualizamos los datos: revisá el carrito.` : res.mensaje);
      setReintento(res.reintentable);
    }
  }

  return (
    <form onSubmit={(e) => void enviar(e)} className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 pb-4">
        <div className="rounded-xl bg-accent px-4 py-3 text-accent-foreground" aria-live="polite">
          <p className="text-sm font-medium">Total a cobrar</p>
          <p className="text-4xl leading-tight font-bold tabular-nums">{formatARS(total)}</p>
        </div>

        {rows.map((row) => (
          <PagoRowEditor
            key={row.id}
            row={row}
            disabled={enviando || reintento}
            puedeQuitar={rows.length > 1}
            faltaCents={falta}
            onChange={(patch) => editar(row.id, patch)}
            onCompletar={() => editar(row.id, { texto: centsToInput((parseMontoInput(row.texto) ?? 0) + falta) })}
            onQuitar={() => setRows((prev) => prev.filter((r) => r.id !== row.id))}
          />
        ))}

        <Button
          type="button"
          variant="outline"
          className="h-11 w-full"
          disabled={rows.length >= MAX_PAGOS || enviando || reintento}
          onClick={agregarMedio}
        >
          <Plus aria-hidden="true" />
          Agregar otro medio
        </Button>

        <p
          aria-live="polite"
          className={falta === 0 ? "text-sm font-medium text-success" : "text-base font-semibold text-warning"}
        >
          {falta > 0 && (
            <>
              Faltan <span className="tabular-nums">{formatARS(falta)}</span>
            </>
          )}
          {falta < 0 && (
            <>
              Sobran <span className="tabular-nums">{formatARS(-falta)}</span>
            </>
          )}
          {falta === 0 && "El pago cubre el total"}
        </p>

        {hayEfectivo && efectivo > 0 && (
          <div className="space-y-2 rounded-xl border bg-card p-3">
            <label htmlFor="paga-con" className="text-sm font-medium">
              Paga con
            </label>
            <Input
              id="paga-con"
              type="text"
              inputMode="decimal"
              autoComplete="off"
              disabled={enviando || reintento}
              value={pagaCon}
              onChange={(e) => setPagaCon(e.target.value)}
              placeholder={formatARS(efectivo)}
              className="h-12 text-right text-lg font-semibold tabular-nums"
            />
            <div className="flex flex-wrap gap-2">
              {quickCashOptions(efectivo).map((c) => (
                <Button
                  key={c}
                  type="button"
                  variant="secondary"
                  className="h-11 flex-1 tabular-nums"
                  disabled={enviando || reintento}
                  onClick={() => setPagaCon(centsToInput(c))}
                >
                  {formatARS(c)}
                </Button>
              ))}
            </div>
            {pagaConCents !== null && vuelto > 0 && (
              <div className="rounded-lg bg-success/10 px-3 py-2 text-success">
                <p className="text-sm font-medium">Vuelto</p>
                <p className="text-3xl font-bold tabular-nums">{formatARS(vuelto)}</p>
              </div>
            )}
            {pagaConCents !== null && pagaConCents < efectivo && (
              <p className="text-sm text-warning">Lo que recibís es menos que el efectivo a cobrar.</p>
            )}
          </div>
        )}

        {error !== null && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden="true" />
            <AlertDescription>
              <p>{error}</p>
              {reintento && <p>Si reintentás no se duplica la venta.</p>}
            </AlertDescription>
          </Alert>
        )}
      </div>

      <div className="border-t bg-card p-4">
        <Button type="submit" size="lg" className="h-14 w-full text-lg" disabled={!puedeConfirmar || enviando}>
          {enviando ? <Loader2 aria-hidden="true" className="animate-spin" /> : null}
          {reintento && error !== null ? "Reintentar" : "Confirmar venta"}
          <Kbd className="ml-2 bg-primary-foreground/20 text-primary-foreground">Enter</Kbd>
        </Button>
      </div>
    </form>
  );
}
