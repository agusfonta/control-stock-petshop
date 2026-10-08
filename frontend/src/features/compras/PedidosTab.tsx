import { ClipboardList } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EstadoPedidoBadge } from "@/features/compras/EstadoPedidoBadge";
import { PAGE_SIZE, usePedidos } from "@/features/compras/api";
import { ESTADO_PEDIDO_LABEL, formatFecha } from "@/features/compras/format";
import { DistribuidoraSelect } from "@/features/distribuidoras/DistribuidoraSelect";
import { useDistribuidorasIndex } from "@/features/distribuidoras/api";
import type { EstadoPedido, Pedido } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";

const TODOS = "todos";
const ESTADOS: readonly EstadoPedido[] = ["pendiente", "recibido", "cancelado"];

function esEstado(valor: string): valor is EstadoPedido {
  return (ESTADOS as readonly string[]).includes(valor);
}

interface PedidosTabProps {
  onNuevo: () => void;
}

/** Pedidos a distribuidoras: listado paginado filtrable por estado y distribuidora. */
export function PedidosTab({ onNuevo }: PedidosTabProps): ReactElement {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [estado, setEstado] = useState<EstadoPedido | null>(null);
  const [distribuidoraId, setDistribuidoraId] = useState("");
  const pedidos = usePedidos({ page, estado, distribuidoraId: distribuidoraId === "" ? null : distribuidoraId });
  const distribuidoras = useDistribuidorasIndex();
  const filtrado = estado !== null || distribuidoraId !== "";

  const columnas: DataTableColumn<Pedido>[] = [
    {
      id: "fecha",
      header: "Fecha",
      cell: (p) => (
        <Link
          to={`/compras/pedidos/${p.id}`}
          className="font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {formatFecha(p.created_at)}
        </Link>
      ),
    },
    {
      id: "distribuidora",
      header: "Distribuidora",
      cell: (p) => {
        const d = distribuidoras.data?.get(p.distribuidora_id);
        if (d !== undefined) return <span className="font-medium">{d.nombre}</span>;
        return (
          <span className="text-muted-foreground">{distribuidoras.data === undefined ? "—" : "Distribuidora dada de baja"}</span>
        );
      },
    },
    { id: "estado", header: "Estado", cell: (p) => <EstadoPedidoBadge estado={p.estado} /> },
    {
      id: "total",
      header: "Total estimado",
      align: "right",
      cell: (p) => <MoneyText value={p.total_estimado} className="font-medium" />,
    },
  ];

  const nuevo = (
    <Button type="button" onClick={onNuevo}>
      <ClipboardList aria-hidden="true" /> Nuevo pedido
    </Button>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={estado ?? TODOS}
          onValueChange={(v) => {
            setEstado(esEstado(v) ? v : null);
            setPage(1);
          }}
        >
          <SelectTrigger aria-label="Filtrar por estado" className="h-10 w-full sm:w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TODOS}>Todos los estados</SelectItem>
            {ESTADOS.map((e) => (
              <SelectItem key={e} value={e}>
                {ESTADO_PEDIDO_LABEL[e]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <DistribuidoraSelect
          conTodas
          value={distribuidoraId}
          onChange={(id) => {
            setDistribuidoraId(id);
            setPage(1);
          }}
          aria-label="Filtrar por distribuidora"
        />
        {filtrado && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setEstado(null);
              setDistribuidoraId("");
              setPage(1);
            }}
          >
            Limpiar filtros
          </Button>
        )}
      </div>
      {pedidos.isError && pedidos.data === undefined ? (
        <ErrorState title="No pudimos cargar los pedidos" onRetry={() => void pedidos.refetch()} />
      ) : (
        <DataTable
          label="Pedidos a distribuidoras"
          columns={columnas}
          rows={pedidos.data?.items}
          getRowKey={(p) => p.id}
          isLoading={pedidos.isLoading}
          onRowClick={(p) => void navigate(`/compras/pedidos/${p.id}`)}
          empty={
            <EmptyState
              icon={ClipboardList}
              title={filtrado ? "No hay pedidos con esos filtros" : "Todavía no hay pedidos"}
              description={
                filtrado
                  ? "Probá con otro estado o distribuidora."
                  : "Armá el primero eligiendo una distribuidora y los productos a reponer."
              }
              action={filtrado ? undefined : nuevo}
            />
          }
          pagination={{ page, pageSize: PAGE_SIZE, total: pedidos.data?.total ?? 0, onPageChange: setPage }}
        />
      )}
    </div>
  );
}
