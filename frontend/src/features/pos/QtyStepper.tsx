import { Minus, Plus } from "lucide-react";
import { type KeyboardEvent, type ReactElement, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface QtyStepperProps {
  nombre: string;
  cantidad: number;
  onChange: (cantidad: number) => void;
}

/** Stepper tactil de cantidad: -, campo editable (se confirma con Enter o al salir) y +. */
export function QtyStepper({ nombre, cantidad, onChange }: QtyStepperProps): ReactElement {
  const [borrador, setBorrador] = useState<string | null>(null);

  function confirmar(): void {
    if (borrador !== null) {
      const n = Number(borrador);
      if (borrador.trim() !== "" && Number.isFinite(n)) onChange(n);
      setBorrador(null);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>): void {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      confirmar();
    } else if (e.key === "Escape") {
      setBorrador(null);
    }
  }

  return (
    <div className="flex items-center gap-1">
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-9 pointer-coarse:size-11"
        aria-label={`Restar una unidad de ${nombre}`}
        disabled={cantidad <= 1}
        onClick={() => onChange(cantidad - 1)}
      >
        <Minus aria-hidden="true" />
      </Button>
      <Input
        type="text"
        inputMode="numeric"
        aria-label={`Cantidad de ${nombre}`}
        className="h-9 w-12 px-1 text-center tabular-nums pointer-coarse:h-11"
        value={borrador ?? String(cantidad)}
        onChange={(e) => setBorrador(e.target.value.replace(/\D/g, ""))}
        onFocus={(e) => e.currentTarget.select()}
        onBlur={confirmar}
        onKeyDown={onKeyDown}
      />
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-9 pointer-coarse:size-11"
        aria-label={`Sumar una unidad de ${nombre}`}
        onClick={() => onChange(cantidad + 1)}
      >
        <Plus aria-hidden="true" />
      </Button>
    </div>
  );
}
