import { useQuery } from "@tanstack/react-query";
import { Package, Search } from "lucide-react";
import { type ReactElement, type ReactNode, useState } from "react";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { apiFetch } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type { Paginated, Producto } from "@/shared/api/types";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { cn } from "@/shared/lib/utils";

const MIN_CHARS = 2;
const DEBOUNCE_MS = 250;
const RESULTADOS = 20;

interface ProductoPickerProps {
  onSelect: (producto: Producto) => void;
  /** Texto del boton que abre el selector. */
  label?: ReactNode;
  /** Productos que no deben ofrecerse (ya agregados). */
  excluir?: ReadonlySet<string>;
  disabled?: boolean;
  className?: string;
}

/** Selector de producto: `Command` sobre `GET /productos/buscar` (min. 2 caracteres, debounce 250 ms). */
export function ProductoPicker({
  onSelect,
  label = "Elegir un producto",
  excluir,
  disabled = false,
  className,
}: ProductoPickerProps): ReactElement {
  const [open, setOpen] = useState(false);
  const [texto, setTexto] = useState("");
  const q = useDebouncedValue(texto.trim(), DEBOUNCE_MS);
  const habilitada = q.length >= MIN_CHARS;
  const busqueda = useQuery({
    queryKey: queryKeys.productos.buscar(q, { picker: true }),
    enabled: habilitada,
    queryFn: ({ signal }) =>
      apiFetch<Paginated<Producto>>("/productos/buscar", { query: { q, page: 1, page_size: RESULTADOS }, signal }),
  });
  const items = (habilitada ? (busqueda.data?.items ?? []) : []).filter((p) => excluir?.has(p.id) !== true);

  function elegir(producto: Producto): void {
    onSelect(producto);
    setOpen(false);
    setTexto("");
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setTexto("");
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn("h-10 justify-start font-normal text-muted-foreground", className)}
        >
          <Search aria-hidden="true" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(26rem,calc(100vw-2rem))] p-0">
        <Command shouldFilter={false}>
          <CommandInput placeholder="Buscá por SKU o nombre" value={texto} onValueChange={setTexto} />
          <CommandList>
            {!habilitada ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">Escribí al menos 2 caracteres.</p>
            ) : busqueda.isFetching && busqueda.data === undefined ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">Buscando…</p>
            ) : busqueda.isError ? (
              <p className="px-3 py-6 text-center text-sm text-destructive">No pudimos buscar. Probá de nuevo.</p>
            ) : (
              <>
                <CommandEmpty>No encontramos productos con "{q}".</CommandEmpty>
                <CommandGroup>
                  {items.map((p) => (
                    <CommandItem key={p.id} value={p.id} onSelect={() => elegir(p)} className="min-h-11 gap-3">
                      <Package aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{p.nombre}</span>
                        <span className="block text-xs text-muted-foreground">{p.sku}</span>
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
