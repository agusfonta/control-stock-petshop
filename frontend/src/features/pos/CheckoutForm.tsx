import { CircleAlert, Loader2, Plus } from "lucide-react";
import { type FormEvent, type ReactElement, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { cartSignature, totalCents } from "@/features/pos/cart";
import { PagoRowEditor } from "@/features/pos/PagoRowEditor";
import { type PagoRow, centsToInput, nuevoRowId, siguienteMedio } from "@/features/pos/pagoRows";
import {
  MEDIOS_PAGO,
  type PagoDraft,
  canConfirm,
  parseMontoInput,
  remainingCents,
  vueltoCents,
} from "@/features/pos/payments";
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

/** Un pago por medio: no hay mas filas que medios. */
const MAX_FILAS = MEDIOS_PAGO.length;

/**
 * Los montos que se envian. Los medios que no son efectivo salen de lo tipeado; el efectivo NO se tipea:
 * es lo que resta del total (nunca negativo), asi la suma cuadra y "Paga con" solo sirve para el vuelto.
 */
function filasADrafts(rows: readonly PagoRow[], total: number): PagoDraft[] {
  const otros = rows.reduce((acc, r) => (r.metodo === "efectivo" ? acc : acc + (parseMontoInput(r.texto) ?? 0)), 0);
  const efectivo = Math.max(0, total - otros);
  return rows.map((r) => ({
    id: r.id,
    metodo: r.metodo,
    montoCents: r.metodo === "efectivo" ? efectivo : (parseMontoInput(r.texto) ?? 0),
  }));
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

  const drafts = filasADrafts(rows, total);
  const falta = remainingCents(total, drafts);
  const puedeConfirmar = canConfirm(total, drafts);
  const hayEfectivo = rows.some((r) => r.metodo === "efectivo");
  const efectivoCents = drafts.find((d) => d.metodo === "efectivo")?.montoCents ?? 0;
  const pagaConCents = parseMontoInput(pagaCon);
  // Vuelto (informativo): solo sobre el efectivo y solo si la persona informo con cuanto paga.
  const vuelto = pagaConCents === null ? 0 : vueltoCents(pagaConCents, efectivoCents);

  function editar(id: string, patch: Partial<Omit<PagoRow, "id">>): void {
    setError(null);
    let cambios = patch;
    if (patch.metodo !== undefined && rows.find((r) => r.id === id)?.metodo === "efectivo") {
      // Al dejar de ser efectivo, "Paga con" se descarta y el medio nuevo hereda el monto derivado.
      setPagaCon("");
      cambios = { ...patch, texto: efectivoCents > 0 ? centsToInput(efectivoCents) : "" };
    }
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...cambios } : r)));
  }

  function quitar(id: string): void {
    if (rows.find((r) => r.id === id)?.metodo === "efectivo") setPagaCon("");
    setRows((prev) => prev.filter((r) => r.id !== id));
  }

  function agregarMedio(): void {
    // Con efectivo en juego: lo que "Paga con" no cubre del total (vacio si no esta informado o ya cubre todo).
    // Sin efectivo: lo que falta.
    const restante = hayEfectivo ? (pagaConCents === null ? 0 : total - pagaConCents) : falta;
    const sugerido = restante > 0 ? centsToInput(restante) : "";
    setRows((prev) => [...prev, { id: nuevoRowId(), metodo: siguienteMedio(prev), texto: sugerido }]);
  }

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (!puedeConfirmar || enviando) return;
    const res = await cobrar(drafts, { reintento });
    if (res === null) return;
    if (res.tipo === "ok") {
      const conVuelto = vuelto > 0 ? vuelto : null;
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
            mediosUsados={rows.filter((r) => r.id !== row.id).map((r) => r.metodo)}
            faltaCents={falta}
            efectivoCents={efectivoCents}
            pagaCon={pagaCon}
            vueltoCents={vuelto}
            onPagaConChange={setPagaCon}
            onChange={(patch) => editar(row.id, patch)}
            onCompletar={() => editar(row.id, { texto: centsToInput((parseMontoInput(row.texto) ?? 0) + falta) })}
            onQuitar={() => quitar(row.id)}
          />
        ))}

        <Button
          type="button"
          variant="outline"
          className="h-11 w-full"
          disabled={rows.length >= MAX_FILAS || enviando || reintento}
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
