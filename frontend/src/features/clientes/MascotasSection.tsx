import { PawPrint, Pencil, Plus, RotateCw, Trash2 } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MascotaSheet } from "@/features/clientes/MascotaSheet";
import { useBajaMascota, useMascotas } from "@/features/clientes/api";
import { TIPO_MASCOTA_LABEL } from "@/features/clientes/mascotaForm";
import { ApiError } from "@/shared/api/errors";
import type { Mascota } from "@/shared/api/types";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { useCan } from "@/shared/lib/permissions";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

/**
 * Mascotas activas del cliente: alta para ambos roles; editar y dar de baja solo la dueña.
 * Con el cliente dado de baja (`activo === false`) la sección es de solo lectura.
 */
export function MascotasSection({ clienteId, activo }: { clienteId: string; activo: boolean }): ReactElement {
  const puedeEditar = useCan("clientes.editar") && activo;
  const mascotas = useMascotas(clienteId);
  const baja = useBajaMascota(clienteId);
  const [sheet, setSheet] = useState<{ mascota: Mascota | null } | null>(null);
  const [aBaja, setABaja] = useState<Mascota | null>(null);

  async function confirmarBaja(): Promise<void> {
    if (aBaja === null) return;
    try {
      await baja.mutateAsync(aBaja.id);
      notifySuccess("Mascota dada de baja");
    } catch (error) {
      notifyError(error instanceof ApiError ? error.message : "No pudimos dar de baja la mascota");
    } finally {
      setABaja(null);
    }
  }

  const agregar = activo ? (
    <Button
      type="button"
      variant="outline"
      size="sm"
      disabled={mascotas.isLoading}
      onClick={() => setSheet({ mascota: null })}
    >
      <Plus aria-hidden="true" /> Agregar mascota
    </Button>
  ) : undefined;
  const lista = mascotas.data;
  const vacia = lista !== undefined && lista.length === 0;

  return (
    <section aria-labelledby="mascotas-titulo" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="mascotas-titulo" className="text-lg font-semibold">
          Mascotas
        </h2>
        {!vacia && agregar}
      </div>
      {mascotas.isLoading && (
        <Skeleton role="status" aria-busy="true" aria-label="Cargando mascotas" className="h-16 w-full rounded-xl" />
      )}
      {mascotas.isError && lista === undefined && (
        <ErrorState title="No pudimos cargar las mascotas" onRetry={() => void mascotas.refetch()} />
      )}
      {mascotas.isError && lista !== undefined && (
        <Alert variant="destructive" className="items-center">
          <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
            <p>No pudimos actualizar las mascotas</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="text-foreground"
              onClick={() => void mascotas.refetch()}
            >
              <RotateCw aria-hidden="true" />
              Reintentar
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {vacia && (
        <EmptyState
          icon={PawPrint}
          title="Sin mascotas registradas"
          description={activo ? "Agregá a sus mascotas para conocer mejor a este cliente." : undefined}
          action={agregar}
        />
      )}
      {lista !== undefined && lista.length > 0 && (
        <ul className="divide-y rounded-xl border" aria-label="Mascotas">
          {lista.map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-2 px-4 py-2 text-sm">
              <span>{`${m.nombre} · ${TIPO_MASCOTA_LABEL[m.tipo]}`}</span>
              {puedeEditar && (
                <span className="flex gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Editar a ${m.nombre}`}
                    onClick={() => setSheet({ mascota: m })}
                  >
                    <Pencil aria-hidden="true" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Dar de baja a ${m.nombre}`}
                    onClick={() => setABaja(m)}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {activo && (
        <MascotaSheet
          open={sheet !== null}
          onOpenChange={(open) => {
            if (!open) setSheet(null);
          }}
          clienteId={clienteId}
          mascota={sheet?.mascota ?? null}
        />
      )}
      <ConfirmDialog
        open={aBaja !== null}
        onOpenChange={(open) => {
          if (!open) setABaja(null);
        }}
        title="Dar de baja la mascota"
        description={`"${aBaja?.nombre ?? ""}" deja de aparecer en la ficha del cliente.`}
        confirmLabel="Dar de baja"
        destructive
        onConfirm={() => void confirmarBaja()}
      />
    </section>
  );
}
