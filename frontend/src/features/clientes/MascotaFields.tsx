import type { ReactElement } from "react";
import type { UseFormRegisterReturn } from "react-hook-form";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TIPOS_MASCOTA, TIPO_MASCOTA_LABEL } from "@/features/clientes/mascotaForm";
import type { TipoMascota } from "@/shared/api/types";

interface MascotaFieldsProps {
  /** Prefijo de los ids de los inputs (evita colisiones cuando conviven dos formularios). */
  idPrefix: string;
  nombreLabel?: string;
  tipoLabel?: string;
  nombreInput: UseFormRegisterReturn;
  nombreError: string | undefined;
  /** `""` = sin elegir (se muestra el placeholder). */
  tipoValue: TipoMascota | "";
  onTipoChange: (tipo: TipoMascota) => void;
  tipoError: string | undefined;
}

function esTipo(valor: string): valor is TipoMascota {
  return TIPOS_MASCOTA.some((t) => t === valor);
}

/** Campos nombre + tipo de una mascota, compartidos por `MascotaSheet` y el alta de cliente. */
export function MascotaFields({
  idPrefix,
  nombreLabel = "Nombre",
  tipoLabel = "Tipo",
  nombreInput,
  nombreError,
  tipoValue,
  onTipoChange,
  tipoError,
}: MascotaFieldsProps): ReactElement {
  return (
    <>
      <Field data-invalid={nombreError !== undefined}>
        <FieldLabel htmlFor={`${idPrefix}-nombre`}>{nombreLabel}</FieldLabel>
        <Input
          id={`${idPrefix}-nombre`}
          autoComplete="off"
          aria-invalid={nombreError !== undefined}
          {...nombreInput}
        />
        <FieldError>{nombreError}</FieldError>
      </Field>
      <Field data-invalid={tipoError !== undefined}>
        <FieldLabel htmlFor={`${idPrefix}-tipo`}>{tipoLabel}</FieldLabel>
        <Select
          value={tipoValue}
          onValueChange={(v) => {
            if (esTipo(v)) onTipoChange(v);
          }}
        >
          <SelectTrigger id={`${idPrefix}-tipo`} className="h-10 w-full" aria-invalid={tipoError !== undefined}>
            <SelectValue placeholder="Seleccionar" />
          </SelectTrigger>
          <SelectContent>
            {TIPOS_MASCOTA.map((t) => (
              <SelectItem key={t} value={t}>
                {TIPO_MASCOTA_LABEL[t]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <FieldError>{tipoError}</FieldError>
      </Field>
    </>
  );
}
