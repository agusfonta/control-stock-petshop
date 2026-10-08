import { type ReactElement, useState } from "react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAnularVenta } from "@/features/ventas/api";
import { ApiError } from "@/shared/api/errors";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

const MOTIVO_MAX = 300;

interface AnularVentaDialogProps {
  ventaId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Anulación (dueña): motivo obligatorio (<= 300) y confirmación con el verbo concreto (UX6). */
export function AnularVentaDialog({ ventaId, open, onOpenChange }: AnularVentaDialogProps): ReactElement {
  const anular = useAnularVenta(ventaId);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<string | null>(null);

  function cambiarApertura(abierto: boolean): void {
    if (anular.isPending) return;
    if (!abierto) {
      setMotivo("");
      setError(null);
    }
    onOpenChange(abierto);
  }

  async function confirmar(): Promise<void> {
    const texto = motivo.trim();
    if (texto === "") {
      setError("Indicá el motivo");
      return;
    }
    try {
      await anular.mutateAsync(texto);
      notifySuccess("Venta anulada, stock devuelto");
      cambiarApertura(false);
    } catch (e) {
      notifyError(e instanceof ApiError ? e.message : "No pudimos anular la venta");
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={cambiarApertura}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Anular venta</AlertDialogTitle>
          <AlertDialogDescription>
            Se devuelve el stock de todos los productos de la venta. Esta acción queda registrada y no se puede deshacer.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-1.5">
          <label htmlFor="motivo-anulacion" className="text-sm font-medium">
            Motivo de la anulación
          </label>
          <Textarea
            id="motivo-anulacion"
            value={motivo}
            maxLength={MOTIVO_MAX}
            aria-invalid={error !== null}
            aria-describedby={error !== null ? "motivo-error" : undefined}
            onChange={(e) => {
              setMotivo(e.target.value);
              setError(null);
            }}
          />
          <div className="flex justify-between text-xs">
            <span id="motivo-error" role={error !== null ? "alert" : undefined} className="text-destructive">
              {error}
            </span>
            <span className="text-muted-foreground tabular-nums">
              {motivo.length}/{MOTIVO_MAX}
            </span>
          </div>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={anular.isPending}>Cancelar</AlertDialogCancel>
          <Button type="button" variant="destructive" disabled={anular.isPending} onClick={() => void confirmar()}>
            Anular venta
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
