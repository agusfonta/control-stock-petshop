import { useQueryClient } from "@tanstack/react-query";
import { ScanBarcode, Search, SearchX, X } from "lucide-react";
import { type KeyboardEvent, type ReactElement, type RefObject, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DEBOUNCE_MS,
  MIN_CHARS_BUSQUEDA,
  buscarProductosAhora,
  useBuscarProductos,
} from "@/features/pos/api";
import { ProductResultRow } from "@/features/pos/ProductResultRow";
import { resolveScan } from "@/features/pos/scan";
import { useCartStore } from "@/features/pos/useCartStore";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import type { Producto } from "@/shared/api/types";
import { cn } from "@/shared/lib/utils";

export interface Aviso {
  texto: string;
  tono: "ok" | "warn";
}

interface SearchPanelProps {
  inputRef: RefObject<HTMLInputElement | null>;
  aviso: Aviso | null;
  onAviso: (aviso: Aviso | null) => void;
  /** Producto agregado o tocado: lo deja como linea seleccionada del carrito. */
  onAdded: (productoId: string) => void;
}

/** Panel izquierdo: buscador grande (lector de barras + teclado) y resultados tactiles (UX2, UX3, D10). */
export function SearchPanel({ inputRef, aviso, onAviso, onAdded }: SearchPanelProps): ReactElement {
  const queryClient = useQueryClient();
  const addProduct = useCartStore((s) => s.addProduct);
  const lineas = useCartStore((s) => s.lineas);
  const [texto, setTexto] = useState("");
  const debounced = useDebouncedValue(texto, DEBOUNCE_MS);
  const busqueda = useBuscarProductos(debounced);
  const listaRef = useRef<HTMLDivElement>(null);

  const buscando = debounced.trim().length >= MIN_CHARS_BUSQUEDA;
  const items = buscando ? (busqueda.data?.items ?? []) : [];

  function volverAlBuscador(limpiar: boolean): void {
    if (limpiar) setTexto("");
    inputRef.current?.focus();
  }

  /** Escaneo/Enter limpia el buscador; el toque en una fila lo conserva para sumar mas unidades. */
  function agregar(producto: Producto, limpiar: boolean): void {
    const mensaje = addProduct(producto);
    onAdded(producto.id);
    onAviso(mensaje === null ? { texto: `Agregamos ${producto.nombre}`, tono: "ok" } : { texto: mensaje, tono: "warn" });
    if (limpiar) {
      volverAlBuscador(true);
    } else {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }

  async function enviar(): Promise<void> {
    const codigo = texto.trim();
    if (codigo === "") return;
    try {
      const pagina = await buscarProductosAhora(queryClient, codigo);
      const resultado = resolveScan(codigo, pagina.items);
      if (resultado.kind === "agregar") {
        agregar(resultado.producto, true);
      } else if (resultado.kind === "sin-resultados") {
        onAviso({ texto: `No encontramos el código ${resultado.texto}`, tono: "warn" });
        inputRef.current?.select();
      }
    } catch {
      onAviso({ texto: "No pudimos buscar. Revisá la conexión e intentá de nuevo.", tono: "warn" });
    }
  }

  function enfocarResultado(indice: number): void {
    const botones = listaRef.current?.querySelectorAll<HTMLButtonElement>("button[data-result]:not(:disabled)");
    botones?.[indice]?.focus();
  }

  function onInputKeyDown(e: KeyboardEvent<HTMLInputElement>): void {
    if (e.key === "Enter") {
      e.preventDefault();
      void enviar();
    } else if (e.key === "Escape" && texto !== "") {
      e.preventDefault();
      setTexto("");
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      enfocarResultado(0);
    }
  }

  function onListKeyDown(e: KeyboardEvent<HTMLDivElement>): void {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const botones = Array.from(
      listaRef.current?.querySelectorAll<HTMLButtonElement>("button[data-result]:not(:disabled)") ?? [],
    );
    const actual = botones.findIndex((b) => b === document.activeElement);
    if (actual === -1) return;
    e.preventDefault();
    if (e.key === "ArrowUp" && actual === 0) inputRef.current?.focus();
    else botones[e.key === "ArrowDown" ? Math.min(actual + 1, botones.length - 1) : actual - 1]?.focus();
  }

  return (
    <section aria-label="Productos" className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="space-y-2">
        <InputGroup className="h-14 rounded-xl bg-card text-lg">
          <InputGroupAddon>
            <Search aria-hidden="true" className="size-5" />
          </InputGroupAddon>
          <InputGroupInput
            ref={inputRef}
            type="search"
            role="searchbox"
            aria-label="Buscar producto o escanear código"
            placeholder="Buscá por nombre o escaneá el código de barras"
            className="h-full text-base md:text-lg"
            autoFocus
            autoComplete="off"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={onInputKeyDown}
          />
          {texto !== "" && (
            <InputGroupAddon align="inline-end">
              <InputGroupButton size="icon-sm" aria-label="Limpiar búsqueda" onClick={() => volverAlBuscador(true)}>
                <X aria-hidden="true" />
              </InputGroupButton>
            </InputGroupAddon>
          )}
        </InputGroup>
        <p
          role="status"
          aria-live="polite"
          className={cn(
            "min-h-5 px-1 text-sm",
            aviso?.tono === "warn" ? "font-medium text-warning" : "text-muted-foreground",
          )}
        >
          {aviso?.texto}
        </p>
      </div>

      <div ref={listaRef} onKeyDown={onListKeyDown} className="min-h-0 flex-1 space-y-2 overflow-y-auto pb-2">
        {!buscando && (
          <EmptyState
            icon={ScanBarcode}
            title="Buscá o escaneá un producto"
            description="Escribí al menos 2 letras del nombre, o pasá el lector por el código y presioná Enter."
            className="border-dashed"
          />
        )}
        {buscando && busqueda.isPending && (
          <div aria-busy="true" aria-label="Buscando productos" className="space-y-2">
            {[0, 1, 2, 3].map((n) => (
              <Skeleton key={n} className="h-[4.5rem] w-full rounded-lg" />
            ))}
          </div>
        )}
        {buscando && busqueda.isError && (
          <ErrorState
            title="No pudimos buscar productos"
            onRetry={() => {
              void busqueda.refetch();
            }}
          />
        )}
        {buscando && busqueda.isSuccess && items.length === 0 && (
          <EmptyState
            icon={SearchX}
            title={`No encontramos productos con "${debounced.trim()}"`}
            description="Revisá el nombre o probá con el código del producto."
            action={
              <Button type="button" variant="outline" onClick={() => volverAlBuscador(true)}>
                Nueva búsqueda
              </Button>
            }
          />
        )}
        {items.length > 0 && (
          <div className={cn("space-y-2 transition-opacity", busqueda.isPlaceholderData && "opacity-60")}>
            {items.map((p) => (
              <ProductResultRow
                key={p.id}
                producto={p}
                enCarrito={lineas.find((l) => l.productoId === p.id)?.cantidad ?? 0}
                onAdd={(producto) => agregar(producto, false)}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
