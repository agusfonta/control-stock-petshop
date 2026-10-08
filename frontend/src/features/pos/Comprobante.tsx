import type { ReactElement } from "react";
import { METODO_LABEL, formatFechaHora, numeroCorto } from "@/features/pos/comprobanteFormat";
import type { Venta } from "@/shared/api/types";
import { formatARS, toCents } from "@/shared/lib/money";
import { STORE_NAME } from "@/shared/lib/store";
import { cn } from "@/shared/lib/utils";

interface ComprobanteProps {
  venta: Venta;
  clienteNombre?: string | null;
  /** Solo en la venta recien cobrada (es informativo y no se guarda en el servidor). */
  vueltoCents?: number | null;
  className?: string;
}

function Fila({ etiqueta, children, fuerte = false }: { etiqueta: string; children: string; fuerte?: boolean }): ReactElement {
  return (
    <div className={cn("flex items-baseline justify-between gap-3", fuerte && "text-base font-bold")}>
      <span>{etiqueta}</span>
      <span className="tabular-nums">{children}</span>
    </div>
  );
}

/** Comprobante simple de venta (sin datos fiscales): se ve en pantalla y se imprime en 80 mm o A4 (D11). */
export function Comprobante({ venta, clienteNombre = null, vueltoCents = null, className }: ComprobanteProps): ReactElement {
  const fecha = venta.confirmada_at ?? venta.created_at;
  return (
    <article
      aria-label="Comprobante de venta"
      className={cn("comprobante w-full max-w-[80mm] space-y-3 bg-card font-mono text-[13px] leading-snug text-card-foreground", className)}
    >
      <header className="space-y-0.5 text-center">
        <h2 className="text-lg font-bold tracking-tight">{STORE_NAME}</h2>
        <p>Comprobante de venta</p>
        {venta.estado === "anulada" && <p className="font-bold">ANULADA</p>}
      </header>

      <div className="space-y-0.5 border-y border-dashed py-2">
        <Fila etiqueta="N°">{numeroCorto(venta.id)}</Fila>
        <Fila etiqueta="Fecha">{formatFechaHora(fecha)}</Fila>
        {clienteNombre !== null && <Fila etiqueta="Cliente">{clienteNombre}</Fila>}
      </div>

      <table aria-label="Productos" className="w-full">
        <tbody>
          {venta.lineas.map((l) => (
            <ItemFila key={l.id} nombre={l.producto_nombre} cantidad={l.cantidad} precio={toCents(l.precio_unit)} subtotal={toCents(l.subtotal)} />
          ))}
        </tbody>
      </table>

      <div className="space-y-0.5 border-t border-dashed pt-2">
        <Fila etiqueta="Total" fuerte>
          {formatARS(toCents(venta.total))}
        </Fila>
      </div>

      <div className="space-y-0.5 border-t border-dashed pt-2">
        {venta.pagos.map((p) => (
          <Fila key={p.id} etiqueta={METODO_LABEL[p.metodo]}>
            {formatARS(toCents(p.monto))}
          </Fila>
        ))}
        {vueltoCents !== null && vueltoCents > 0 && <Fila etiqueta="Vuelto">{formatARS(vueltoCents)}</Fila>}
      </div>

      <p className="border-t border-dashed pt-2 text-center text-xs">Comprobante no válido como factura</p>
    </article>
  );
}

function ItemFila(props: { nombre: string; cantidad: number; precio: number; subtotal: number }): ReactElement {
  return (
    <>
      <tr>
        <td colSpan={2} className="pt-1.5 font-semibold">
          {props.nombre}
        </td>
      </tr>
      <tr>
        <td className="tabular-nums">
          {props.cantidad} x {formatARS(props.precio)}
        </td>
        <td className="text-right tabular-nums">{formatARS(props.subtotal)}</td>
      </tr>
    </>
  );
}
