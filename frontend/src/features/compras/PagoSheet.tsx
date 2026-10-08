import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactElement, useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useRegistrarPago } from "@/features/compras/api";
import { METODOS_PAGO, METODO_PAGO_LABEL, hoyISO } from "@/features/compras/format";
import { DistribuidoraSelect } from "@/features/distribuidoras/DistribuidoraSelect";
import { parseMontoInput } from "@/features/distribuidoras/montoInput";
import { ApiError } from "@/shared/api/errors";
import { centsToApi } from "@/shared/lib/money";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

const schema = z.object({
  distribuidora_id: z.string().min(1, "Elegí una distribuidora"),
  monto: z.string().refine((v) => parseMontoInput(v) !== null, "Ingresá un monto mayor a cero (hasta 2 decimales)"),
  metodo: z.enum(["efectivo", "transferencia", "cheque", "otro"]),
  fecha: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Ingresá la fecha"),
  nota: z.string().trim().max(500, "Máximo 500 caracteres"),
});
type FormValues = z.infer<typeof schema>;

const CAMPOS: ReadonlySet<string> = new Set<keyof FormValues>(["distribuidora_id", "monto", "metodo", "fecha", "nota"]);

function esCampo(campo: string): campo is keyof FormValues {
  return CAMPOS.has(campo);
}

function valoresIniciales(distribuidoraId: string): FormValues {
  return { distribuidora_id: distribuidoraId, monto: "", metodo: "transferencia", fecha: hoyISO(), nota: "" };
}

interface PagoSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  distribuidoraInicial?: string;
}

/** Registro de un pago a una distribuidora (solo dueña): independiente de los pedidos. */
export function PagoSheet({ open, onOpenChange, distribuidoraInicial = "" }: PagoSheetProps): ReactElement {
  const registrar = useRegistrarPago();
  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: valoresIniciales(distribuidoraInicial) });

  useEffect(() => {
    if (open) reset(valoresIniciales(distribuidoraInicial));
  }, [open, distribuidoraInicial, reset]);

  async function onSubmit(values: FormValues): Promise<void> {
    const cents = parseMontoInput(values.monto);
    if (cents === null) return;
    try {
      await registrar.mutateAsync({
        distribuidora_id: values.distribuidora_id,
        monto: centsToApi(cents),
        metodo: values.metodo,
        fecha: values.fecha,
        nota: values.nota === "" ? null : values.nota,
      });
      notifySuccess("Pago registrado");
      onOpenChange(false);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        notifyError("No pudimos registrar el pago");
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
          <SheetTitle>Registrar pago</SheetTitle>
          <SheetDescription>El pago se descuenta de la cuenta de la distribuidora, no de un pedido puntual.</SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-4">
            <FieldGroup className="gap-4">
              <Field data-invalid={errors.distribuidora_id !== undefined}>
                <FieldLabel htmlFor="pago-distribuidora">Distribuidora</FieldLabel>
                <Controller
                  control={control}
                  name="distribuidora_id"
                  render={({ field }) => (
                    <DistribuidoraSelect
                      id="pago-distribuidora"
                      value={field.value}
                      onChange={field.onChange}
                      aria-invalid={errors.distribuidora_id !== undefined}
                    />
                  )}
                />
                <FieldError>{errors.distribuidora_id?.message}</FieldError>
              </Field>
              <Field data-invalid={errors.monto !== undefined}>
                <FieldLabel htmlFor="pago-monto">Monto</FieldLabel>
                <Input
                  id="pago-monto"
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="Ej.: 50000"
                  aria-invalid={errors.monto !== undefined}
                  {...register("monto")}
                />
                <FieldError>{errors.monto?.message}</FieldError>
              </Field>
              <Field>
                <FieldLabel id="pago-metodo-label">Medio de pago</FieldLabel>
                <Controller
                  control={control}
                  name="metodo"
                  render={({ field }) => (
                    <ToggleGroup
                      type="single"
                      variant="outline"
                      value={field.value}
                      onValueChange={(v) => {
                        if (v !== "") field.onChange(v);
                      }}
                      aria-labelledby="pago-metodo-label"
                      className="flex-wrap"
                    >
                      {METODOS_PAGO.map((m) => (
                        <ToggleGroupItem key={m} value={m} className="h-10 px-4">
                          {METODO_PAGO_LABEL[m]}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                  )}
                />
              </Field>
              <Field data-invalid={errors.fecha !== undefined}>
                <FieldLabel htmlFor="pago-fecha">Fecha</FieldLabel>
                <Input id="pago-fecha" type="date" aria-invalid={errors.fecha !== undefined} {...register("fecha")} />
                <FieldError>{errors.fecha?.message}</FieldError>
              </Field>
              <Field data-invalid={errors.nota !== undefined}>
                <FieldLabel htmlFor="pago-nota">Nota (opcional)</FieldLabel>
                <Textarea id="pago-nota" rows={2} aria-invalid={errors.nota !== undefined} {...register("nota")} />
                <FieldError>{errors.nota?.message}</FieldError>
              </Field>
            </FieldGroup>
          </div>
          <SheetFooter className="flex-row justify-end gap-2 border-t">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner aria-hidden="true" />}
              Registrar pago
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
