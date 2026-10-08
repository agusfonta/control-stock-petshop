import { MoreHorizontal, PackagePlus, PackageSearch, Pencil, Percent, Trash2 } from "lucide-react";
import { type ReactElement, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MargenMinimoDialog } from "@/features/productos/MargenMinimoDialog";
import { ProductoSheet } from "@/features/productos/ProductoSheet";
import { PAGE_SIZE, useBajaProducto, useProductos } from "@/features/productos/api";
import { fraccionAMargenPct } from "@/features/productos/pricing";
import { StockBadge } from "@/features/stock/StockBadge";
import { ApiError } from "@/shared/api/errors";
import type { Producto } from "@/shared/api/types";
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

/** Catalogo: la dueña edita; el mostrador solo consulta precio y stock (UX11). */
export function ProductosPage(): ReactElement {
  const puedeEditar = useCan("productos.editar");
  const [busqueda, setBusqueda] = useState("");
  const q = useDebouncedValue(busqueda.trim(), 250);
  const [page, setPage] = useState(1);
  const [sheet, setSheet] = useState<{ producto: Producto | null } | null>(null);
  const [rapido, setRapido] = useState<Producto | null>(null);
  const [baja, setBaja] = useState<Producto | null>(null);
  const productos = useProductos({ page, q });
  const bajaMutation = useBajaProducto();

  useEffect(() => {
    setPage(1);
  }, [q]);

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

  const columnas: DataTableColumn<Producto>[] = [
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
      cell: (p) => (
        <div className="flex items-center justify-end gap-2">
          <StockBadge stockActual={p.stock_actual} stockMinimo={p.stock_minimo} />
          <span className="tabular-nums">{p.stock_actual}</span>
        </div>
      ),
    },
    { id: "minimo", header: "Mínimo", align: "right", cell: (p) => <span className="tabular-nums">{p.stock_minimo}</span> },
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
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => setBaja(p)}>
              <Trash2 aria-hidden="true" /> Dar de baja
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    });
  }

  const hayBusqueda = q !== "";
  const vacio = (
    <EmptyState
      icon={hayBusqueda ? PackageSearch : PackagePlus}
      title={hayBusqueda ? "No encontramos productos" : "Todavía no hay productos"}
      description={
        hayBusqueda ? `Ningún producto coincide con "${q}". Probá con otro SKU o nombre.` : "Cargá el primer producto del catálogo."
      }
      action={
        puedeEditar && !hayBusqueda ? (
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
        title="Productos"
        description={puedeEditar ? "Catálogo, costos, márgenes y stock mínimo." : "Catálogo con precios y stock."}
        actions={
          puedeEditar ? (
            <Button type="button" onClick={() => setSheet({ producto: null })}>
              <PackagePlus aria-hidden="true" /> Nuevo producto
            </Button>
          ) : undefined
        }
      />
      <div className="space-y-4">
        <SearchField value={busqueda} onChange={setBusqueda} label="Buscar productos" placeholder="Buscar por SKU o nombre" />
        {productos.isError && productos.data === undefined ? (
          <ErrorState title="No pudimos cargar los productos" onRetry={() => void productos.refetch()} />
        ) : (
          <DataTable
            label="Productos"
            columns={columnas}
            rows={productos.data?.items}
            getRowKey={(p) => p.id}
            isLoading={productos.isLoading}
            empty={vacio}
            pagination={{
              page,
              pageSize: PAGE_SIZE,
              total: productos.data?.total ?? 0,
              onPageChange: setPage,
            }}
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
