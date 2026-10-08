import { TrendingUp } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PeriodoFiltro } from "@/features/reportes/PeriodoFiltro";
import { ReportesLayout } from "@/features/reportes/ReportesLayout";
import { type MasVendidosParams, useMasVendidos } from "@/features/reportes/api";
import { type Periodo, fechaLegible, periodoQuery, validarPeriodo } from "@/features/reportes/params";
import type { ProductoVendido } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";

type Orden = MasVendidosParams["orden"];
type Fila = ProductoVendido & { posicion: number };
const LIMITES = [10, 20, 50];

/** Ranking de productos del periodo por unidades o monto; solo `reportes.completos` (guard en la ruta). */
export function MasVendidosPage(): ReactElement {
  const [periodo, setPeriodo] = useState<Periodo>({ desde: "", hasta: "" });
  const [orden, setOrden] = useState<Orden>("cantidad");
  const [limite, setLimite] = useState(10);
  const errorPeriodo = validarPeriodo(periodo);
  const reporte = useMasVendidos({ ...periodoQuery(periodo), orden, limite }, errorPeriodo === null);
  const data = reporte.data;

  const columnas: DataTableColumn<Fila>[] = [
    {
      id: "pos",
      header: "#",
      className: "w-12",
      cell: (p) => <span className="text-muted-foreground tabular-nums">{p.posicion}</span>,
    },
    {
      id: "producto",
      header: "Producto",
      cell: (p) => (
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-medium">
            <span className="truncate">{p.nombre}</span>
            {!p.activo && <Badge variant="outline">Dado de baja</Badge>}
          </p>
          <p className="truncate font-mono text-xs text-muted-foreground">{p.sku}</p>
        </div>
      ),
    },
    { id: "unidades", header: "Unidades", align: "right", cell: (p) => <span className="tabular-nums">{p.unidades}</span> },
    { id: "monto", header: "Monto", align: "right", cell: (p) => <MoneyText value={p.monto} /> },
  ];
  const filas = data?.items.map((item, i): Fila => ({ ...item, posicion: i + 1 }));

  const filtros = (
    <>
      <PeriodoFiltro value={periodo} onChange={setPeriodo} error={errorPeriodo} />
      <div className="space-y-1.5">
        <Label htmlFor="mv-orden">Ordenar por</Label>
        <Select value={orden} onValueChange={(v) => setOrden(v as Orden)}>
          <SelectTrigger id="mv-orden" className="min-w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="cantidad">Unidades</SelectItem>
            <SelectItem value="monto">Monto</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="mv-limite">Mostrar</Label>
        <Select value={String(limite)} onValueChange={(v) => setLimite(Number(v))}>
          <SelectTrigger id="mv-limite" className="min-w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LIMITES.map((l) => (
              <SelectItem key={l} value={String(l)}>
                Top {l}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </>
  );

  return (
    <ReportesLayout
      title="Más vendidos"
      description="Los productos que más se vendieron en el período."
      filtros={filtros}
    >
      {data !== undefined && (
        <p className="text-sm text-muted-foreground" aria-live="polite">
          Período: {fechaLegible(data.desde)} al {fechaLegible(data.hasta)}
        </p>
      )}
      {reporte.isError && data === undefined ? (
        <ErrorState title="No pudimos cargar el ranking" onRetry={() => void reporte.refetch()} />
      ) : (
        <DataTable
          label="Productos más vendidos"
          columns={columnas}
          rows={filas}
          isLoading={reporte.isLoading}
          getRowKey={(p) => p.producto_id}
          empty={
            <EmptyState
              icon={TrendingUp}
              title="No hubo ventas en este período"
              description="Probá con un período más largo."
            />
          }
        />
      )}
    </ReportesLayout>
  );
}
