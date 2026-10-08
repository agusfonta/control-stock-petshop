import { zodResolver } from "@hookform/resolvers/zod";
import { Minus, Plus } from "lucide-react";
import { type ReactElement, useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useAjustarStock } from "@/features/productos/api";
import { type AjusteValues, crearAjusteSchema, parseDelta, stockResultante } from "@/features/stock/ajuste";
import { ApiError } from "@/shared/api/errors";
import type { Producto } from "@/shared/api/types";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

interface AjusteStockDialogProps {
  producto: Pick<Producto, "id" | "nombre" | "sku" | "stock_actual"> | null;
  onOpenChange: (open: boolean) => void;
}

/** "Ajustar stock" (solo dueña): diferencia != 0, motivo obligatorio y stock resultante a la vista. */
export function AjusteStockDialog({ producto, onOpenChange }: AjusteStockDialogProps): ReactElement {
  const stockActual = producto?.stock_actual ?? 0;
  const schema = useMemo(() => crearAjusteSchema(stockActual), [stockActual]);
  const ajustar = useAjustarStock();
  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<AjusteValues>({ resolver: zodResolver(schema), defaultValues: { delta: "", motivo: "" } });

  useEffect(() => {
    if (producto !== null) reset({ delta: "", motivo: "" });
  }, [producto?.id, reset]);

  const delta = useWatch({ control, name: "delta" });
  const resultante = stockResultante(stockActual, delta);

  function mover(paso: number): void {
    const actual = parseDelta(delta) ?? 0;
    setValue("delta", String(actual + paso), { shouldValidate: delta !== "" });
  }

  async function onSubmit(values: AjusteValues): Promise<void> {
    const cantidad = parseDelta(values.delta);
    if (producto === null || cantidad === null) return;
    try {
      const res = await ajustar.mutateAsync({
        id: producto.id,
        body: { cantidad_delta: cantidad, motivo: values.motivo.trim() },
      });
      notifySuccess(`Stock ajustado: ${res.movimiento.stock_previo} → ${res.movimiento.stock_nuevo}`);
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        setError("delta", { message: error.fieldErrors.cantidad_delta ?? error.message });
        if (error.fieldErrors.motivo !== undefined) setError("motivo", { message: error.fieldErrors.motivo });
      } else {
        notifyError(error instanceof ApiError ? error.message : "No pudimos ajustar el stock");
      }
    }
  }

  return (
    <Dialog open={producto !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Ajustar stock</DialogTitle>
          <DialogDescription>
            {producto?.nombre} · stock actual {stockActual}
          </DialogDescription>
        </DialogHeader>
        <form noValidate onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FieldGroup className="gap-4">
            <Field data-invalid={errors.delta !== undefined}>
              <FieldLabel htmlFor="ajuste-delta">Diferencia</FieldLabel>
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" size="icon-lg" aria-label="Restar una unidad" onClick={() => mover(-1)}>
                  <Minus aria-hidden="true" />
                </Button>
                <Input
                  id="ajuste-delta"
                  autoComplete="off"
                  placeholder="-2 o 5"
                  className="h-10 text-center text-base tabular-nums"
                  aria-invalid={errors.delta !== undefined}
                  {...register("delta")}
                />
                <Button type="button" variant="outline" size="icon-lg" aria-label="Sumar una unidad" onClick={() => mover(1)}>
                  <Plus aria-hidden="true" />
                </Button>
              </div>
              <FieldDescription>Negativo para restar (rotura, vencido), positivo para sumar.</FieldDescription>
              <FieldError>{errors.delta?.message}</FieldError>
            </Field>
            <Field data-invalid={errors.motivo !== undefined}>
              <FieldLabel htmlFor="ajuste-motivo">Motivo</FieldLabel>
              <Textarea
                id="ajuste-motivo"
                rows={2}
                placeholder="Ej.: rotura, conteo de inventario"
                aria-invalid={errors.motivo !== undefined}
                {...register("motivo")}
              />
              <FieldError>{errors.motivo?.message}</FieldError>
            </Field>
          </FieldGroup>
          <div className="flex items-center justify-between rounded-lg border bg-muted/40 px-4 py-3" aria-live="polite">
            <span className="text-sm text-muted-foreground">Stock resultante</span>
            <span className="text-lg font-semibold tabular-nums">
              {resultante === null ? "—" : `Quedará en ${resultante}`}
            </span>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner aria-hidden="true" />}
              Confirmar ajuste
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
