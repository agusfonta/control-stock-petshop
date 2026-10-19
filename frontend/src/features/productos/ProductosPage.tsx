import {
  CircleCheck,
  MoreHorizontal,
  PackagePlus,
  PackageSearch,
  Pencil,
  Percent,
  SlidersHorizontal,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { type ReactElement, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Toggle } from "@/components/ui/toggle";
import { MargenMinimoDialog } from "@/features/productos/MargenMinimoDialog";
import { ProductoSheet } from "@/features/productos/ProductoSheet";
import { useBajaProducto } from "@/features/productos/api";
import { fraccionAMargenPct } from "@/features/productos/pricing";
import { AjusteStockDialog } from "@/features/stock/AjusteStockDialog";
import { StockBadge } from "@/features/stock/StockBadge";
import { useAlertasStock, useStockBusqueda, useStockList } from "@/features/stock/api";
import { ApiError } from "@/shared/api/errors";
import type { StockItem } from "@/shared/api/types";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { PageHeader } from "@/shared/components/PageHeader";
import { SearchField } from "@/shared/components/SearchField";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { useCan } from "@/shared/lib/permissions";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

const PAGE_SIZE = 20;

/** Productos y stock en una sola tabla: la dueña edita y ajusta; el mostrador solo consulta (UX7, UX11). */
export function ProductosPage(): ReactElement {
  const puedeEditar = useCan("productos.editar");
  const [busqueda, setBusqueda] = useState("");
  const q = useDebouncedValue(busqueda.trim(), 250);
  const [soloBajo, setSoloBajo] = useState(false);
  const [page, setPage] = useState(1);
  const [sheet, setSheet] = useState<{ producto: StockItem | null } | null>(null);
  const [rapido, setRapido] = useState<StockItem | null>(null);
  const [baja, setBaja] = useState<StockItem | null>(null);
  const [ajustando, setAjustando] = useState<StockItem | null>(null);
  const buscando = q !== "";

  const lista = useStockList({ page, soloBajoMinimo: soloBajo });
  const resultados = useStockBusqueda(q);
  const alertas = useAlertasStock();
  const bajaMutation = useBajaProducto();

  useEffect(() => {
    setPage(1);
  }, [q, soloBajo]);

  const activa = buscando ? resultados : lista;
  const filas = buscando ? resultados.data?.items.filter((p) => !soloBajo || p.bajo_minimo) : lista.data?.items;
  const bajoMinimo = alertas.data?.total_bajo_minimo;

  async function confirmarBaja(): Promise<void> {
    if (baja === null) return;
    try {
      await bajaMutation.mutateAsync(baja.id);
      notifySuccess("Producto dado de baja");
    } catch (error) {
      notifyError(error instanceof ApiError ? error.message : "No pudimos dar de baja el producto");
    } finally {
      setBaja(null);
    }
  }

  const columnas: DataTableColumn<StockItem>[] = [
    { id: "sku", header: "SKU", cell: (p) => <span className="font-mono text-xs">{p.sku}</span> },
    {
      id: "nombre",
      header: "Producto",
      cell: (p) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{p.nombre}</p>
          <p className="truncate text-xs text-muted-foreground">
            {[p.marca, p.categoria].filter((v): v is string => v !== null && v !== "").join(" · ") || "—"}
          </p>
        </div>
      ),
    },
  ];
  if (puedeEditar) {
    columnas.push(
      { id: "costo", header: "Costo", align: "right", cell: (p) => <MoneyText value={p.costo} /> },
      {
        id: "margen",
        header: "Margen",
        align: "right",
        cell: (p) => <span className="tabular-nums">{fraccionAMargenPct(p.margen_pct)} %</span>,
      },
    );
  }
  columnas.push(
    {
      id: "precio",
      header: "Precio",
      align: "right",
      cell: (p) => <MoneyText value={p.precio_venta} className="font-semibold" />,
    },
    {
      id: "stock",
      header: "Stock",
      align: "right",
      cell: (p) => <span className="text-base font-semibold tabular-nums">{p.stock_actual}</span>,
    },
    { id: "minimo", header: "Mínimo", align: "right", cell: (p) => <span className="tabular-nums">{p.stock_minimo}</span> },
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
  );
  if (puedeEditar) {
    columnas.push({
      id: "acciones",
      header: <span className="sr-only">Acciones</span>,
      align: "right",
      className: "w-12",
      cell: (p) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="ghost" size="icon" aria-label={`Acciones de ${p.nombre}`}>
              <MoreHorizontal aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setSheet({ producto: p })}>
              <Pencil aria-hidden="true" /> Editar
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setRapido(p)}>
              <Percent aria-hidden="true" /> Margen y mínimo
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setAjustando(p)}>
              <SlidersHorizontal aria-hidden="true" /> Ajustar stock
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => setBaja(p)}>
              <Trash2 aria-hidden="true" /> Dar de baja
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    });
  }

  const vacio = (
    <EmptyState
      icon={buscando ? PackageSearch : soloBajo ? CircleCheck : PackagePlus}
      title={
        buscando
          ? "No encontramos productos"
          : soloBajo
            ? "Todo el stock está por encima del mínimo"
            : "Todavía no hay productos"
      }
      description={
        buscando
          ? `Ningún producto coincide con "${q}"${soloBajo ? " bajo el mínimo" : ""}. Probá con otro SKU o nombre.`
          : soloBajo
            ? "No hay nada para reponer por ahora."
            : "Cargá el primer producto del catálogo."
      }
      action={
        puedeEditar && !buscando && !soloBajo ? (
          <Button type="button" onClick={() => setSheet({ producto: null })}>
            <PackagePlus aria-hidden="true" /> Nuevo producto
          </Button>
        ) : undefined
      }
    />
  );

  return (
    <>
      <PageHeader
        title="Productos y stock"
        description={puedeEditar ? "Catálogo, costos, márgenes y existencias." : "Catálogo con precios y stock."}
        actions={
          puedeEditar ? (
            <Button type="button" onClick={() => setSheet({ producto: null })}>
              <PackagePlus aria-hidden="true" /> Nuevo producto
            </Button>
          ) : undefined
        }
      />
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
            {bajoMinimo > 0 ? (
              <TriangleAlert className="size-5" aria-hidden="true" />
            ) : (
              <CircleCheck className="size-5" aria-hidden="true" />
            )}
            <p className="text-sm font-medium">
              {bajoMinimo === 0
                ? "Ningún producto está bajo el mínimo."
                : bajoMinimo === 1
                  ? "1 producto bajo el mínimo."
                  : `${bajoMinimo} productos bajo el mínimo.`}
            </p>
            {bajoMinimo > 0 && !soloBajo && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="ml-auto bg-background text-foreground"
                onClick={() => setSoloBajo(true)}
              >
                Ver solo esos
              </Button>
            )}
          </div>
        )}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <SearchField value={busqueda} onChange={setBusqueda} label="Buscar productos" placeholder="Buscar por SKU o nombre" />
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
          <ErrorState title="No pudimos cargar los productos" onRetry={() => void activa.refetch()} />
        ) : (
          <DataTable
            label="Productos"
            columns={columnas}
            rows={filas}
            getRowKey={(p) => p.id}
            isLoading={activa.isLoading}
            empty={vacio}
            pagination={
              buscando ? undefined : { page, pageSize: PAGE_SIZE, total: lista.data?.total ?? 0, onPageChange: setPage }
            }
          />
        )}
      </div>
      <ProductoSheet
        open={sheet !== null}
        onOpenChange={(open) => {
          if (!open) setSheet(null);
        }}
        producto={sheet?.producto ?? null}
      />
      <MargenMinimoDialog
        producto={rapido}
        onOpenChange={(open) => {
          if (!open) setRapido(null);
        }}
      />
      <AjusteStockDialog
        producto={ajustando}
        onOpenChange={(open) => {
          if (!open) setAjustando(null);
        }}
      />
      <ConfirmDialog
        open={baja !== null}
        onOpenChange={(open) => {
          if (!open) setBaja(null);
        }}
        title="Dar de baja el producto"
        description={`"${baja?.nombre ?? ""}" deja de aparecer en el catálogo y en el POS. Las ventas anteriores se conservan.`}
        confirmLabel="Dar de baja"
        destructive
        onConfirm={() => void confirmarBaja()}
      />
    </>
  );
}
