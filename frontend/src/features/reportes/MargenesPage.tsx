import { CircleDollarSign, Percent, TriangleAlert, TrendingUp, Wallet } from "lucide-react";
import { type ReactElement, useState } from "react";
import { PeriodoFiltro } from "@/features/reportes/PeriodoFiltro";
import { ReportesLayout } from "@/features/reportes/ReportesLayout";
import { useMargenes } from "@/features/reportes/api";
import { type Periodo, fechaLegible, formatMargenPct, periodoQuery, validarPeriodo } from "@/features/reportes/params";
import type { MargenProducto, MargenesReporte } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { KpiCard } from "@/shared/components/KpiCard";
import { MoneyText } from "@/shared/components/MoneyText";
import { toCents } from "@/shared/lib/money";

const PAGE_SIZE = 20;

const COLUMNAS: DataTableColumn<MargenProducto>[] = [
  {
    id: "producto",
    header: "Producto",
    cell: (p) => (
      <div className="min-w-0">
        <p className="truncate font-medium">{p.nombre}</p>
        <p className="truncate font-mono text-xs text-muted-foreground">{p.sku}</p>
      </div>
    ),
  },
  { id: "unidades", header: "Unidades", align: "right", cell: (p) => <span className="tabular-nums">{p.unidades}</span> },
  { id: "ingresos", header: "Ingresos", align: "right", cell: (p) => <MoneyText value={p.ingresos} /> },
  { id: "costo", header: "Costo", align: "right", cell: (p) => <MoneyText value={p.costo} /> },
  { id: "margen", header: "Margen bruto", align: "right", cell: (p) => <MoneyText value={p.margen_bruto} className="font-medium" /> },
  {
    id: "pct",
    header: "Margen %",
    align: "right",
    cell: (p) => <span className="tabular-nums">{formatMargenPct(p.margen_pct)}</span>,
  },
];

function Totales({ data }: { data: MargenesReporte }): ReactElement {
  const t = data.totales;
  return (
    <>
      <p className="text-sm text-muted-foreground" aria-live="polite">
        Período: {fechaLegible(data.desde)} al {fechaLegible(data.hasta)}
      </p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Ingresos" value={<MoneyText value={t.ingresos} />} icon={Wallet} />
        <KpiCard label="Costo" value={<MoneyText value={t.costo} />} icon={CircleDollarSign} />
        <KpiCard label="Margen bruto" value={<MoneyText value={t.margen_bruto} />} icon={TrendingUp} />
        <KpiCard
          label="Margen sobre costo"
          value={formatMargenPct(t.margen_pct)}
          hint="Margen bruto ÷ costo"
          icon={Percent}
        />
      </div>
      {t.lineas_sin_costo > 0 && (
        <aside
          aria-label="Líneas sin costo"
          className="flex items-start gap-3 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            <strong>
              {t.lineas_sin_costo === 1 ? "1 línea" : `${t.lineas_sin_costo} líneas`} sin costo informado
            </strong>{" "}
            por <MoneyText value={t.ingresos_sin_costo} />. No se incluyen en el margen de arriba ni en la tabla.
          </p>
        </aside>
      )}
    </>
  );
}

/** Margen bruto por producto con costo historico del periodo; solo `reportes.completos` (guard en la ruta). */
export function MargenesPage(): ReactElement {
  const [periodo, setPeriodo] = useState<Periodo>({ desde: "", hasta: "" });
  const [page, setPage] = useState(1);
  const errorPeriodo = validarPeriodo(periodo);
  const reporte = useMargenes({ ...periodoQuery(periodo), page, pageSize: PAGE_SIZE }, errorPeriodo === null);
  const data = reporte.data;
  const sinMargen = data !== undefined && data.items.length === 0 && toCents(data.totales.ingresos_sin_costo) === 0;

  return (
    <ReportesLayout
      title="Márgenes"
      description="Ganancia bruta por producto, con el costo que tenía cada venta."
      filtros={
        <PeriodoFiltro
          value={periodo}
          onChange={(p) => {
            setPeriodo(p);
            setPage(1);
          }}
          error={errorPeriodo}
        />
      }
    >
      {data !== undefined && <Totales data={data} />}
      {reporte.isError && data === undefined ? (
        <ErrorState title="No pudimos cargar los márgenes" onRetry={() => void reporte.refetch()} />
      ) : (
        <DataTable
          label="Márgenes por producto"
          columns={COLUMNAS}
          rows={data?.items}
          isLoading={reporte.isLoading}
          getRowKey={(p) => p.producto_id}
          pagination={
            data === undefined
              ? undefined
              : { page: data.page, pageSize: data.page_size, total: data.total, onPageChange: setPage }
          }
          empty={
            <EmptyState
              icon={Percent}
              title={sinMargen ? "No hubo ventas en este período" : "No hay productos con costo informado"}
              description={
                sinMargen
                  ? "Probá con un período más largo."
                  : "Las ventas del período no tienen costo registrado, así que no se puede calcular el margen."
              }
            />
          }
        />
      )}
    </ReportesLayout>
  );
}
