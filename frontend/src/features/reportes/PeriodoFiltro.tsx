import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PRESET_LABEL, type Periodo, type PeriodoPreset, periodoPreset, toIsoDate } from "@/features/reportes/params";

interface PeriodoFiltroProps {
  value: Periodo;
  onChange: (periodo: Periodo) => void;
  /** Mensaje de `validarPeriodo` para mostrar junto a los campos. */
  error?: string | null;
}

const PRESETS: PeriodoPreset[] = ["7d", "30d", "mes"];

/** Periodo desde/hasta con atajos; vacio = ultimos 30 dias (default del servidor). */
export function PeriodoFiltro({ value, onChange, error }: PeriodoFiltroProps): ReactElement {
  const hoy = toIsoDate(new Date());
  return (
    <>
      <div className="space-y-1.5">
        <Label htmlFor="periodo-desde">Desde</Label>
        <Input
          id="periodo-desde"
          type="date"
          value={value.desde}
          max={hoy}
          aria-invalid={error ? true : undefined}
          onChange={(e) => onChange({ ...value, desde: e.target.value })}
          className="w-auto min-w-40"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="periodo-hasta">Hasta</Label>
        <Input
          id="periodo-hasta"
          type="date"
          value={value.hasta}
          max={hoy}
          aria-invalid={error ? true : undefined}
          onChange={(e) => onChange({ ...value, hasta: e.target.value })}
          className="w-auto min-w-40"
        />
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Períodos rápidos">
        {PRESETS.map((p) => (
          <Button key={p} type="button" variant="outline" onClick={() => onChange(periodoPreset(p))}>
            {PRESET_LABEL[p]}
          </Button>
        ))}
      </div>
      {error ? (
        <p role="alert" className="basis-full text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </>
  );
}
