import { MoreHorizontal, Pencil, Trash2, UserPlus, UserSearch } from "lucide-react";
import { type ReactElement, useEffect, useState } from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ClienteSheet } from "@/features/clientes/ClienteSheet";
import { PAGE_SIZE, useBajaCliente, useClientes } from "@/features/clientes/api";
import { ApiError } from "@/shared/api/errors";
import { TIPO_MASCOTA_LABEL } from "@/features/clientes/mascotaForm";
import type { Cliente, ClienteListItem } from "@/shared/api/types";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { PageHeader } from "@/shared/components/PageHeader";
import { SearchField } from "@/shared/components/SearchField";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { useCan } from "@/shared/lib/permissions";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

/** Listado de clientes: alta para ambos roles; edicion y baja solo con `clientes.editar`. */
export function ClientesPage(): ReactElement {
  const puedeEditar = useCan("clientes.editar");
  const [busqueda, setBusqueda] = useState("");
  const q = useDebouncedValue(busqueda.trim(), 250);
  const [page, setPage] = useState(1);
  const [sheet, setSheet] = useState<{ cliente: Cliente | null } | null>(null);
  const [baja, setBaja] = useState<Cliente | null>(null);
  const clientes = useClientes({ page, q });
  const bajaMutation = useBajaCliente();

  useEffect(() => {
    setPage(1);
  }, [q]);

  // Pagina fuera de rango (p. ej. tras dar de baja al ultimo de la ultima pagina): volver a la ultima con datos.
  const total = clientes.data?.total ?? 0;
  const vacioFueraDeRango =
    !clientes.isLoading && clientes.data !== undefined && clientes.data.items.length === 0 && total > 0 && page > 1;
  useEffect(() => {
    if (vacioFueraDeRango) setPage(Math.max(1, Math.ceil(total / PAGE_SIZE)));
  }, [vacioFueraDeRango, total]);

  async function confirmarBaja(): Promise<void> {
    if (baja === null) return;
    try {
      await bajaMutation.mutateAsync(baja.id);
      notifySuccess("Cliente dado de baja");
    } catch (error) {
      notifyError(error instanceof ApiError ? error.message : "No pudimos dar de baja el cliente");
    } finally {
      setBaja(null);
    }
  }

  const columnas: DataTableColumn<ClienteListItem>[] = [
    {
      id: "nombre",
      header: "Nombre",
      cell: (c) => (
        <Link
          to={`/clientes/${c.id}`}
          className="font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {c.nombre}
        </Link>
      ),
    },
    { id: "telefono", header: "Teléfono", cell: (c) => c.telefono ?? <span className="text-muted-foreground">—</span> },
    { id: "email", header: "Email", cell: (c) => c.email ?? <span className="text-muted-foreground">—</span> },
    { id: "direccion", header: "Dirección", cell: (c) => c.direccion ?? <span className="text-muted-foreground">—</span> },
    {
      id: "mascotas",
      header: "Mascotas",
      cell: (c) =>
        c.mascotas.length === 0 ? (
          <span className="text-muted-foreground">—</span>
        ) : (
          c.mascotas.map((m) => `${m.nombre} (${TIPO_MASCOTA_LABEL[m.tipo]})`).join(", ")
        ),
    },
  ];
  if (puedeEditar) {
    columnas.push({
      id: "acciones",
      header: <span className="sr-only">Acciones</span>,
      align: "right",
      className: "w-12",
      cell: (c) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="ghost" size="icon" aria-label={`Acciones de ${c.nombre}`}>
              <MoreHorizontal aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setSheet({ cliente: c })}>
              <Pencil aria-hidden="true" /> Editar
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => setBaja(c)}>
              <Trash2 aria-hidden="true" /> Dar de baja
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    });
  }

  const hayBusqueda = q !== "";
  const nuevo = (
    <Button type="button" onClick={() => setSheet({ cliente: null })}>
      <UserPlus aria-hidden="true" /> Nuevo cliente
    </Button>
  );

  return (
    <>
      <PageHeader title="Clientes" description="Datos de contacto e historial de compras." actions={nuevo} />
      <div className="space-y-4">
        <SearchField
          value={busqueda}
          onChange={setBusqueda}
          label="Buscar clientes"
          placeholder="Buscar por nombre, email o teléfono"
          maxLength={100}
        />
        {clientes.isError && clientes.data === undefined ? (
          <ErrorState title="No pudimos cargar los clientes" onRetry={() => void clientes.refetch()} />
        ) : (
          <DataTable
            label="Clientes"
            columns={columnas}
            rows={clientes.data?.items}
            getRowKey={(c) => c.id}
            isLoading={clientes.isLoading}
            empty={
              <EmptyState
                icon={hayBusqueda ? UserSearch : UserPlus}
                title={hayBusqueda ? "No encontramos clientes" : "Todavía no hay clientes"}
                description={
                  hayBusqueda
                    ? `Ningún cliente coincide con "${q}". Probá con otro nombre, email o teléfono.`
                    : "Cargá el primero para asociarlo a sus compras."
                }
                action={hayBusqueda ? undefined : nuevo}
              />
            }
            pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
          />
        )}
      </div>
      <ClienteSheet
        open={sheet !== null}
        onOpenChange={(open) => {
          if (!open) setSheet(null);
        }}
        cliente={sheet?.cliente ?? null}
      />
      <ConfirmDialog
        open={baja !== null}
        onOpenChange={(open) => {
          if (!open) setBaja(null);
        }}
        title="Dar de baja al cliente"
        description={`"${baja?.nombre ?? ""}" deja de aparecer en el listado y en el POS. Su historial de ventas se conserva.`}
        confirmLabel="Dar de baja"
        destructive
        onConfirm={() => void confirmarBaja()}
      />
    </>
  );
}
