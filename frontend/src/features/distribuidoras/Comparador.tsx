import { Scale, TrendingDown } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ProductoPicker } from "@/features/distribuidoras/ProductoPicker";
import { useComparar } from "@/features/distribuidoras/api";
import type { CompararFila, Producto } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { toCents } from "@/shared/lib/money";

/** Comparador de costos: elegido un producto, sus costos por distribuidora del mas barato al mas caro. */
export function Comparador(): ReactElement {
  const [producto, setProducto] = useState<Producto | null>(null);
  const comparar = useComparar(producto?.id ?? null);

  // El servidor ordena por costo; se reordena por si acaso para garantizar que el primero es el mas barato.
  const filas = [...(comparar.data?.filas ?? [])].sort((a, b) => toCents(a.costo) - toCents(b.costo));
  const minimo = filas.length > 0 ? toCents(filas[0]?.costo ?? 0) : null;

  const columnas: DataTableColumn<CompararFila>[] = [
    {
      id: "distribuidora",
      header: "Distribuidora",
      cell: (f) => (
        <span className="flex flex-wrap items-center gap-2">
          <Link
            to={`/distribuidoras/${f.distribuidora_id}`}
            className="font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {f.distribuidora_nombre}
          </Link>
          {minimo !== null && toCents(f.costo) === minimo && (
            <Badge className="gap-1">
              <TrendingDown aria-hidden="true" className="size-3" /> Más barato
            </Badge>
          )}
        </span>
      ),
    },
    { id: "costo", header: "Costo", align: "right", cell: (f) => <MoneyText value={f.costo} className="font-medium" /> },
    {
      id: "sugerido",
      header: "Precio sugerido",
      align: "right",
      cell: (f) => <MoneyText value={f.precio_sugerido} className="text-muted-foreground" />,
    },
  ];

  return (
    <section aria-label="Comparador de costos" className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <ProductoPicker
          onSelect={setProducto}
          label={producto === null ? "Elegir un producto para comparar" : "Cambiar de producto"}
          className="w-full sm:w-auto"
        />
        {producto !== null && (
          <p className="text-sm">
            <span className="font-medium">{producto.nombre}</span>{" "}
            <span className="text-muted-foreground">· {producto.sku}</span>
          </p>
        )}
      </div>
      {producto === null ? (
        <EmptyState
          icon={Scale}
          title="Compará costos entre distribuidoras"
          description="Elegí un producto y mirá quién lo ofrece más barato, con el precio de venta que resultaría."
        />
      ) : comparar.isError ? (
        <ErrorState title="No pudimos comparar los costos" onRetry={() => void comparar.refetch()} />
      ) : comparar.isLoading ? (
        <Skeleton className="h-40 w-full rounded-xl" />
      ) : (
        <DataTable
          label={`Costos de ${producto.nombre} por distribuidora`}
          columns={columnas}
          rows={filas}
          getRowKey={(f) => f.distribuidora_id}
          empty={
            <EmptyState
              icon={Scale}
              title="Ninguna distribuidora lo ofrece"
              description="Este producto no está en ninguna lista de precios. Cargalo desde la ficha de una distribuidora."
            />
          }
        />
      )}
    </section>
  );
}
