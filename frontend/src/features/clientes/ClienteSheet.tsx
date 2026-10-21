import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { type ReactElement, useEffect, useRef } from "react";
import { type Control, type FieldErrors, type UseFormRegister, useController, useFieldArray, useForm } from "react-hook-form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { MascotaFields } from "@/features/clientes/MascotaFields";
import { useCrearCliente, useEditarCliente, useMascotas } from "@/features/clientes/api";
import {
  type ClienteFormValues,
  aPayloadCliente,
  clienteSchema,
  valoresClienteDesde,
  valoresClienteVacios,
} from "@/features/clientes/clienteForm";
import { valoresMascotaVacios } from "@/features/clientes/mascotaForm";
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

/** Campo del servidor (loc sin `body`) -> campo del formulario. */
const CAMPOS: Readonly<Record<string, keyof ClienteFormValues>> = {
  nombre: "nombre",
  telefono: "telefono",
  email: "email",
  direccion: "direccion",
  "mascota.nombre": "mascotaNombre",
  "mascota.tipo": "mascotaTipo",
};

const MASCOTA_FILA = /^mascotas\.(\d+)\.(nombre|tipo)$/;

interface MascotaFilaProps {
  index: number;
  /** Clave estable de la fila (`field.id` de useFieldArray). */
  fieldId: string;
  control: Control<ClienteFormValues>;
  register: UseFormRegister<ClienteFormValues>;
  errors: FieldErrors<ClienteFormValues>;
  onQuitar: () => void;
}

/** Fila editable de una mascota del cliente (necesita `useController` para el Select, por eso es un componente). */
function MascotaFila({ index, fieldId, control, register, errors, onQuitar }: MascotaFilaProps): ReactElement {
  const { field: tipo } = useController({ control, name: `mascotas.${index}.tipo` });
  const numero = index + 1;
  return (
    <div className="space-y-4 rounded-lg border p-3">
      <MascotaFields
        idPrefix={`cliente-mascota-${fieldId}`}
        nombreLabel={`Nombre de la mascota ${numero}`}
        tipoLabel={`Tipo de la mascota ${numero}`}
        nombreInput={register(`mascotas.${index}.nombre`)}
        nombreError={errors.mascotas?.[index]?.nombre?.message}
        tipoValue={tipo.value}
        onTipoChange={tipo.onChange}
        tipoError={errors.mascotas?.[index]?.tipo?.message}
      />
      <Button type="button" variant="outline" size="sm" onClick={onQuitar} aria-label={`Quitar mascota ${numero}`}>
        <Trash2 aria-hidden="true" /> Quitar
      </Button>
    </div>
  );
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
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ClienteFormValues>({ resolver: zodResolver(clienteSchema), defaultValues: valoresClienteVacios() });

  const { field: tipoMascota } = useController({ control, name: "mascotaTipo" });
  const filas = useFieldArray({ control, name: "mascotas" });
  const mascotas = useMascotas(cliente?.id ?? "", open && !esAlta);
  const mascotasVigentes = mascotas.data;
  /** `true` cuando las mascotas del servidor ya estan en el formulario (solo entonces viajan en el PUT). */
  const sembradas = useRef(false);

  useEffect(() => {
    if (!open) return;
    sembradas.current = false;
    reset(cliente === null ? valoresClienteVacios() : valoresClienteDesde(cliente));
  }, [open, cliente, reset]);

  // Las mascotas se cargan una sola vez por apertura: un refetch posterior no pisa lo que se esta editando.
  useEffect(() => {
    if (!open || cliente === null || sembradas.current || mascotasVigentes === undefined) return;
    sembradas.current = true;
    filas.replace(valoresClienteDesde(cliente, mascotasVigentes).mascotas);
  }, [open, cliente, mascotasVigentes, filas.replace]);

  async function onSubmit(values: ClienteFormValues): Promise<void> {
    try {
      const modo = cliente === null ? "alta" : sembradas.current ? "edicion-con-mascotas" : "edicion";
      const body = aPayloadCliente(values, modo);
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
      if (error.status === 409 && /dado de baja/i.test(error.message)) {
        notifyError(error.message);
        marcado = true;
      } else if (error.status === 409) {
        setError("email", { message: "Ya existe un cliente con ese email" }, { shouldFocus: true });
        marcado = true;
      }
      for (const [campo, mensaje] of Object.entries(error.fieldErrors)) {
        const fila = MASCOTA_FILA.exec(campo);
        if (fila !== null) {
          setError(`mascotas.${Number(fila[1])}.${fila[2] === "tipo" ? "tipo" : "nombre"}`, { message: mensaje }, { shouldFocus: true });
          marcado = true;
          continue;
        }
        const destino = CAMPOS[campo];
        if (destino !== undefined) {
          setError(destino, { message: mensaje }, { shouldFocus: true });
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
              {esAlta && (
                <FieldSet className="gap-4">
                  <FieldLegend variant="label">Mascota (opcional)</FieldLegend>
                  <MascotaFields
                    idPrefix="cliente-mascota"
                    nombreLabel="Nombre de la mascota"
                    tipoLabel="Tipo de mascota"
                    nombreInput={register("mascotaNombre")}
                    nombreError={errors.mascotaNombre?.message}
                    tipoValue={tipoMascota.value}
                    onTipoChange={tipoMascota.onChange}
                    tipoError={errors.mascotaTipo?.message}
                  />
                </FieldSet>
              )}
              {!esAlta && (
                <FieldSet className="gap-4">
                  <FieldLegend variant="label">Mascotas</FieldLegend>
                  {mascotas.isLoading && (
                    <Skeleton role="status" aria-busy="true" aria-label="Cargando mascotas" className="h-16 w-full rounded-xl" />
                  )}
                  {mascotas.isError && mascotasVigentes === undefined && (
                    <Alert>
                      <AlertDescription>
                        No pudimos cargar las mascotas. Podés guardar los datos del cliente; las mascotas no se modifican.
                      </AlertDescription>
                    </Alert>
                  )}
                  {mascotasVigentes !== undefined && (
                    <>
                      {filas.fields.map((fila, index) => (
                        <MascotaFila
                          key={fila.id}
                          fieldId={fila.id}
                          index={index}
                          control={control}
                          register={register}
                          errors={errors}
                          onQuitar={() => filas.remove(index)}
                        />
                      ))}
                      <Button type="button" variant="outline" onClick={() => filas.append(valoresMascotaVacios())}>
                        <Plus aria-hidden="true" /> Agregar mascota
                      </Button>
                    </>
                  )}
                </FieldSet>
              )}
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
