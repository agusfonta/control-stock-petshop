import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactElement, useEffect } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useCrearDistribuidora, useEditarDistribuidora } from "@/features/distribuidoras/api";
import {
  type DistribuidoraFormValues,
  aPayloadDistribuidora,
  distribuidoraSchema,
  valoresDistribuidoraDesde,
  valoresDistribuidoraVacios,
} from "@/features/distribuidoras/distribuidoraForm";
import { ApiError } from "@/shared/api/errors";
import type { Distribuidora } from "@/shared/api/types";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

interface DistribuidoraSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `null` = alta. */
  distribuidora: Distribuidora | null;
}

const CAMPOS: ReadonlySet<string> = new Set<keyof DistribuidoraFormValues>([
  "nombre",
  "contacto",
  "cuit",
  "condiciones",
]);

function esCampo(campo: string): campo is keyof DistribuidoraFormValues {
  return CAMPOS.has(campo);
}

/** Alta/edicion de distribuidora en panel lateral (solo con `distribuidoras.editar`). */
export function DistribuidoraSheet({ open, onOpenChange, distribuidora }: DistribuidoraSheetProps): ReactElement {
  const esAlta = distribuidora === null;
  const crear = useCrearDistribuidora();
  const editar = useEditarDistribuidora();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<DistribuidoraFormValues>({
    resolver: zodResolver(distribuidoraSchema),
    defaultValues: valoresDistribuidoraVacios(),
  });

  useEffect(() => {
    if (open) reset(distribuidora === null ? valoresDistribuidoraVacios() : valoresDistribuidoraDesde(distribuidora));
  }, [open, distribuidora, reset]);

  async function onSubmit(values: DistribuidoraFormValues): Promise<void> {
    const body = aPayloadDistribuidora(values);
    try {
      if (distribuidora === null) await crear.mutateAsync(body);
      else await editar.mutateAsync({ id: distribuidora.id, body });
      notifySuccess(distribuidora === null ? "Distribuidora creada" : "Distribuidora actualizada");
      onOpenChange(false);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        notifyError("No pudimos guardar la distribuidora");
        return;
      }
      let marcado = false;
      for (const [campo, mensaje] of Object.entries(error.fieldErrors)) {
        if (esCampo(campo)) {
          setError(campo, { message: mensaje });
          marcado = true;
        }
      }
      if (!marcado) notifyError(error.message);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        <SheetHeader className="border-b">
          <SheetTitle>{esAlta ? "Nueva distribuidora" : "Editar distribuidora"}</SheetTitle>
          <SheetDescription>Solo el nombre es obligatorio.</SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-4">
            <FieldGroup className="gap-4">
              <Field data-invalid={errors.nombre !== undefined}>
                <FieldLabel htmlFor="dist-nombre">Nombre</FieldLabel>
                <Input id="dist-nombre" autoComplete="off" aria-invalid={errors.nombre !== undefined} {...register("nombre")} />
                <FieldError>{errors.nombre?.message}</FieldError>
              </Field>
              <Field data-invalid={errors.contacto !== undefined}>
                <FieldLabel htmlFor="dist-contacto">Contacto (opcional)</FieldLabel>
                <Input id="dist-contacto" autoComplete="off" aria-invalid={errors.contacto !== undefined} {...register("contacto")} />
                <FieldError>{errors.contacto?.message}</FieldError>
              </Field>
              <Field data-invalid={errors.cuit !== undefined}>
                <FieldLabel htmlFor="dist-cuit">CUIT (opcional)</FieldLabel>
                <Input id="dist-cuit" autoComplete="off" inputMode="numeric" aria-invalid={errors.cuit !== undefined} {...register("cuit")} />
                <FieldError>{errors.cuit?.message}</FieldError>
              </Field>
              <Field data-invalid={errors.condiciones !== undefined}>
                <FieldLabel htmlFor="dist-condiciones">Condiciones (opcional)</FieldLabel>
                <Textarea
                  id="dist-condiciones"
                  rows={3}
                  placeholder="Plazo de pago, mínimo de compra, días de reparto…"
                  aria-invalid={errors.condiciones !== undefined}
                  {...register("condiciones")}
                />
                <FieldError>{errors.condiciones?.message}</FieldError>
              </Field>
            </FieldGroup>
          </div>
          <SheetFooter className="flex-row justify-end gap-2 border-t">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner aria-hidden="true" />}
              {esAlta ? "Crear distribuidora" : "Guardar cambios"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
