import { zodResolver } from "@hookform/resolvers/zod";
import type { ReactElement } from "react";
import { useEffect } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { useCrearProducto, useDistribuidorasActivas, useEditarProducto } from "@/features/productos/api";
import { parseMargenPct, precioPreview } from "@/features/productos/pricing";
import {
  type ProductoFormValues,
  SIN_DISTRIBUIDORA,
  UNIDADES,
  aPayload,
  aPayloadAlta,
  parseMontoCents,
  productoSchema,
  valoresDesdeProducto,
  valoresVacios,
} from "@/features/productos/productoForm";
import { ApiError } from "@/shared/api/errors";
import type { Producto } from "@/shared/api/types";
import { formatARS } from "@/shared/lib/money";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

interface ProductoSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `null` = alta; con producto = edicion. */
  producto: Producto | null;
}

/** Campo del servidor (Pydantic) -> campo del formulario. */
const CAMPOS_SERVIDOR: Record<string, keyof ProductoFormValues> = {
  sku: "sku",
  nombre: "nombre",
  marca: "marca",
  categoria: "categoria",
  unidad: "unidad",
  costo: "costo",
  margen_pct: "margen",
  stock_actual: "stockInicial",
  stock_minimo: "stockMinimo",
  distribuidora_default_id: "distribuidoraId",
};

/** Alta/edicion de producto en panel lateral (UX6): react-hook-form + zod, errores del servidor al campo. */
export function ProductoSheet({ open, onOpenChange, producto }: ProductoSheetProps): ReactElement {
  const esAlta = producto === null;
  const crear = useCrearProducto();
  const editar = useEditarProducto();
  const distribuidoras = useDistribuidorasActivas(open);
  const {
    register,
    control,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ProductoFormValues>({
    resolver: zodResolver(productoSchema),
    defaultValues: valoresVacios(),
  });

  useEffect(() => {
    if (open) reset(producto === null ? valoresVacios() : valoresDesdeProducto(producto));
  }, [open, producto, reset]);

  const [costo, margen] = useWatch({ control, name: ["costo", "margen"] });
  const preview = precioPreview(parseMontoCents(costo), parseMargenPct(margen));

  async function onSubmit(values: ProductoFormValues): Promise<void> {
    try {
      if (producto === null) {
        await crear.mutateAsync(aPayloadAlta(values));
        notifySuccess("Producto creado");
      } else {
        await editar.mutateAsync({ id: producto.id, body: aPayload(values) });
        notifySuccess("Producto actualizado");
      }
      onOpenChange(false);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        notifyError("No pudimos guardar el producto");
        return;
      }
      let marcado = false;
      if (error.status === 409) {
        setError("sku", { message: "Ya existe un producto con ese SKU" });
        marcado = true;
      }
      for (const [campo, mensaje] of Object.entries(error.fieldErrors)) {
        const destino = CAMPOS_SERVIDOR[campo];
        if (destino !== undefined) {
          setError(destino, { message: mensaje });
          marcado = true;
        }
      }
      if (!marcado) notifyError(error.message);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-lg">
        <SheetHeader className="border-b">
          <SheetTitle>{esAlta ? "Nuevo producto" : "Editar producto"}</SheetTitle>
          <SheetDescription>
            {esAlta
              ? "El precio de venta se calcula con el costo y el margen."
              : "El stock no se edita acá: cambia con ventas, pedidos y ajustes."}
          </SheetDescription>
        </SheetHeader>
        <form noValidate onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-4">
            <FieldGroup className="gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field data-invalid={errors.sku !== undefined}>
                  <FieldLabel htmlFor="producto-sku">SKU</FieldLabel>
                  <Input id="producto-sku" autoComplete="off" aria-invalid={errors.sku !== undefined} {...register("sku")} />
                  <FieldError>{errors.sku?.message}</FieldError>
                </Field>
                <Field>
                  <FieldLabel htmlFor="producto-unidad">Unidad</FieldLabel>
                  <Controller
                    control={control}
                    name="unidad"
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger id="producto-unidad" className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {UNIDADES.map((u) => (
                            <SelectItem key={u.value} value={u.value}>
                              {u.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </Field>
              </div>
              <Field data-invalid={errors.nombre !== undefined}>
                <FieldLabel htmlFor="producto-nombre">Nombre</FieldLabel>
                <Input id="producto-nombre" autoComplete="off" aria-invalid={errors.nombre !== undefined} {...register("nombre")} />
                <FieldError>{errors.nombre?.message}</FieldError>
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field data-invalid={errors.marca !== undefined}>
                  <FieldLabel htmlFor="producto-marca">Marca (opcional)</FieldLabel>
                  <Input id="producto-marca" autoComplete="off" {...register("marca")} />
                  <FieldError>{errors.marca?.message}</FieldError>
                </Field>
                <Field data-invalid={errors.categoria !== undefined}>
                  <FieldLabel htmlFor="producto-categoria">Categoría (opcional)</FieldLabel>
                  <Input id="producto-categoria" autoComplete="off" {...register("categoria")} />
                  <FieldError>{errors.categoria?.message}</FieldError>
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field data-invalid={errors.costo !== undefined}>
                  <FieldLabel htmlFor="producto-costo">Costo ($)</FieldLabel>
                  <Input
                    id="producto-costo"
                    inputMode="decimal"
                    autoComplete="off"
                    aria-invalid={errors.costo !== undefined}
                    {...register("costo")}
                  />
                  <FieldError>{errors.costo?.message}</FieldError>
                </Field>
                <Field data-invalid={errors.margen !== undefined}>
                  <FieldLabel htmlFor="producto-margen">Margen (%)</FieldLabel>
                  <Input
                    id="producto-margen"
                    inputMode="decimal"
                    autoComplete="off"
                    aria-invalid={errors.margen !== undefined}
                    {...register("margen")}
                  />
                  <FieldError>{errors.margen?.message}</FieldError>
                </Field>
              </div>
              <div className="flex items-center justify-between rounded-lg border bg-muted/40 px-4 py-3" aria-live="polite">
                <span className="text-sm text-muted-foreground">Precio de venta</span>
                <span className="text-xl font-semibold tabular-nums" data-testid="precio-preview">
                  {preview === null ? "—" : formatARS(preview)}
                </span>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {esAlta && (
                  <Field data-invalid={errors.stockInicial !== undefined}>
                    <FieldLabel htmlFor="producto-stock-inicial">Stock inicial</FieldLabel>
                    <Input
                      id="producto-stock-inicial"
                      inputMode="numeric"
                      autoComplete="off"
                      aria-invalid={errors.stockInicial !== undefined}
                      {...register("stockInicial")}
                    />
                    <FieldError>{errors.stockInicial?.message}</FieldError>
                  </Field>
                )}
                <Field data-invalid={errors.stockMinimo !== undefined}>
                  <FieldLabel htmlFor="producto-stock-minimo">Stock mínimo</FieldLabel>
                  <Input
                    id="producto-stock-minimo"
                    inputMode="numeric"
                    autoComplete="off"
                    aria-invalid={errors.stockMinimo !== undefined}
                    {...register("stockMinimo")}
                  />
                  <FieldError>{errors.stockMinimo?.message}</FieldError>
                </Field>
              </div>
              <Field>
                <FieldLabel htmlFor="producto-distribuidora">Distribuidora por defecto</FieldLabel>
                <Controller
                  control={control}
                  name="distribuidoraId"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="producto-distribuidora" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={SIN_DISTRIBUIDORA}>Sin distribuidora</SelectItem>
                        {(distribuidoras.data ?? []).map((d) => (
                          <SelectItem key={d.id} value={d.id}>
                            {d.nombre}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                <FieldDescription>Se usa para sugerir pedidos de reposición.</FieldDescription>
              </Field>
            </FieldGroup>
          </div>
          <SheetFooter className="flex-row justify-end gap-2 border-t">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner aria-hidden="true" />}
              {esAlta ? "Crear producto" : "Guardar cambios"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
