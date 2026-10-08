import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactElement, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { ProductoPicker } from "@/features/distribuidoras/ProductoPicker";
import { useAgregarPrecio, useCambiarCosto } from "@/features/distribuidoras/api";
import { fraccionAMargenPct, precioPreview } from "@/features/productos/pricing";
import { parseMontoInput } from "@/features/distribuidoras/montoInput";
import { ApiError } from "@/shared/api/errors";
import type { Producto } from "@/shared/api/types";
import { centsToApi, formatARS } from "@/shared/lib/money";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

export const MENSAJE_DUPLICADO = "Ese producto ya está en la lista de esta distribuidora";

const schema = z.object({
  producto_id: z.string().min(1, "Elegí un producto"),
  costo: z.string().refine((v) => parseMontoInput(v) !== null, "Ingresá un costo mayor a cero (hasta 2 decimales)"),
});
type FormValues = z.infer<typeof schema>;

interface PrecioSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  distribuidoraId: string;
  /** Alta: `null`. Cambio de costo: el producto de la fila. */
  producto: Producto | null;
  /** Producto ya presentes en la lista (no se ofrecen en el alta). */
  enLista: ReadonlySet<string>;
  costoActualCents?: number;
}

/** Agregar un producto a la lista de la distribuidora o cambiar su costo (solo dueña). */
export function PrecioSheet({
  open,
  onOpenChange,
  distribuidoraId,
  producto,
  enLista,
  costoActualCents,
}: PrecioSheetProps): ReactElement {
  const esAlta = producto === null;
  const [elegido, setElegido] = useState<Producto | null>(null);
  const agregar = useAgregarPrecio(distribuidoraId);
  const cambiar = useCambiarCosto(distribuidoraId);
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    setError,
    clearErrors,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { producto_id: "", costo: "" } });

  useEffect(() => {
    if (!open) return;
    setElegido(null);
    reset({
      producto_id: producto?.id ?? "",
      costo: costoActualCents === undefined ? "" : (costoActualCents / 100).toFixed(2).replace(".", ","),
    });
  }, [open, producto, costoActualCents, reset]);

  const costoCents = parseMontoInput(watch("costo"));
  const objetivo = producto ?? elegido;
  const preview = objetivo === null ? null : precioPreview(costoCents, fraccionAMargenPct(objetivo.margen_pct));

  async function onSubmit(values: FormValues): Promise<void> {
    const cents = parseMontoInput(values.costo);
    if (cents === null) return;
    const body = { producto_id: values.producto_id, costo: centsToApi(cents) };
    try {
      if (esAlta) await agregar.mutateAsync(body);
      else await cambiar.mutateAsync(body);
      notifySuccess(esAlta ? "Producto agregado a la lista" : "Costo actualizado");
      onOpenChange(false);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        notifyError("No pudimos guardar el costo");
        return;
      }
      if (error.status === 409) {
        setError("producto_id", { message: MENSAJE_DUPLICADO });
      } else if (error.fieldErrors.costo !== undefined) {
        setError("costo", { message: error.fieldErrors.costo });
      } else {
        notifyError(error.message);
      }
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        <SheetHeader className="border-b">
          <SheetTitle>{esAlta ? "Agregar producto a la lista" : "Cambiar costo"}</SheetTitle>
          <SheetDescription>
            {esAlta ? "Elegí el producto y cargá el costo que te cobra esta distribuidora." : (producto?.nombre ?? "")}
          </SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-4">
            <FieldGroup className="gap-4">
              {esAlta && (
                <Field data-invalid={errors.producto_id !== undefined}>
                  <FieldLabel>Producto</FieldLabel>
                  <ProductoPicker
                    excluir={enLista}
                    label={elegido === null ? "Buscar producto" : `${elegido.nombre} (${elegido.sku})`}
                    onSelect={(p) => {
                      setElegido(p);
                      setValue("producto_id", p.id, { shouldValidate: true });
                      clearErrors("producto_id");
                    }}
                  />
                  <FieldError>{errors.producto_id?.message}</FieldError>
                </Field>
              )}
              <Field data-invalid={errors.costo !== undefined}>
                <FieldLabel htmlFor="precio-costo">Costo</FieldLabel>
                <Input
                  id="precio-costo"
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="Ej.: 17500,00"
                  aria-invalid={errors.costo !== undefined}
                  {...register("costo")}
                />
                {preview !== null && (
                  <FieldDescription>
                    Con el margen actual del producto, el precio de venta sería{" "}
                    <strong>{formatARS(preview)}</strong>.
                  </FieldDescription>
                )}
                <FieldError>{errors.costo?.message}</FieldError>
              </Field>
            </FieldGroup>
          </div>
          <SheetFooter className="flex-row justify-end gap-2 border-t">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner aria-hidden="true" />}
              {esAlta ? "Agregar a la lista" : "Guardar costo"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
