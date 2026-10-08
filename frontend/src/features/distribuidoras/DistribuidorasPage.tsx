import { MoreHorizontal, Pencil, Plus, Store, Trash2 } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Comparador } from "@/features/distribuidoras/Comparador";
import { DistribuidoraSheet } from "@/features/distribuidoras/DistribuidoraSheet";
import { PAGE_SIZE, useBajaDistribuidora, useDistribuidoras } from "@/features/distribuidoras/api";
import { ApiError } from "@/shared/api/errors";
import type { Distribuidora } from "@/shared/api/types";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { PageHeader } from "@/shared/components/PageHeader";
import { useCan } from "@/shared/lib/permissions";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

const link =
  "font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none";

const vacio = <span className="text-muted-foreground">—</span>;

/** Distribuidoras (ambos roles leen) y comparador de costos; ABM solo con `distribuidoras.editar`. */
export function DistribuidorasPage(): ReactElement {
  const puedeEditar = useCan("distribuidoras.editar");
  const [page, setPage] = useState(1);
  const [sheet, setSheet] = useState<{ distribuidora: Distribuidora | null } | null>(null);
  const [baja, setBaja] = useState<Distribuidora | null>(null);
  const distribuidoras = useDistribuidoras(page);
  const bajaMutation = useBajaDistribuidora();

  async function confirmarBaja(): Promise<void> {
    if (baja === null) return;
    try {
      await bajaMutation.mutateAsync(baja.id);
      notifySuccess("Distribuidora dada de baja");
    } catch (error) {
      notifyError(error instanceof ApiError ? error.message : "No pudimos dar de baja la distribuidora");
    } finally {
      setBaja(null);
    }
  }

  const columnas: DataTableColumn<Distribuidora>[] = [
    {
      id: "nombre",
      header: "Nombre",
      cell: (d) => (
        <Link to={`/distribuidoras/${d.id}`} className={link}>
          {d.nombre}
        </Link>
      ),
    },
    { id: "contacto", header: "Contacto", cell: (d) => d.contacto ?? vacio },
    { id: "cuit", header: "CUIT", cell: (d) => d.cuit ?? vacio },
    {
      id: "condiciones",
      header: "Condiciones",
      cell: (d) => <span className="line-clamp-1 max-w-64">{d.condiciones ?? vacio}</span>,
    },
  ];
  if (puedeEditar) {
    columnas.push({
      id: "acciones",
      header: <span className="sr-only">Acciones</span>,
      align: "right",
      className: "w-12",
      cell: (d) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="ghost" size="icon" aria-label={`Acciones de ${d.nombre}`}>
              <MoreHorizontal aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setSheet({ distribuidora: d })}>
              <Pencil aria-hidden="true" /> Editar
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => setBaja(d)}>
              <Trash2 aria-hidden="true" /> Dar de baja
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    });
  }

  const nueva = puedeEditar ? (
    <Button type="button" onClick={() => setSheet({ distribuidora: null })}>
      <Plus aria-hidden="true" /> Nueva distribuidora
    </Button>
  ) : undefined;

  return (
    <>
      <PageHeader
        title="Distribuidoras"
        description="Proveedores, sus listas de precios y el comparador de costos."
        actions={nueva}
      />
      <Tabs defaultValue="listado" className="gap-4">
        <TabsList>
          <TabsTrigger value="listado">Distribuidoras</TabsTrigger>
          <TabsTrigger value="comparador">Comparador de costos</TabsTrigger>
        </TabsList>
        <TabsContent value="listado" className="space-y-4">
          {distribuidoras.isError && distribuidoras.data === undefined ? (
            <ErrorState title="No pudimos cargar las distribuidoras" onRetry={() => void distribuidoras.refetch()} />
          ) : (
            <DataTable
              label="Distribuidoras"
              columns={columnas}
              rows={distribuidoras.data?.items}
              getRowKey={(d) => d.id}
              isLoading={distribuidoras.isLoading}
              empty={
                <EmptyState
                  icon={Store}
                  title="Todavía no hay distribuidoras"
                  description={
                    puedeEditar
                      ? "Cargá la primera para armar su lista de precios y hacerle pedidos."
                      : "La dueña todavía no cargó ninguna distribuidora."
                  }
                  action={nueva}
                />
              }
              pagination={{
                page,
                pageSize: PAGE_SIZE,
                total: distribuidoras.data?.total ?? 0,
                onPageChange: setPage,
              }}
            />
          )}
        </TabsContent>
        <TabsContent value="comparador">
          <Comparador />
        </TabsContent>
      </Tabs>
      <DistribuidoraSheet
        open={sheet !== null}
        onOpenChange={(open) => {
          if (!open) setSheet(null);
        }}
        distribuidora={sheet?.distribuidora ?? null}
      />
      <ConfirmDialog
        open={baja !== null}
        onOpenChange={(open) => {
          if (!open) setBaja(null);
        }}
        title="Dar de baja la distribuidora"
        description={`"${baja?.nombre ?? ""}" deja de aparecer en el listado y no se le podrán hacer pedidos nuevos. Sus pedidos y pagos anteriores se conservan.`}
        confirmLabel="Dar de baja"
        destructive
        onConfirm={() => void confirmarBaja()}
      />
    </>
  );
}
