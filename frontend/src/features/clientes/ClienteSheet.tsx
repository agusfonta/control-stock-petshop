import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactElement, useEffect } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { useCrearCliente, useEditarCliente } from "@/features/clientes/api";
import {
  type ClienteFormValues,
  aPayloadCliente,
  clienteSchema,
  valoresClienteDesde,
  valoresClienteVacios,
} from "@/features/clientes/clienteForm";
import { ApiError } from "@/shared/api/errors";
import type { Cliente } from "@/shared/api/types";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

interface ClienteSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `null` = alta; con cliente = edicion (solo dueña). */
  cliente: Cliente | null;
  onSaved?: (cliente: Cliente) => void;
}

const CAMPOS: ReadonlySet<string> = new Set<keyof ClienteFormValues>(["nombre", "telefono", "email", "direccion"]);

function esCampo(campo: string): campo is keyof ClienteFormValues {
  return CAMPOS.has(campo);
}

/** Alta/edicion de cliente en panel lateral; `409` de email y `422` van al campo (UX6). */
export function ClienteSheet({ open, onOpenChange, cliente, onSaved }: ClienteSheetProps): ReactElement {
  const esAlta = cliente === null;
  const crear = useCrearCliente();
  const editar = useEditarCliente();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ClienteFormValues>({ resolver: zodResolver(clienteSchema), defaultValues: valoresClienteVacios() });

  useEffect(() => {
    if (open) reset(cliente === null ? valoresClienteVacios() : valoresClienteDesde(cliente));
  }, [open, cliente, reset]);

  async function onSubmit(values: ClienteFormValues): Promise<void> {
    try {
      const body = aPayloadCliente(values);
      const guardado =
        cliente === null
          ? await crear.mutateAsync(body)
          : await editar.mutateAsync({ id: cliente.id, body });
      notifySuccess(cliente === null ? "Cliente creado" : "Cliente actualizado");
      onSaved?.(guardado);
      onOpenChange(false);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        notifyError("No pudimos guardar el cliente");
        return;
      }
      let marcado = false;
      if (error.status === 409) {
        setError("email", { message: "Ya existe un cliente con ese email" });
        marcado = true;
      }
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
          <SheetTitle>{esAlta ? "Nuevo cliente" : "Editar cliente"}</SheetTitle>
          <SheetDescription>Solo el nombre es obligatorio.</SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-4">
            <FieldGroup className="gap-4">
              <Field data-invalid={errors.nombre !== undefined}>
                <FieldLabel htmlFor="cliente-nombre">Nombre</FieldLabel>
                <Input id="cliente-nombre" autoComplete="off" aria-invalid={errors.nombre !== undefined} {...register("nombre")} />
                <FieldError>{errors.nombre?.message}</FieldError>
              </Field>
              <Field data-invalid={errors.telefono !== undefined}>
                <FieldLabel htmlFor="cliente-telefono">Teléfono (opcional)</FieldLabel>
                <Input
                  id="cliente-telefono"
                  type="tel"
                  inputMode="tel"
                  autoComplete="off"
                  aria-invalid={errors.telefono !== undefined}
                  {...register("telefono")}
                />
                <FieldError>{errors.telefono?.message}</FieldError>
              </Field>
              <Field data-invalid={errors.email !== undefined}>
                <FieldLabel htmlFor="cliente-email">Email (opcional)</FieldLabel>
                <Input
                  id="cliente-email"
                  type="email"
                  inputMode="email"
                  autoComplete="off"
                  aria-invalid={errors.email !== undefined}
                  {...register("email")}
                />
                <FieldError>{errors.email?.message}</FieldError>
              </Field>
              <Field data-invalid={errors.direccion !== undefined}>
                <FieldLabel htmlFor="cliente-direccion">Dirección (opcional)</FieldLabel>
                <Input
                  id="cliente-direccion"
                  autoComplete="off"
                  aria-invalid={errors.direccion !== undefined}
                  {...register("direccion")}
                />
                <FieldError>{errors.direccion?.message}</FieldError>
              </Field>
            </FieldGroup>
          </div>
          <SheetFooter className="flex-row justify-end gap-2 border-t">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner aria-hidden="true" />}
              {esAlta ? "Crear cliente" : "Guardar cambios"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
