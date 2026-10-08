import { Check, Loader2, UserPlus, UserRound, X } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { DEBOUNCE_MS, MIN_CHARS_BUSQUEDA, useBuscarClientes, useCrearCliente } from "@/features/pos/api";
import { useCartStore } from "@/features/pos/useCartStore";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import type { Cliente } from "@/shared/api/types";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

function detalle(c: Cliente): string | null {
  return c.telefono ?? c.email ?? null;
}

/** Cliente opcional de la venta: buscar, crear solo con el nombre o quitar (UX2). */
export function ClienteSelector(): ReactElement {
  const cliente = useCartStore((s) => s.cliente);
  const setCliente = useCartStore((s) => s.setCliente);
  const [open, setOpen] = useState(false);
  const [texto, setTexto] = useState("");
  const debounced = useDebouncedValue(texto, DEBOUNCE_MS);
  const busqueda = useBuscarClientes(debounced);
  const crear = useCrearCliente();

  const nombre = texto.trim();
  const largoOk = nombre.length >= MIN_CHARS_BUSQUEDA;
  // Resultados de una busqueda anterior (debounce pendiente o placeholder) no se muestran como si fueran del texto actual.
  const vigente = debounced.trim() === nombre && !busqueda.isPlaceholderData;
  const buscando = largoOk && (!vigente || busqueda.isFetching);
  const items = largoOk && vigente ? (busqueda.data?.items ?? []) : [];
  const hayExacto = items.some((c) => c.nombre.toLowerCase() === nombre.toLowerCase());
  const puedeCrear = largoOk && !buscando && !hayExacto;

  function elegir(c: Cliente): void {
    setCliente(c);
    setOpen(false);
    setTexto("");
  }

  function crearInline(): void {
    crear.mutate(nombre, {
      onSuccess: (nuevo) => {
        elegir(nuevo);
        notifySuccess("Cliente creado");
      },
      onError: (error) => notifyError(error.message),
    });
  }

  if (cliente !== null && !open) {
    return (
      <div className="flex min-h-11 items-center gap-2 rounded-lg border bg-accent/50 px-3 py-1.5">
        <UserRound aria-hidden="true" className="size-4 shrink-0 text-accent-foreground" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{cliente.nombre}</p>
          {detalle(cliente) !== null && <p className="truncate text-xs text-muted-foreground">{detalle(cliente)}</p>}
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(true)}>
          Cambiar
        </Button>
        <Button type="button" variant="ghost" size="icon-sm" aria-label="Quitar cliente" onClick={() => setCliente(null)}>
          <X aria-hidden="true" />
        </Button>
      </div>
    );
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
        <Button type="button" variant="outline" className="h-11 w-full justify-start font-normal text-muted-foreground">
          <UserRound aria-hidden="true" />
          {cliente === null ? "Agregar cliente (opcional)" : "Elegir otro cliente"}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(22rem,calc(100vw-2rem))] p-0">
        <Command shouldFilter={false}>
          <CommandInput placeholder="Nombre, email o teléfono" value={texto} onValueChange={setTexto} />
          <CommandList>
            {!largoOk && (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                Escribí al menos {MIN_CHARS_BUSQUEDA} letras para buscar.
              </p>
            )}
            {buscando && items.length === 0 && (
              <p className="flex items-center justify-center gap-2 px-3 py-6 text-sm text-muted-foreground">
                <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Buscando…
              </p>
            )}
            {largoOk && !buscando && items.length === 0 && !puedeCrear && (
              <CommandEmpty>No encontramos clientes.</CommandEmpty>
            )}
            {puedeCrear && (
              <CommandGroup>
                <CommandItem value="crear-cliente" onSelect={crearInline} disabled={crear.isPending} className="min-h-11">
                  {crear.isPending ? <Loader2 aria-hidden="true" className="animate-spin" /> : <UserPlus aria-hidden="true" />}
                  Crear cliente "{nombre}"
                </CommandItem>
              </CommandGroup>
            )}
            {items.length > 0 && (
              <CommandGroup heading="Clientes">
                {items.map((c) => (
                  <CommandItem key={c.id} value={c.id} onSelect={() => elegir(c)} className="min-h-11">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{c.nombre}</p>
                      {detalle(c) !== null && <p className="truncate text-xs text-muted-foreground">{detalle(c)}</p>}
                    </div>
                    {cliente?.id === c.id && <Check aria-hidden="true" />}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
