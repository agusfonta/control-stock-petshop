import { zodResolver } from "@hookform/resolvers/zod";
import type { ReactElement } from "react";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useMargenMinimo } from "@/features/productos/api";
import { fraccionAMargenPct, margenPctAFraccion, parseMargenPct, precioPreview } from "@/features/productos/pricing";
import { ApiError } from "@/shared/api/errors";
import type { Producto } from "@/shared/api/types";
import { formatARS, toCents } from "@/shared/lib/money";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

const schema = z.object({
  margen: z.string().refine((v) => parseMargenPct(v) !== null, "Ingresá el margen en % (ej. 35)"),
  stockMinimo: z.string().refine((v) => /^\d+$/.test(v.trim()), "Ingresá un número entero (0 o más)"),
});

type Values = z.infer<typeof schema>;

interface MargenMinimoDialogProps {
  producto: Producto | null;
  onOpenChange: (open: boolean) => void;
}

/** Cambio rapido de margen y stock minimo (PATCH `/productos/{id}/margen-minimo`). */
export function MargenMinimoDialog({ producto, onOpenChange }: MargenMinimoDialogProps): ReactElement {
  const mutation = useMargenMinimo();
  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { margen: "", stockMinimo: "" } });

  useEffect(() => {
    if (producto !== null) {
      reset({
        margen: String(fraccionAMargenPct(producto.margen_pct)),
        stockMinimo: String(producto.stock_minimo),
      });
    }
  }, [producto, reset]);

  const margen = useWatch({ control, name: "margen" });
  const preview =
    producto === null ? null : precioPreview(toCents(producto.costo), parseMargenPct(margen));

  async function onSubmit(values: Values): Promise<void> {
    if (producto === null) return;
    const pct = parseMargenPct(values.margen);
    if (pct === null) return;
    try {
      await mutation.mutateAsync({
        id: producto.id,
        body: { margen_pct: margenPctAFraccion(pct), stock_minimo: Number(values.stockMinimo.trim()) },
      });
      notifySuccess("Producto actualizado");
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError && error.fieldErrors.margen_pct !== undefined) {
        setError("margen", { message: error.fieldErrors.margen_pct });
      } else if (error instanceof ApiError && error.fieldErrors.stock_minimo !== undefined) {
        setError("stockMinimo", { message: error.fieldErrors.stock_minimo });
      } else {
        notifyError(error instanceof ApiError ? error.message : "No pudimos actualizar el producto");
      }
    }
  }

  return (
    <Dialog open={producto !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Margen y stock mínimo</DialogTitle>
          <DialogDescription>{producto?.nombre}</DialogDescription>
        </DialogHeader>
        <form noValidate onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FieldGroup className="gap-4">
            <Field data-invalid={errors.margen !== undefined}>
              <FieldLabel htmlFor="rapido-margen">Margen (%)</FieldLabel>
              <Input
                id="rapido-margen"
                inputMode="decimal"
                autoComplete="off"
                aria-invalid={errors.margen !== undefined}
                {...register("margen")}
              />
              <FieldError>{errors.margen?.message}</FieldError>
            </Field>
            <Field data-invalid={errors.stockMinimo !== undefined}>
              <FieldLabel htmlFor="rapido-minimo">Stock mínimo</FieldLabel>
              <Input
                id="rapido-minimo"
                inputMode="numeric"
                autoComplete="off"
                aria-invalid={errors.stockMinimo !== undefined}
                {...register("stockMinimo")}
              />
              <FieldError>{errors.stockMinimo?.message}</FieldError>
            </Field>
          </FieldGroup>
          <div className="flex items-center justify-between rounded-lg border bg-muted/40 px-4 py-3" aria-live="polite">
            <span className="text-sm text-muted-foreground">Nuevo precio de venta</span>
            <span className="text-lg font-semibold tabular-nums">{preview === null ? "—" : formatARS(preview)}</span>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner aria-hidden="true" />}
              Guardar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
