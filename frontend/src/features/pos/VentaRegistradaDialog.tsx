import { CircleCheck, Printer } from "lucide-react";
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/kbd";
import { Comprobante } from "@/features/pos/Comprobante";
import { ComprobantePrint } from "@/features/pos/ComprobantePrint";
import type { Venta } from "@/shared/api/types";

export interface VentaRegistrada {
  venta: Venta;
  vueltoCents: number | null;
  clienteNombre: string | null;
}

interface VentaRegistradaDialogProps {
  registrada: VentaRegistrada | null;
  /** Cierra el comprobante (boton, Enter o Esc). */
  onNuevaVenta: () => void;
  /** Cuando el dialogo termino de cerrarse: ahi se devuelve el foco al buscador. */
  onCerrado: () => void;
}

/** Pantalla de exito (UX5): comprobante + "Imprimir" y "Nueva venta" (primario, Enter). */
export function VentaRegistradaDialog({ registrada, onNuevaVenta, onCerrado }: VentaRegistradaDialogProps): ReactElement {
  return (
    <>
      <Dialog open={registrada !== null} onOpenChange={(open) => !open && onNuevaVenta()}>
        <DialogContent
          className="flex max-h-[92svh] flex-col gap-4 sm:max-w-sm"
          onOpenAutoFocus={(e) => {
            e.preventDefault();
            document.getElementById("nueva-venta")?.focus();
          }}
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            onCerrado();
          }}
        >
          <div className="flex flex-col items-center gap-1 text-center">
            <CircleCheck aria-hidden="true" className="size-12 text-success motion-safe:animate-in motion-safe:zoom-in-50" />
            <DialogTitle className="text-xl">Venta registrada</DialogTitle>
            <DialogDescription>El stock ya se descontó. Podés imprimir el comprobante o seguir vendiendo.</DialogDescription>
          </div>
          {registrada !== null && (
            <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border bg-card p-3">
              <Comprobante
                venta={registrada.venta}
                clienteNombre={registrada.clienteNombre}
                vueltoCents={registrada.vueltoCents}
                className="mx-auto"
              />
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <Button type="button" variant="outline" size="lg" className="h-12" onClick={() => {
                window.print();
                // Despues de imprimir el Enter sigue significando "Nueva venta".
                document.getElementById("nueva-venta")?.focus();
              }}>
              <Printer aria-hidden="true" />
              Imprimir
            </Button>
            <Button id="nueva-venta" type="button" size="lg" className="h-12" onClick={onNuevaVenta}>
              Nueva venta
              <Kbd className="bg-primary-foreground/20 text-primary-foreground">Enter</Kbd>
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      {registrada !== null && (
        <ComprobantePrint
          venta={registrada.venta}
          clienteNombre={registrada.clienteNombre}
          vueltoCents={registrada.vueltoCents}
        />
      )}
    </>
  );
}
