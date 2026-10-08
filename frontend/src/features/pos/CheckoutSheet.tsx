import { type ReactElement, useRef, useState } from "react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { CheckoutForm } from "@/features/pos/CheckoutForm";
import type { Venta } from "@/shared/api/types";

interface CheckoutSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `vueltoCents` es solo informativo y solo existe en la venta recien cobrada. */
  onSuccess: (venta: Venta, vueltoCents: number | null, clienteNombre: string | null) => void;
  /** Al terminar de cerrarse; sirve para decidir adonde vuelve el foco (el panel no tiene boton disparador). */
  onCloseAutoFocus?: (event: Event) => void;
}

/** Panel lateral de cobro (UX4): medios como botones, "Paga con", vuelto y pagos divididos. */
export function CheckoutSheet({ open, onOpenChange, onSuccess, onCloseAutoFocus }: CheckoutSheetProps): ReactElement {
  const contentRef = useRef<HTMLDivElement>(null);
  // Cada apertura monta un formulario nuevo, aunque la animacion de cierre anterior no haya terminado.
  const [estabaAbierto, setEstabaAbierto] = useState(open);
  const [apertura, setApertura] = useState(0);
  if (open !== estabaAbierto) {
    setEstabaAbierto(open);
    if (open) setApertura((n) => n + 1);
  }
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        ref={contentRef}
        className="w-full gap-0 sm:max-w-md"
        onCloseAutoFocus={onCloseAutoFocus}
        onOpenAutoFocus={(e) => {
          // Teclado primero: el foco va a "Paga con" (o al primer monto) para cobrar sin mouse.
          e.preventDefault();
          const campo =
            contentRef.current?.querySelector<HTMLInputElement>("#paga-con:not(:disabled)") ??
            contentRef.current?.querySelector<HTMLInputElement>("input:not(:disabled)");
          campo?.focus();
        }}
      >
        <SheetHeader>
          <SheetTitle className="text-xl">Cobrar</SheetTitle>
          <SheetDescription>Elegí cómo paga el cliente. Podés dividir el total en hasta 5 pagos.</SheetDescription>
        </SheetHeader>
        <CheckoutForm key={apertura} onCerrar={() => onOpenChange(false)} onSuccess={onSuccess} />
      </SheetContent>
    </Sheet>
  );
}
