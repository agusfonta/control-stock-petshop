import { CircleCheck, PackageSearch, SlidersHorizontal, TriangleAlert } from "lucide-react";
import { type ReactElement, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/toggle";
import { AjusteStockDialog } from "@/features/stock/AjusteStockDialog";
import { StockBadge } from "@/features/stock/StockBadge";
import { useAlertasStock, useStockBusqueda, useStockList } from "@/features/stock/api";
import type { StockItem } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { PageHeader } from "@/shared/components/PageHeader";
import { SearchField } from "@/shared/components/SearchField";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { useCan } from "@/shared/lib/permissions";

const PAGE_SIZE = 20;

/** Consulta rapida de stock con alertas de reposicion; solo la dueña ajusta (D13, UX7). */
export function StockPage(): ReactElement {
  const puedeAjustar = useCan("stock.ajustar");
  const [busqueda, setBusqueda] = useState("");
  const q = useDebouncedValue(busqueda.trim(), 250);
  const [soloBajo, setSoloBajo] = useState(false);
  const [page, setPage] = useState(1);
  const [ajustando, setAjustando] = useState<StockItem | null>(null);
  const buscando = q !== "";

  const lista = useStockList({ page, soloBajoMinimo: soloBajo });
  const resultados = useStockBusqueda(q);
  const alertas = useAlertasStock();

  useEffect(() => {
    setPage(1);
  }, [q, soloBajo]);

  const activa = buscando ? resultados : lista;
  const filas = buscando
    ? resultados.data?.items.filter((p) => !soloBajo || p.bajo_minimo)
    : lista.data?.items;
  const bajoMinimo = alertas.data?.total_bajo_minimo;

  const columnas: DataTableColumn<StockItem>[] = [
    { id: "sku", header: "SKU", cell: (p) => <span className="font-mono text-xs">{p.sku}</span> },
    {
      id: "nombre",
      header: "Producto",
      cell: (p) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{p.nombre}</p>
          {p.marca !== null && p.marca !== "" && <p className="truncate text-xs text-muted-foreground">{p.marca}</p>}
        </div>
      ),
    },
    {
      id: "estado",
      header: "Estado",
      cell: (p) =>
        p.bajo_minimo ? (
          <StockBadge stockActual={p.stock_actual} stockMinimo={p.stock_minimo} />
        ) : (
          <span className="text-sm text-muted-foreground">Normal</span>
        ),
    },
    {
      id: "stock",
      header: "Stock",
      align: "right",
      cell: (p) => <span className="text-base font-semibold tabular-nums">{p.stock_actual}</span>,
    },
    { id: "minimo", header: "Mínimo", align: "right", cell: (p) => <span className="tabular-nums">{p.stock_minimo}</span> },
  ];
  if (puedeAjustar) {
    columnas.push({
      id: "acciones",
      header: <span className="sr-only">Acciones</span>,
      align: "right",
      cell: (p) => (
        <Button type="button" variant="outline" size="sm" onClick={() => setAjustando(p)} aria-label={`Ajustar stock de ${p.nombre}`}>
          <SlidersHorizontal aria-hidden="true" />
          Ajustar stock
        </Button>
      ),
    });
  }

  const vacio = (
    <EmptyState
      icon={soloBajo && !buscando ? CircleCheck : PackageSearch}
      title={
        buscando
          ? "No encontramos productos"
          : soloBajo
            ? "Todo el stock está por encima del mínimo"
            : "Todavía no hay productos"
      }
      description={
        buscando
          ? `Ningún producto coincide con "${q}"${soloBajo ? " bajo el mínimo" : ""}.`
          : soloBajo
            ? "No hay nada para reponer por ahora."
            : "Cargá productos desde el catálogo."
      }
    />
  );

  return (
    <>
      <PageHeader title="Stock" description="Existencias actuales y productos para reponer." />
      <div className="space-y-4">
        {bajoMinimo !== undefined && (
          <div
            className={
              bajoMinimo > 0
                ? "flex items-center gap-3 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-warning"
                : "flex items-center gap-3 rounded-xl border bg-card px-4 py-3 text-muted-foreground"
            }
            role="status"
          >
            {bajoMinimo > 0 ? <TriangleAlert className="size-5" aria-hidden="true" /> : <CircleCheck className="size-5" aria-hidden="true" />}
            <p className="text-sm font-medium">
              {bajoMinimo === 0
                ? "Ningún producto está bajo el mínimo."
                : bajoMinimo === 1
                  ? "1 producto bajo el mínimo."
                  : `${bajoMinimo} productos bajo el mínimo.`}
            </p>
            {bajoMinimo > 0 && !soloBajo && (
              <Button type="button" variant="outline" size="sm" className="ml-auto bg-background text-foreground" onClick={() => setSoloBajo(true)}>
                Ver solo esos
              </Button>
            )}
          </div>
        )}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <SearchField value={busqueda} onChange={setBusqueda} label="Buscar en stock" placeholder="Buscar por SKU o nombre" />
          <Toggle
            variant="outline"
            pressed={soloBajo}
            onPressedChange={setSoloBajo}
            aria-label="Solo bajo mínimo"
            className="h-10 gap-2 px-4"
          >
            <TriangleAlert aria-hidden="true" />
            Solo bajo mínimo
          </Toggle>
        </div>
        {activa.isError && activa.data === undefined ? (
          <ErrorState title="No pudimos cargar el stock" onRetry={() => void activa.refetch()} />
        ) : (
          <DataTable
            label="Stock"
            columns={columnas}
            rows={filas}
            getRowKey={(p) => p.id}
            isLoading={activa.isLoading}
            empty={vacio}
            pagination={
              buscando
                ? undefined
                : { page, pageSize: PAGE_SIZE, total: lista.data?.total ?? 0, onPageChange: setPage }
            }
          />
        )}
      </div>
      <AjusteStockDialog
        producto={ajustando}
        onOpenChange={(open) => {
          if (!open) setAjustando(null);
        }}
      />
    </>
  );
}
