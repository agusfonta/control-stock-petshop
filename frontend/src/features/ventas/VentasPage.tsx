import { Receipt } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatFechaHora, numeroCorto } from "@/features/pos/comprobanteFormat";
import { useSession } from "@/features/auth/session";
import { ClienteNombre } from "@/features/ventas/ClienteNombre";
import { EstadoVentaBadge } from "@/features/ventas/EstadoVentaBadge";
import { PAGE_SIZE, type VentasFiltros, useVentas } from "@/features/ventas/api";
import { hoyLocal, validarRango } from "@/features/ventas/filtros";
import type { VentaResumen } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { PageHeader } from "@/shared/components/PageHeader";

type EstadoFiltro = "todas" | "confirmada" | "anulada";

const OPCIONES_ESTADO: { value: EstadoFiltro; label: string }[] = [
  { value: "todas", label: "Confirmadas y anuladas" },
  { value: "confirmada", label: "Confirmadas" },
  { value: "anulada", label: "Anuladas" },
];


/** Historial de ventas: hoy por defecto; el mostrador ve solo las suyas (lo garantiza el servidor). */
export function VentasPage(): ReactElement {
  const navigate = useNavigate();
  const me = useSession((s) => s.user);
  const [estado, setEstado] = useState<EstadoFiltro>("todas");
  const [desde, setDesde] = useState(() => hoyLocal());
  const [hasta, setHasta] = useState(() => hoyLocal());
  const [page, setPage] = useState(1);

  const errorRango = validarRango(desde, hasta);
  const filtros: VentasFiltros = { estado: estado === "todas" ? undefined : estado, desde, hasta, page };
  const ventas = useVentas(errorRango === null ? filtros : { ...filtros, desde: "", hasta: "", page: 1 });

  const columnas: DataTableColumn<VentaResumen>[] = [
    { id: "fecha", header: "Fecha", cell: (v) => <span className="tabular-nums">{formatFechaHora(v.confirmada_at ?? v.created_at)}</span> },
    {
      id: "numero",
      header: "N°",
      cell: (v) => (
        <Link to={`/ventas/${v.id}`} className="font-mono font-medium text-primary underline-offset-4 hover:underline focus-visible:underline">
          {numeroCorto(v.id)}
        </Link>
      ),
    },
    { id: "cliente", header: "Cliente", cell: (v) => <ClienteNombre id={v.cliente_id} /> },
    { id: "vendedor", header: "Vendedor", cell: (v) => (v.usuario_id === me?.id ? "Vos" : "Otro usuario") },
    { id: "total", header: "Total", align: "right", cell: (v) => <MoneyText value={v.total} className="font-medium" /> },
    { id: "estado", header: "Estado", cell: (v) => <EstadoVentaBadge estado={v.estado} /> },
  ];

  function cambiar(accion: () => void): void {
    accion();
    setPage(1);
  }

  return (
    <>
      <PageHeader title="Ventas" description="Historial de ventas del mostrador. Por defecto, las de hoy." />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <label htmlFor="ventas-desde" className="block text-sm font-medium">
            Desde
          </label>
          <Input id="ventas-desde" type="date" className="h-10 w-40" value={desde} max={hasta || undefined} onChange={(e) => cambiar(() => setDesde(e.target.value))} />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="ventas-hasta" className="block text-sm font-medium">
            Hasta
          </label>
          <Input id="ventas-hasta" type="date" className="h-10 w-40" value={hasta} min={desde || undefined} onChange={(e) => cambiar(() => setHasta(e.target.value))} />
        </div>
        <Select value={estado} onValueChange={(v) => cambiar(() => setEstado(v as EstadoFiltro))}>
          <SelectTrigger aria-label="Filtrar por estado" className="h-10 w-full sm:w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OPCIONES_ESTADO.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          type="button"
          variant="ghost"
          className="h-10"
          onClick={() => cambiar(() => { setDesde(hoyLocal()); setHasta(hoyLocal()); setEstado("todas"); })}
        >
          Hoy
        </Button>
      </div>
      {errorRango !== null && (
        <p role="alert" className="mb-3 text-sm text-destructive">
          {errorRango}
        </p>
      )}

      {ventas.isError ? (
        <ErrorState title="No pudimos cargar las ventas" onRetry={() => void ventas.refetch()} />
      ) : (
        <DataTable
          label="Ventas"
          columns={columnas}
          rows={ventas.data?.items}
          getRowKey={(v) => v.id}
          isLoading={ventas.isPending}
          onRowClick={(v) => void navigate(`/ventas/${v.id}`)}
          empty={
            <EmptyState
              icon={Receipt}
              title="No hay ventas en este período"
              description="Probá con otras fechas o con otro estado. Las ventas nuevas aparecen acá apenas se cobran."
            />
          }
          pagination={
            ventas.data === undefined
              ? undefined
              : { page, pageSize: PAGE_SIZE, total: ventas.data.total, onPageChange: setPage }
          }
        />
      )}
    </>
  );
}
