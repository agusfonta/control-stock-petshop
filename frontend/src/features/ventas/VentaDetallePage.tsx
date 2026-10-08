import { ArrowLeft, Printer, Receipt } from "lucide-react";
import { type ReactElement, type ReactNode, useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSession } from "@/features/auth/session";
import { ComprobantePrint } from "@/features/pos/ComprobantePrint";
import { METODO_LABEL, formatFechaHora, numeroCorto } from "@/features/pos/comprobanteFormat";
import { AnularVentaDialog } from "@/features/ventas/AnularVentaDialog";
import { EstadoVentaBadge } from "@/features/ventas/EstadoVentaBadge";
import { useClientePuntual, useClientesIndex, useVenta } from "@/features/ventas/api";
import { ApiError } from "@/shared/api/errors";
import type { Venta } from "@/shared/api/types";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { PageHeader } from "@/shared/components/PageHeader";
import { useCan } from "@/shared/lib/permissions";

function Dato({ etiqueta, children, className }: { etiqueta: string; children: ReactNode; className?: string }): ReactElement {
  return (
    <div className={className}>
      <dt className="text-xs font-medium text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="mt-0.5 text-sm">{children}</dd>
    </div>
  );
}

/** Nombre del cliente: indice cacheado (D12) y, si fue dado de baja, consulta puntual. */
function useNombreCliente(venta: Venta): string | null {
  const indice = useClientesIndex();
  const id = venta.cliente_id;
  const enIndice = id === null ? undefined : indice.data?.get(id);
  const puntual = useClientePuntual(id, indice.isSuccess && enIndice === undefined);
  return enIndice?.nombre ?? puntual.data?.nombre ?? null;
}

function TablaLineas({ venta }: { venta: Venta }): ReactElement {
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <Table aria-label="Productos de la venta">
        <TableHeader className="bg-muted/50">
          <TableRow className="hover:bg-transparent">
            <TableHead className="px-4">Producto</TableHead>
            <TableHead className="px-4 text-right">Cantidad</TableHead>
            <TableHead className="px-4 text-right">Precio</TableHead>
            <TableHead className="px-4 text-right">Subtotal</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {venta.lineas.map((l) => (
            <TableRow key={l.id} className="h-12">
              <TableCell className="px-4">{l.producto_nombre}</TableCell>
              <TableCell className="px-4 text-right tabular-nums">{l.cantidad}</TableCell>
              <TableCell className="px-4 text-right">
                <MoneyText value={l.precio_unit} />
              </TableCell>
              <TableCell className="px-4 text-right">
                <MoneyText value={l.subtotal} className="font-medium" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function TablaPagos({ venta }: { venta: Venta }): ReactElement {
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <Table aria-label="Pagos de la venta">
        <TableHeader className="bg-muted/50">
          <TableRow className="hover:bg-transparent">
            <TableHead className="px-4">Medio de pago</TableHead>
            <TableHead className="px-4 text-right">Monto</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {venta.pagos.map((p) => (
            <TableRow key={p.id} className="h-12">
              <TableCell className="px-4">{METODO_LABEL[p.metodo]}</TableCell>
              <TableCell className="px-4 text-right">
                <MoneyText value={p.monto} className="font-medium" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function Detalle({ venta }: { venta: Venta }): ReactElement {
  const me = useSession((s) => s.user);
  const puedeAnular = useCan("ventas.anular") && venta.estado === "confirmada";
  const [anulando, setAnulando] = useState(false);
  const nombreCliente = useNombreCliente(venta);

  return (
    <>
      <PageHeader
        title={`Venta ${numeroCorto(venta.id)}`}
        description={`Cobrada el ${formatFechaHora(venta.confirmada_at ?? venta.created_at)}`}
        actions={
          <>
            <Button asChild variant="ghost">
              <Link to="/ventas">
                <ArrowLeft aria-hidden="true" />
                Volver a ventas
              </Link>
            </Button>
            <Button type="button" variant="outline" onClick={() => window.print()}>
              <Printer aria-hidden="true" />
              Reimprimir comprobante
            </Button>
            {puedeAnular && (
              <Button type="button" variant="destructive" onClick={() => setAnulando(true)}>
                Anular venta
              </Button>
            )}
          </>
        }
      />

      <div className="space-y-4">
        <dl className="grid grid-cols-2 gap-4 rounded-xl border bg-card p-4 md:grid-cols-4">
          <Dato etiqueta="Estado">
            <EstadoVentaBadge estado={venta.estado} />
          </Dato>
          <Dato etiqueta="Vendedor">{venta.usuario_id === me?.id ? "Vos" : "Otro usuario"}</Dato>
          <Dato etiqueta="Cliente">
            {venta.cliente_id === null ? <span className="text-muted-foreground">Sin cliente</span> : (nombreCliente ?? "—")}
          </Dato>
          <Dato etiqueta="Total">
            <MoneyText value={venta.total} className="text-base font-semibold" />
          </Dato>
          {venta.anulada_at !== null && <Dato etiqueta="Anulada el">{formatFechaHora(venta.anulada_at)}</Dato>}
          {venta.motivo_anulacion !== null && (
            <Dato etiqueta="Motivo de anulación" className="col-span-2">
              {venta.motivo_anulacion}
            </Dato>
          )}
        </dl>
        <TablaLineas venta={venta} />
        <TablaPagos venta={venta} />
      </div>

      {puedeAnular && <AnularVentaDialog ventaId={venta.id} open={anulando} onOpenChange={setAnulando} />}
      <ComprobantePrint venta={venta} clienteNombre={nombreCliente} />
    </>
  );
}

/** Detalle de una venta: líneas, pagos, estado, reimpresión y (solo dueña) anulación. */
export function VentaDetallePage(): ReactElement {
  const { id = "" } = useParams();
  const venta = useVenta(id);

  if (venta.isPending) {
    return (
      <div className="space-y-4" aria-busy="true">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (venta.isError) {
    if (venta.error instanceof ApiError && venta.error.status === 404) {
      return (
        <EmptyState
          icon={Receipt}
          title="No encontramos esta venta"
          description="Puede que no exista o que no sea una de tus ventas."
          action={
            <Button asChild variant="outline">
              <Link to="/ventas">Volver a ventas</Link>
            </Button>
          }
        />
      );
    }
    return <ErrorState title="No pudimos cargar la venta" onRetry={() => void venta.refetch()} />;
  }
  return <Detalle venta={venta.data} />;
}
