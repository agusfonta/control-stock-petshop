import { ShoppingCart } from "lucide-react";
import { type ReactElement, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerTitle } from "@/components/ui/drawer";
import { Kbd } from "@/components/ui/kbd";
import { totalCents, unidadesTotales } from "@/features/pos/cart";
import { CartPanel } from "@/features/pos/CartPanel";
import { CheckoutSheet } from "@/features/pos/CheckoutSheet";
import { type Aviso, SearchPanel } from "@/features/pos/SearchPanel";
import { useCartStore } from "@/features/pos/useCartStore";
import { usePosShortcuts } from "@/features/pos/usePosShortcuts";
import { type VentaRegistrada, VentaRegistradaDialog } from "@/features/pos/VentaRegistradaDialog";
import type { Venta } from "@/shared/api/types";
import { useIsMobile } from "@/shared/hooks/use-mobile";
import { formatARS } from "@/shared/lib/money";

const AVISO_MS = 5000;

const ATAJOS: readonly { tecla: string; accion: string }[] = [
  { tecla: "F2", accion: "Buscar" },
  { tecla: "F9", accion: "Cobrar" },
  { tecla: "+ / -", accion: "Cantidad" },
  { tecla: "Esc", accion: "Limpiar" },
];

function AtajosVisibles(): ReactElement {
  return (
    <ul aria-label="Atajos de teclado" className="hidden flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground lg:flex">
      {ATAJOS.map((a) => (
        <li key={a.tecla} className="flex items-center gap-1.5">
          <Kbd>{a.tecla}</Kbd>
          {a.accion}
        </li>
      ))}
    </ul>
  );
}

/** Venta de mostrador: buscador + resultados a la izquierda, carrito fijo a la derecha (UX2, UX3). */
export function PosPage(): ReactElement {
  const inputRef = useRef<HTMLInputElement>(null);
  const verCarritoRef = useRef<HTMLButtonElement>(null);
  const isMobile = useIsMobile();
  const lineas = useCartStore((s) => s.lineas);
  const setQty = useCartStore((s) => s.setQty);
  const [aviso, setAviso] = useState<Aviso | null>(null);
  const [seleccionada, setSeleccionada] = useState<string | null>(null);
  const [carritoAbierto, setCarritoAbierto] = useState(false);
  const [cobrando, setCobrando] = useState(false);
  const [registrada, setRegistrada] = useState<VentaRegistrada | null>(null);

  useEffect(() => {
    if (aviso === null) return;
    const id = window.setTimeout(() => setAviso(null), AVISO_MS);
    return () => window.clearTimeout(id);
  }, [aviso]);

  const puedeCobrar = lineas.length > 0 && lineas.every((l) => l.disponible === undefined);

  const cobrar = useCallback((): void => {
    if (!puedeCobrar) return;
    setCarritoAbierto(false);
    setCobrando(true);
  }, [puedeCobrar]);

  const avisarTope = useCallback((mensaje: string | null): void => {
    setAviso(mensaje === null ? null : { texto: mensaje, tono: "warn" });
  }, []);

  const ajustarCantidad = useCallback(
    (delta: 1 | -1): boolean => {
      const linea = lineas.find((l) => l.productoId === seleccionada);
      if (linea === undefined) return false;
      avisarTope(setQty(linea.productoId, linea.cantidad + delta));
      return true;
    },
    [lineas, seleccionada, setQty, avisarTope],
  );

  const ventaCobrada = useCallback((venta: Venta, vueltoCents: number | null, clienteNombre: string | null): void => {
    setSeleccionada(null);
    setRegistrada({ venta, vueltoCents, clienteNombre });
  }, []);

  usePosShortcuts({ inputRef, onCobrar: cobrar, onAjustarCantidad: ajustarCantidad });

  const panelCarrito = (
    <CartPanel seleccionada={seleccionada} onSelect={setSeleccionada} onAviso={avisarTope} onCobrar={cobrar} />
  );

  return (
    <div
      data-cobrando={cobrando}
      className="flex min-h-0 flex-col gap-4 pb-24 md:grid md:h-[calc(100svh-7.5rem)] md:grid-cols-[minmax(0,1fr)_21rem] md:pb-0 lg:grid-cols-[minmax(0,1fr)_25rem] lg:gap-6"
    >
      <h1 className="sr-only">POS</h1>
      <div className="flex min-h-0 flex-col gap-3">
        <SearchPanel inputRef={inputRef} aviso={aviso} onAviso={setAviso} onAdded={setSeleccionada} />
        <AtajosVisibles />
      </div>

      {isMobile ? (
        <>
          <div className="fixed inset-x-0 bottom-0 z-30 flex items-center gap-3 border-t bg-card p-3 shadow-[0_-4px_12px_rgb(0_0_0/0.06)]">
            <div className="min-w-0 flex-1" aria-live="polite">
              <p className="text-xs text-muted-foreground">
                {unidadesTotales(lineas)} {unidadesTotales(lineas) === 1 ? "unidad" : "unidades"}
              </p>
              <p className="text-2xl leading-tight font-bold tabular-nums">{formatARS(totalCents(lineas))}</p>
            </div>
            <Button
              ref={verCarritoRef}
              type="button"
              size="lg"
              className="h-12 px-5 text-base"
              onClick={() => setCarritoAbierto(true)}
            >
              <ShoppingCart aria-hidden="true" />
              Ver carrito
            </Button>
          </div>
          <Drawer open={carritoAbierto} onOpenChange={setCarritoAbierto}>
            <DrawerContent className="h-[88svh]">
              <DrawerTitle className="sr-only">Carrito</DrawerTitle>
              <DrawerDescription className="sr-only">Productos, cliente y total de la venta en curso.</DrawerDescription>
              <div className="min-h-0 flex-1 p-3">{panelCarrito}</div>
            </DrawerContent>
          </Drawer>
        </>
      ) : (
        <aside className="min-h-0">{panelCarrito}</aside>
      )}

      <CheckoutSheet
        open={cobrando}
        onOpenChange={setCobrando}
        onSuccess={ventaCobrada}
        onCloseAutoFocus={(e) => {
          // Sin boton disparador, Radix dejaria el foco en <body>. Si hubo venta, el comprobante maneja el suyo.
          e.preventDefault();
          if (registrada !== null) return;
          (isMobile ? verCarritoRef.current : inputRef.current)?.focus();
        }}
      />
      <VentaRegistradaDialog
        registrada={registrada}
        onNuevaVenta={() => {
          setRegistrada(null);
          // Despues del render: con el dialogo aun montado su trampa de foco devolveria el foco al boton.
          window.setTimeout(() => inputRef.current?.focus(), 0);
        }}
        onCerrado={() => inputRef.current?.focus()}
      />
    </div>
  );
}
