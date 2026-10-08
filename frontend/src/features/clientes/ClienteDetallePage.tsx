import { ArrowLeft, Mail, MapPin, Pencil, Phone, Receipt } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Link, useParams } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ClienteSheet } from "@/features/clientes/ClienteSheet";
import { PAGE_SIZE, useCliente, useHistorialCliente } from "@/features/clientes/api";
import { formatFechaHora } from "@/features/clientes/format";
import { ApiError } from "@/shared/api/errors";
import type { EstadoVenta, VentaResumen } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { PageHeader } from "@/shared/components/PageHeader";
import { useCan } from "@/shared/lib/permissions";

const ESTADO_LABEL: Record<EstadoVenta, string> = {
  borrador: "Borrador",
  confirmada: "Confirmada",
  anulada: "Anulada",
};

function EstadoBadge({ estado }: { estado: EstadoVenta }): ReactElement {
  if (estado === "anulada") {
    return (
      <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-destructive">
        {ESTADO_LABEL[estado]}
      </Badge>
    );
  }
  return <Badge variant="secondary">{ESTADO_LABEL[estado]}</Badge>;
}

function Dato({ icon: Icon, children }: { icon: typeof Mail; children: string | null }): ReactElement {
  return (
    <li className="flex items-center gap-2 text-sm">
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      {children ?? <span className="text-muted-foreground">Sin dato</span>}
    </li>
  );
}

const columnas: DataTableColumn<VentaResumen>[] = [
  {
    id: "fecha",
    header: "Fecha",
    cell: (v) => (
      <Link
        to={`/ventas/${v.id}`}
        className="font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        {formatFechaHora(v.confirmada_at ?? v.created_at)}
      </Link>
    ),
  },
  { id: "estado", header: "Estado", cell: (v) => <EstadoBadge estado={v.estado} /> },
  { id: "total", header: "Total", align: "right", cell: (v) => <MoneyText value={v.total} className="font-semibold" /> },
];

/** Detalle del cliente con su historial de ventas paginado (cada venta enlaza a `/ventas/:id`). */
export function ClienteDetallePage(): ReactElement {
  const { id = "" } = useParams<{ id: string }>();
  const puedeEditar = useCan("clientes.editar");
  const [page, setPage] = useState(1);
  const [editando, setEditando] = useState(false);
  const cliente = useCliente(id);
  const historial = useHistorialCliente(id, page);

  const volver = (
    <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2 text-muted-foreground">
      <Link to="/clientes">
        <ArrowLeft aria-hidden="true" /> Clientes
      </Link>
    </Button>
  );

  if (cliente.isLoading) {
    return (
      <>
        {volver}
        <Skeleton className="mb-6 h-9 w-64" />
        <Skeleton className="h-28 w-full rounded-xl" />
      </>
    );
  }
  if (cliente.isError || cliente.data === undefined) {
    const noExiste = cliente.error instanceof ApiError && cliente.error.status === 404;
    return (
      <>
        {volver}
        {noExiste ? (
          <EmptyState title="No encontramos al cliente" description="Puede que haya sido dado de baja o que el enlace sea incorrecto." />
        ) : (
          <ErrorState title="No pudimos cargar el cliente" onRetry={() => void cliente.refetch()} />
        )}
      </>
    );
  }

  const c = cliente.data;
  return (
    <>
      {volver}
      <PageHeader
        title={c.nombre}
        description={c.activo ? undefined : "Cliente dado de baja"}
        actions={
          puedeEditar ? (
            <Button type="button" variant="outline" onClick={() => setEditando(true)}>
              <Pencil aria-hidden="true" /> Editar
            </Button>
          ) : undefined
        }
      />
      <div className="space-y-6">
        <Card className="shadow-none">
          <CardContent>
            <ul className="grid gap-3 sm:grid-cols-3" aria-label="Datos de contacto">
              <Dato icon={Phone}>{c.telefono}</Dato>
              <Dato icon={Mail}>{c.email}</Dato>
              <Dato icon={MapPin}>{c.direccion}</Dato>
            </ul>
          </CardContent>
        </Card>
        <section aria-labelledby="historial-titulo" className="space-y-3">
          <h2 id="historial-titulo" className="text-lg font-semibold">
            Historial de ventas
          </h2>
          {!puedeEditar && (
            <p className="text-sm text-muted-foreground">Ves las ventas que registraste vos a este cliente.</p>
          )}
          {historial.isError && historial.data === undefined ? (
            <ErrorState title="No pudimos cargar el historial" onRetry={() => void historial.refetch()} />
          ) : (
            <DataTable
              label="Historial de ventas"
              columns={columnas}
              rows={historial.data?.items}
              getRowKey={(v) => v.id}
              isLoading={historial.isLoading}
              empty={
                <EmptyState
                  icon={Receipt}
                  title="Todavía no compró"
                  description="Cuando le vendas algo desde el POS, la venta aparece acá."
                />
              }
              pagination={{ page, pageSize: PAGE_SIZE, total: historial.data?.total ?? 0, onPageChange: setPage }}
            />
          )}
        </section>
      </div>
      <ClienteSheet open={editando} onOpenChange={setEditando} cliente={c} />
    </>
  );
}
