import { type ReactElement, useMemo } from "react";
import { createPortal } from "react-dom";
import { Comprobante } from "@/features/pos/Comprobante";
import "@/features/pos/print.css";
import type { Venta } from "@/shared/api/types";

function getPrintRoot(): HTMLElement {
  let el = document.getElementById("print-root");
  if (el === null) {
    el = document.createElement("div");
    el.id = "print-root";
    document.body.appendChild(el);
  }
  return el;
}

interface ComprobantePrintProps {
  venta: Venta;
  clienteNombre?: string | null;
  vueltoCents?: number | null;
}

/** Copia del comprobante en `#print-root`: la unica parte visible al imprimir (ver print.css). */
export function ComprobantePrint(props: ComprobantePrintProps): ReactElement {
  const root = useMemo(getPrintRoot, []);
  return createPortal(
    <div aria-hidden="true">
      <Comprobante {...props} />
    </div>,
    root,
  );
}
