import { Banknote, MoreHorizontal, Trash2 } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAnularPago, usePagos } from "@/features/compras/api";
import { METODO_PAGO_LABEL, formatDia } from "@/features/compras/format";
import { DistribuidoraSelect } from "@/features/distribuidoras/DistribuidoraSelect";
import { useDistribuidorasIndex } from "@/features/distribuidoras/api";
import { ApiError } from "@/shared/api/errors";
import type { PagoDistribuidora } from "@/shared/api/types";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

const PAGE_SIZE = 20;

interface PagosTabProps {
  onRegistrar: () => void;
}

/** Pagos a distribuidoras (solo dueña): listado filtrable y anulación con confirmación. */
export function PagosTab({ onRegistrar }: PagosTabProps): ReactElement {
  const [page, setPage] = useState(1);
  const [distribuidoraId, setDistribuidoraId] = useState("");
  const [aAnular, setAAnular] = useState<PagoDistribuidora | null>(null);
  const pagos = usePagos(page, distribuidoraId === "" ? null : distribuidoraId, true);
  const distribuidoras = useDistribuidorasIndex();
  const anular = useAnularPago();

  async function confirmarAnular(): Promise<void> {
    if (aAnular === null) return;
    try {
      await anular.mutateAsync(aAnular.id);
      notifySuccess("Pago anulado");
    } catch (error) {
      notifyError(error instanceof ApiError ? error.message : "No pudimos anular el pago");
    } finally {
      setAAnular(null);
    }
  }

  const columnas: DataTableColumn<PagoDistribuidora>[] = [
    { id: "fecha", header: "Fecha", cell: (p) => formatDia(p.fecha) },
    {
      id: "distribuidora",
      header: "Distribuidora",
      cell: (p) => {
        const d = distribuidoras.data?.get(p.distribuidora_id);
        return d === undefined ? (
          <span className="text-muted-foreground">{distribuidoras.data === undefined ? "—" : "Distribuidora dada de baja"}</span>
        ) : (
          <Link to={`/distribuidoras/${d.id}`} className="font-medium underline-offset-4 hover:underline">
            {d.nombre}
          </Link>
        );
      },
    },
    { id: "metodo", header: "Medio", cell: (p) => METODO_PAGO_LABEL[p.metodo] },
    { id: "monto", header: "Monto", align: "right", cell: (p) => <MoneyText value={p.monto} className="font-medium" /> },
    {
      id: "nota",
      header: "Nota",
      cell: (p) => <span className="line-clamp-1 max-w-56">{p.nota ?? <span className="text-muted-foreground">—</span>}</span>,
    },
    {
      id: "acciones",
      header: <span className="sr-only">Acciones</span>,
      align: "right",
      className: "w-12",
      cell: (p) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="ghost" size="icon" aria-label={`Acciones del pago del ${formatDia(p.fecha)}`}>
              <MoreHorizontal aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem variant="destructive" onSelect={() => setAAnular(p)}>
              <Trash2 aria-hidden="true" /> Anular pago
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  const registrarBtn = (
    <Button type="button" onClick={onRegistrar}>
      <Banknote aria-hidden="true" /> Registrar pago
    </Button>
  );

  return (
    <div className="space-y-4">
      <DistribuidoraSelect
        conTodas
        value={distribuidoraId}
        onChange={(id) => {
          setDistribuidoraId(id);
          setPage(1);
        }}
        aria-label="Filtrar pagos por distribuidora"
      />
      {pagos.isError && pagos.data === undefined ? (
        <ErrorState title="No pudimos cargar los pagos" onRetry={() => void pagos.refetch()} />
      ) : (
        <DataTable
          label="Pagos a distribuidoras"
          columns={columnas}
          rows={pagos.data?.items}
          getRowKey={(p) => p.id}
          isLoading={pagos.isLoading}
          empty={
            <EmptyState
              icon={Banknote}
              title={distribuidoraId === "" ? "Todavía no registraste pagos" : "Sin pagos para esta distribuidora"}
              description="Los pagos se descuentan de lo que le debés a cada distribuidora."
              action={registrarBtn}
            />
          }
          pagination={{ page, pageSize: PAGE_SIZE, total: pagos.data?.total ?? 0, onPageChange: setPage }}
        />
      )}
      <ConfirmDialog
        open={aAnular !== null}
        onOpenChange={(open) => {
          if (!open) setAAnular(null);
        }}
        title="Anular pago"
        description="El pago deja de figurar y vuelve a sumarse al saldo que le debés a la distribuidora."
        confirmLabel="Anular pago"
        cancelLabel="Volver"
        destructive
        onConfirm={() => void confirmarAnular()}
      />
    </div>
  );
}
