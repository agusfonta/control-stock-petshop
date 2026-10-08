import { Plus, Trash2 } from "lucide-react";
import { type ReactElement, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useBajoMinimo, useCrearPedido } from "@/features/compras/api";
import {
  type LineaBorrador,
  agregarLinea,
  cantidadValida,
  puedeEnviarPedido,
  quitarLinea,
  setCantidad,
  sugerirProductos,
  totalEstimadoCents,
} from "@/features/compras/pedidoLineas";
import { DistribuidoraSelect } from "@/features/distribuidoras/DistribuidoraSelect";
import { ProductoPicker } from "@/features/distribuidoras/ProductoPicker";
import { useListaPrecios, useProductosIndex } from "@/features/distribuidoras/api";
import { ApiError } from "@/shared/api/errors";
import type { Producto, StockItem } from "@/shared/api/types";
import { MoneyText } from "@/shared/components/MoneyText";
import { type Money, formatARS, toCents } from "@/shared/lib/money";
import { notifyError, notifySuccess } from "@/shared/lib/toast";

const MAX_SUGERENCIAS = 8;

interface PedidoSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Distribuidora preseleccionada (acceso desde Reposicion: `?distribuidora=`). */
  distribuidoraInicial?: string;
  /** Producto ya agregado como primera linea (acceso desde Reposicion: `?producto=`). */
  productoInicial?: string;
}

function aStockItem(p: Producto): StockItem {
  return { ...p, bajo_minimo: p.stock_actual <= p.stock_minimo };
}

/** Alta de pedido: distribuidora + productos con cantidad; los costos los fija el servidor. */
export function PedidoSheet({
  open,
  onOpenChange,
  distribuidoraInicial = "",
  productoInicial = "",
}: PedidoSheetProps): ReactElement {
  const navigate = useNavigate();
  const [distribuidoraId, setDistribuidoraId] = useState(distribuidoraInicial);
  const [lineas, setLineas] = useState<LineaBorrador[]>([]);
  const [notas, setNotas] = useState("");
  const [intento, setIntento] = useState(false);
  const crear = useCrearPedido();
  const productos = useProductosIndex();
  const lista = useListaPrecios(distribuidoraId);
  const alertas = useBajoMinimo(open);
  const sembrado = useRef(false);

  useEffect(() => {
    if (!open) return;
    sembrado.current = false;
    setDistribuidoraId(distribuidoraInicial);
    setLineas([]);
    setNotas("");
    setIntento(false);
  }, [open, distribuidoraInicial]);

  // Producto preseleccionado: una sola vez por apertura, cuando el indice de nombres ya cargo.
  useEffect(() => {
    if (!open || productoInicial === "" || sembrado.current || productos.data === undefined) return;
    sembrado.current = true;
    const p = productos.data.get(productoInicial);
    if (p !== undefined) setLineas([{ producto_id: p.id, cantidad: Math.max(1, p.stock_minimo * 2 - p.stock_actual) }]);
  }, [open, productoInicial, productos.data]);

  // Costo estimado por producto: el de la lista de la distribuidora o, si no figura, el del producto.
  const costos = useMemo(() => {
    const m = new Map<string, Money>();
    for (const l of lineas) {
      const p = productos.data?.get(l.producto_id);
      if (p !== undefined) m.set(l.producto_id, p.costo);
    }
    for (const e of lista.data ?? []) {
      if (lineas.some((l) => l.producto_id === e.producto_id)) m.set(e.producto_id, e.costo);
    }
    return m;
  }, [lineas, lista.data, productos.data]);

  const sugerencias = useMemo(() => {
    if (distribuidoraId === "") return [];
    const deLista = (lista.data ?? []).flatMap((e) => {
      const p = productos.data?.get(e.producto_id);
      return p === undefined ? [] : [aStockItem(p)];
    });
    return sugerirProductos({
      lista: deLista,
      bajoMinimo: alertas.data?.items ?? [],
      yaEnPedido: lineas.map((l) => l.producto_id),
    }).slice(0, MAX_SUGERENCIAS);
  }, [distribuidoraId, lista.data, productos.data, alertas.data, lineas]);

  const valido = puedeEnviarPedido(distribuidoraId, lineas);
  const totalCents = totalEstimadoCents(lineas, costos);
  const yaAgregados = useMemo(() => new Set(lineas.map((l) => l.producto_id)), [lineas]);

  async function enviar(): Promise<void> {
    setIntento(true);
    if (!valido) return;
    try {
      const pedido = await crear.mutateAsync({
        distribuidora_id: distribuidoraId,
        lineas,
        notas: notas.trim() === "" ? null : notas.trim(),
      });
      notifySuccess("Pedido creado");
      onOpenChange(false);
      void navigate(`/compras/pedidos/${pedido.id}`);
    } catch (error) {
      notifyError(error instanceof ApiError ? error.message : "No pudimos crear el pedido");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-2xl">
        <SheetHeader className="border-b">
          <SheetTitle>Nuevo pedido</SheetTitle>
          <SheetDescription>
            Elegí la distribuidora y los productos. El pedido no mueve stock hasta que lo recibas.
          </SheetDescription>
        </SheetHeader>
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void enviar();
          }}
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="flex-1 space-y-5 overflow-y-auto p-4">
            <FieldGroup className="gap-4">
              <Field data-invalid={intento && distribuidoraId === ""}>
                <FieldLabel htmlFor="pedido-distribuidora">Distribuidora</FieldLabel>
                <DistribuidoraSelect
                  id="pedido-distribuidora"
                  value={distribuidoraId}
                  onChange={setDistribuidoraId}
                  aria-invalid={intento && distribuidoraId === ""}
                />
                <FieldError>{intento && distribuidoraId === "" ? "Elegí una distribuidora" : undefined}</FieldError>
              </Field>
            </FieldGroup>

            {sugerencias.length > 0 && (
              <section aria-label="Sugerencias" className="space-y-2">
                <h3 className="text-sm font-medium">Sugeridos</h3>
                <ul className="flex flex-wrap gap-2">
                  {sugerencias.map((s) => (
                    <li key={s.producto.id}>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        aria-label={`Agregar ${s.producto.nombre}`}
                        onClick={() => setLineas((prev) => agregarLinea(prev, s.producto.id, s.cantidadSugerida))}
                      >
                        <Plus aria-hidden="true" />
                        <span className="max-w-48 truncate">{s.producto.nombre}</span>
                        {s.bajoMinimo && (
                          <Badge variant="outline" className="border-warning/30 bg-warning-soft text-warning">
                            Bajo mínimo
                          </Badge>
                        )}
                      </Button>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section aria-label="Productos del pedido" className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-medium">Productos</h3>
                <ProductoPicker
                  excluir={yaAgregados}
                  label="Agregar producto"
                  onSelect={(p) => setLineas((prev) => agregarLinea(prev, p.id, 1))}
                />
              </div>
              {lineas.length === 0 ? (
                <p className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
                  {intento ? "Agregá al menos un producto." : "Todavía no agregaste productos."}
                </p>
              ) : (
                <ul className="divide-y rounded-lg border">
                  {lineas.map((l) => {
                    const p = productos.data?.get(l.producto_id);
                    const costo = costos.get(l.producto_id);
                    const invalida = !cantidadValida(l.cantidad);
                    return (
                      <li key={l.producto_id} className="flex flex-wrap items-center gap-3 p-3">
                        <div className="min-w-0 flex-1 basis-48">
                          <p className="truncate text-sm font-medium">{p?.nombre ?? "Producto"}</p>
                          <p className="text-xs text-muted-foreground">
                            {p?.sku ?? ""}
                            {costo !== undefined && ` · ${formatARS(toCents(costo))} c/u`}
                          </p>
                        </div>
                        <div className="flex flex-col">
                          <Input
                            type="number"
                            inputMode="numeric"
                            min={1}
                            step={1}
                            aria-label={`Cantidad de ${p?.nombre ?? "producto"}`}
                            aria-invalid={invalida}
                            className="h-10 w-24 text-right tabular-nums"
                            value={Number.isNaN(l.cantidad) ? "" : l.cantidad}
                            onChange={(e) =>
                              setLineas((prev) => setCantidad(prev, l.producto_id, e.target.value === "" ? 0 : Number(e.target.value)))
                            }
                          />
                          {invalida && <span className="mt-1 text-xs text-destructive">Entero mayor a 0</span>}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Quitar ${p?.nombre ?? "producto"}`}
                          onClick={() => setLineas((prev) => quitarLinea(prev, l.producto_id))}
                        >
                          <Trash2 aria-hidden="true" />
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <Field>
              <FieldLabel htmlFor="pedido-notas">Notas (opcional)</FieldLabel>
              <Textarea
                id="pedido-notas"
                rows={2}
                maxLength={500}
                value={notas}
                onChange={(e) => setNotas(e.target.value)}
                placeholder="Ej.: entregar el jueves"
              />
            </Field>
          </div>
          <SheetFooter className="flex-row items-center justify-between gap-2 border-t">
            <p className="text-sm">
              <span className="text-muted-foreground">Total estimado </span>
              <MoneyText value={totalCents / 100} className="text-lg font-semibold" />
            </p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={crear.isPending || (intento && !valido)}>
                {crear.isPending && <Spinner aria-hidden="true" />}
                Crear pedido
              </Button>
            </div>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
