import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, PackageCheck, XCircle } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EstadoPedidoBadge } from "@/features/compras/EstadoPedidoBadge";
import { useCancelarPedido, usePedido, useRecibirPedido } from "@/features/compras/api";
import { formatFecha, formatFechaHora } from "@/features/compras/format";
import { useDistribuidora, useProductosIndex } from "@/features/distribuidoras/api";
import { ApiError } from "@/shared/api/errors";
import { queryKeys } from "@/shared/api/queryKeys";
import type { LineaPedido } from "@/shared/api/types";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { PageHeader } from "@/shared/components/PageHeader";
import { useCan } from "@/shared/lib/permissions";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

type Accion = "recibir" | "cancelar";

/** Detalle del pedido: líneas, total estimado y acciones (recibir ambos roles, cancelar solo dueña). */
export function PedidoDetallePage(): ReactElement {
  const { id = "" } = useParams();
  const puedeCancelar = useCan("compras.cancelar");
  const qc = useQueryClient();
  const pedido = usePedido(id);
  const distribuidora = useDistribuidora(pedido.data?.distribuidora_id ?? "");
  const productos = useProductosIndex();
  const recibir = useRecibirPedido();
  const cancelar = useCancelarPedido();
  const [accion, setAccion] = useState<Accion | null>(null);

  async function ejecutar(cual: Accion): Promise<void> {
    setAccion(null);
    try {
      if (cual === "recibir") {
        await recibir.mutateAsync(id);
        notifySuccess("Pedido recibido, stock actualizado");
      } else {
        await cancelar.mutateAsync(id);
        notifySuccess("Pedido cancelado");
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        notifyError("El pedido ya no está pendiente");
        await qc.invalidateQueries({ queryKey: queryKeys.pedidos.all });
      } else {
        notifyError(
          error instanceof ApiError
            ? error.message
            : cual === "recibir"
              ? "No pudimos recibir el pedido"
              : "No pudimos cancelar el pedido",
        );
      }
    }
  }

  const volver = (
    <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
      <Link to="/compras">
        <ArrowLeft aria-hidden="true" /> Pedidos
      </Link>
    </Button>
  );

  if (pedido.isLoading) {
    return (
      <>
        {volver}
        <Skeleton className="h-24 w-full rounded-xl" />
      </>
    );
  }
  if (pedido.isError || pedido.data === undefined) {
    const noExiste = pedido.error instanceof ApiError && pedido.error.status === 404;
    return (
      <>
        {volver}
        <ErrorState
          title={noExiste ? "No encontramos ese pedido" : "No pudimos cargar el pedido"}
          description={noExiste ? "Revisá el listado de pedidos." : undefined}
          onRetry={noExiste ? undefined : () => void pedido.refetch()}
        />
      </>
    );
  }

  const p = pedido.data;
  const pendiente = p.estado === "pendiente";
  const ocupado = recibir.isPending || cancelar.isPending;
  const nombreDe = (productoId: string): string => productos.data?.get(productoId)?.nombre ?? "—";

  const columnas: DataTableColumn<LineaPedido>[] = [
    {
      id: "producto",
      header: "Producto",
      cell: (l) => (
        <span className="block min-w-0">
          <span className="block truncate font-medium">{nombreDe(l.producto_id)}</span>
          <span className="block text-xs text-muted-foreground">{productos.data?.get(l.producto_id)?.sku ?? ""}</span>
        </span>
      ),
    },
    { id: "cantidad", header: "Cantidad", align: "right", cell: (l) => <span className="tabular-nums">{l.cantidad}</span> },
    { id: "costo", header: "Costo unitario", align: "right", cell: (l) => <MoneyText value={l.costo_unitario} /> },
    { id: "subtotal", header: "Subtotal", align: "right", cell: (l) => <MoneyText value={l.subtotal} className="font-medium" /> },
    {
      id: "stock",
      header: "Stock actual",
      align: "right",
      cell: (l) => <span className="tabular-nums">{productos.data?.get(l.producto_id)?.stock_actual ?? "—"}</span>,
    },
  ];

  return (
    <>
      {volver}
      <PageHeader
        title={`Pedido a ${distribuidora.data?.nombre ?? "distribuidora"}`}
        description={`Creado el ${formatFecha(p.created_at)}`}
        actions={
          pendiente ? (
            <>
              {puedeCancelar && (
                <Button type="button" variant="outline" disabled={ocupado} onClick={() => setAccion("cancelar")}>
                  <XCircle aria-hidden="true" /> Cancelar pedido
                </Button>
              )}
              <Button type="button" disabled={ocupado} onClick={() => setAccion("recibir")}>
                <PackageCheck aria-hidden="true" /> Recibir pedido
              </Button>
            </>
          ) : undefined
        }
      />
      <div className="space-y-4">
        <Card>
          <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3">
            <div>
              <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Estado</p>
              <div className="mt-1">
                <EstadoPedidoBadge estado={p.estado} />
              </div>
            </div>
            {distribuidora.data !== undefined && (
              <div>
                <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Distribuidora</p>
                <Link
                  to={`/distribuidoras/${distribuidora.data.id}`}
                  className="mt-1 block text-sm font-medium underline-offset-4 hover:underline"
                >
                  {distribuidora.data.nombre}
                </Link>
              </div>
            )}
            {p.recibido_at !== null && (
              <div>
                <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Fecha de recepción</p>
                <p className="mt-1 text-sm">{formatFechaHora(p.recibido_at)}</p>
              </div>
            )}
            {p.notas !== null && p.notas !== "" && (
              <div className="min-w-0">
                <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Notas</p>
                <p className="mt-1 text-sm">{p.notas}</p>
              </div>
            )}
            <div className="ml-auto text-right">
              <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Total estimado</p>
              <MoneyText value={p.total_estimado} className="text-2xl font-semibold" />
            </div>
          </CardContent>
        </Card>
        <DataTable label="Líneas del pedido" columns={columnas} rows={p.lineas} getRowKey={(l) => l.id} />
        {pendiente && (
          <p className="text-sm text-muted-foreground">
            Mientras esté pendiente, el pedido no mueve stock. Al recibirlo se suma todo y se actualizan los costos.
          </p>
        )}
      </div>
      <ConfirmDialog
        open={accion === "recibir"}
        onOpenChange={(open) => {
          if (!open) setAccion(null);
        }}
        title="Recibir pedido"
        description="Se suma todo el stock del pedido y se actualizan los costos de los productos con los del pedido. Esta acción no se puede deshacer."
        confirmLabel="Recibir pedido"
        onConfirm={() => void ejecutar("recibir")}
      />
      <ConfirmDialog
        open={accion === "cancelar"}
        onOpenChange={(open) => {
          if (!open) setAccion(null);
        }}
        title="Cancelar pedido"
        description="El pedido queda cancelado y no se puede recibir. El stock no cambia."
        confirmLabel="Cancelar pedido"
        cancelLabel="Volver"
        destructive
        onConfirm={() => void ejecutar("cancelar")}
      />
    </>
  );
}
