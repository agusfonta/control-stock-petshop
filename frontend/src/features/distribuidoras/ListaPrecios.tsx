import { MoreHorizontal, PackagePlus, Pencil, Trash2 } from "lucide-react";
import { type ReactElement, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PrecioSheet } from "@/features/distribuidoras/PrecioSheet";
import { useListaPrecios, useProductosIndex, useQuitarPrecio } from "@/features/distribuidoras/api";
import { ApiError } from "@/shared/api/errors";
import type { ListaPrecio, Producto } from "@/shared/api/types";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { toCents } from "@/shared/lib/money";
import { useCan } from "@/shared/lib/permissions";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

interface ListaPreciosProps {
  distribuidoraId: string;
}

/** Lista de precios de una distribuidora; agregar, cambiar costo y quitar solo con `distribuidoras.editar`. */
export function ListaPrecios({ distribuidoraId }: ListaPreciosProps): ReactElement {
  const puedeEditar = useCan("distribuidoras.editar");
  const lista = useListaPrecios(distribuidoraId);
  const productos = useProductosIndex();
  const quitar = useQuitarPrecio(distribuidoraId);
  const [sheet, setSheet] = useState<{ producto: Producto | null; costoCents?: number } | null>(null);
  const [aQuitar, setAQuitar] = useState<ListaPrecio | null>(null);

  const filas = useMemo(
    () =>
      [...(lista.data ?? [])].sort((a, b) =>
        (productos.data?.get(a.producto_id)?.nombre ?? "~").localeCompare(
          productos.data?.get(b.producto_id)?.nombre ?? "~",
          "es",
        ),
      ),
    [lista.data, productos.data],
  );
  const enLista = useMemo(() => new Set(filas.map((f) => f.producto_id)), [filas]);

  async function confirmarQuitar(): Promise<void> {
    if (aQuitar === null) return;
    try {
      await quitar.mutateAsync(aQuitar.producto_id);
      notifySuccess("Producto quitado de la lista");
    } catch (error) {
      notifyError(error instanceof ApiError ? error.message : "No pudimos quitar el producto");
    } finally {
      setAQuitar(null);
    }
  }

  const nombreDe = (id: string): string => productos.data?.get(id)?.nombre ?? "—";
  const columnas: DataTableColumn<ListaPrecio>[] = [
    {
      id: "producto",
      header: "Producto",
      cell: (f) => (
        <span className="block min-w-0">
          <span className="block truncate font-medium">{nombreDe(f.producto_id)}</span>
          <span className="block text-xs text-muted-foreground">{productos.data?.get(f.producto_id)?.sku ?? ""}</span>
        </span>
      ),
    },
    { id: "costo", header: "Costo", align: "right", cell: (f) => <MoneyText value={f.costo} className="font-medium" /> },
  ];
  if (puedeEditar) {
    columnas.push({
      id: "acciones",
      header: <span className="sr-only">Acciones</span>,
      align: "right",
      className: "w-12",
      cell: (f) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="ghost" size="icon" aria-label={`Acciones de ${nombreDe(f.producto_id)}`}>
              <MoreHorizontal aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onSelect={() => {
                const p = productos.data?.get(f.producto_id);
                if (p !== undefined) setSheet({ producto: p, costoCents: toCents(f.costo) });
                else notifyError("Ese producto está dado de baja");
              }}
            >
              <Pencil aria-hidden="true" /> Cambiar costo
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => setAQuitar(f)}>
              <Trash2 aria-hidden="true" /> Quitar de la lista
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    });
  }

  const agregar = puedeEditar ? (
    <Button type="button" onClick={() => setSheet({ producto: null })}>
      <PackagePlus aria-hidden="true" /> Agregar producto
    </Button>
  ) : undefined;

  return (
    <section aria-label="Lista de precios" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Lista de precios</h2>
        {filas.length > 0 && agregar}
      </div>
      {lista.isError ? (
        <ErrorState title="No pudimos cargar la lista de precios" onRetry={() => void lista.refetch()} />
      ) : (
        <DataTable
          label="Lista de precios"
          columns={columnas}
          rows={lista.data === undefined ? undefined : filas}
          getRowKey={(f) => f.id}
          isLoading={lista.isLoading}
          empty={
            <EmptyState
              icon={PackagePlus}
              title="La lista está vacía"
              description={
                puedeEditar
                  ? "Agregá los productos que ofrece esta distribuidora con su costo."
                  : "Todavía no se cargaron productos para esta distribuidora."
              }
              action={agregar}
            />
          }
        />
      )}
      <PrecioSheet
        open={sheet !== null}
        onOpenChange={(open) => {
          if (!open) setSheet(null);
        }}
        distribuidoraId={distribuidoraId}
        producto={sheet?.producto ?? null}
        costoActualCents={sheet?.costoCents}
        enLista={enLista}
      />
      <ConfirmDialog
        open={aQuitar !== null}
        onOpenChange={(open) => {
          if (!open) setAQuitar(null);
        }}
        title="Quitar de la lista"
        description={`"${aQuitar === null ? "" : nombreDe(aQuitar.producto_id)}" deja de figurar en esta distribuidora. El producto y su costo actual no cambian.`}
        confirmLabel="Quitar de la lista"
        destructive
        onConfirm={() => void confirmarQuitar()}
      />
    </section>
  );
}
