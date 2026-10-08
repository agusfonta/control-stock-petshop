import type { ReactElement } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDistribuidorasIndex } from "@/features/distribuidoras/api";
import { cn } from "@/shared/lib/utils";

const TODAS = "__todas__";

interface DistribuidoraSelectProps {
  /** Id elegido; `""` = ninguna (o "Todas" si `conTodas`). */
  value: string;
  onChange: (id: string) => void;
  /** Agrega la opcion "Todas las distribuidoras" (filtros). */
  conTodas?: boolean;
  placeholder?: string;
  id?: string;
  "aria-label"?: string;
  "aria-invalid"?: boolean;
  className?: string;
}

/** Selector de distribuidora activa, alimentado por el indice cacheado (D12). */
export function DistribuidoraSelect({
  value,
  onChange,
  conTodas = false,
  placeholder = "Seleccionar distribuidora",
  id,
  "aria-label": ariaLabel,
  "aria-invalid": ariaInvalid,
  className,
}: DistribuidoraSelectProps): ReactElement {
  const indice = useDistribuidorasIndex();
  const opciones = [...(indice.data?.values() ?? [])].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  return (
    <Select
      value={value === "" && conTodas ? TODAS : value}
      onValueChange={(v) => onChange(v === TODAS ? "" : v)}
    >
      <SelectTrigger
        id={id}
        aria-label={ariaLabel}
        aria-invalid={ariaInvalid}
        className={cn("h-10 w-full sm:w-64", className)}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {conTodas && <SelectItem value={TODAS}>Todas las distribuidoras</SelectItem>}
        {opciones.map((d) => (
          <SelectItem key={d.id} value={d.id}>
            {d.nombre}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
