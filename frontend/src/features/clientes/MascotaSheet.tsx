import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactElement, useEffect } from "react";
import { useController, useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { MascotaFields } from "@/features/clientes/MascotaFields";
import { useCrearMascota, useEditarMascota } from "@/features/clientes/api";
import {
  type MascotaFormValues,
  mascotaSchema,
  valoresMascotaDesde,
  valoresMascotaVacios,
} from "@/features/clientes/mascotaForm";
import { ApiError } from "@/shared/api/errors";
import type { Mascota } from "@/shared/api/types";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

interface MascotaSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clienteId: string;
  /** `null` = alta (ambos roles); con mascota = edicion (solo dueña). */
  mascota: Mascota | null;
}

const CAMPOS: ReadonlySet<string> = new Set<keyof MascotaFormValues>(["nombre", "tipo"]);

function esCampo(campo: string): campo is keyof MascotaFormValues {
  return CAMPOS.has(campo);
}

/** Alta/edicion de mascota en panel lateral; el `422` del servidor se marca en su campo. */
export function MascotaSheet({ open, onOpenChange, clienteId, mascota }: MascotaSheetProps): ReactElement {
  const esAlta = mascota === null;
  const crear = useCrearMascota(clienteId);
  const editar = useEditarMascota(clienteId);
  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<MascotaFormValues>({ resolver: zodResolver(mascotaSchema), defaultValues: valoresMascotaVacios() });

  const { field: tipo } = useController({ control, name: "tipo" });

  useEffect(() => {
    if (open) reset(mascota === null ? valoresMascotaVacios() : valoresMascotaDesde(mascota));
  }, [open, mascota, reset]);

  async function onSubmit(values: MascotaFormValues): Promise<void> {
    try {
      if (mascota === null) await crear.mutateAsync(values);
      else await editar.mutateAsync({ id: mascota.id, body: values });
      notifySuccess(mascota === null ? "Mascota agregada" : "Mascota actualizada");
      onOpenChange(false);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        notifyError("No pudimos guardar la mascota");
        return;
      }
      let marcado = false;
      for (const [campo, mensaje] of Object.entries(error.fieldErrors)) {
        if (esCampo(campo)) {
          setError(campo, { message: mensaje }, { shouldFocus: true });
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
          <SheetTitle>{esAlta ? "Agregar mascota" : "Editar mascota"}</SheetTitle>
          <SheetDescription>El nombre y el tipo son obligatorios.</SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-4">
            <FieldGroup className="gap-4">
              <MascotaFields
                idPrefix="mascota"
                nombreInput={register("nombre")}
                nombreError={errors.nombre?.message}
                tipoValue={tipo.value}
                onTipoChange={tipo.onChange}
                tipoError={errors.tipo?.message}
              />
            </FieldGroup>
          </div>
          <SheetFooter className="flex-row justify-end gap-2 border-t">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner aria-hidden="true" />}
              {esAlta ? "Guardar mascota" : "Guardar cambios"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
