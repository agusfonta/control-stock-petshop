import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { useSession } from "@/features/auth/session";
import { apiFetch } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type { AlertasStock, Paginated, Producto, StockItem } from "@/shared/api/types";

/** Resumen de reposicion; alimenta el badge del sidebar (refetch cada 60 s, D6). */
export function useAlertasStock(): UseQueryResult<AlertasStock> {
  const autenticado = useSession((s) => s.status === "authenticated");
  return useQuery({
    queryKey: queryKeys.stock.alertas,
    queryFn: ({ signal }) => apiFetch<AlertasStock>("/stock/alertas", { signal }),
    enabled: autenticado,
    refetchInterval: 60_000,
  });
}

interface StockParams {
  page: number;
  soloBajoMinimo: boolean;
}

/** Stock de servidor: filtro "bajo minimo" y orden por menor cobertura (`orden=rotacion`). */
export function useStockList({ page, soloBajoMinimo }: StockParams): UseQueryResult<Paginated<StockItem>> {
  return useQuery({
    queryKey: queryKeys.stock.list({ page, soloBajoMinimo }),
    queryFn: ({ signal }) =>
      apiFetch<Paginated<StockItem>>("/stock", {
        query: {
          page,
          page_size: 20,
          orden: "rotacion",
          bajo_minimo: soloBajoMinimo ? true : undefined,
        },
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

/** Convierte un producto del catalogo en fila de stock con la misma regla de `bajo_minimo` (D13). */
function aStockItem(p: Producto): StockItem {
  return { ...p, bajo_minimo: p.stock_actual <= p.stock_minimo };
}

/** Busqueda de la pantalla de stock: `/stock` no busca, asi que usa el catalogo (D13). Hasta 100 resultados. */
export function useStockBusqueda(q: string): UseQueryResult<Paginated<StockItem>> {
  const texto = q.trim();
  return useQuery({
    queryKey: queryKeys.productos.buscar(texto, { vista: "stock" }),
    enabled: texto !== "",
    queryFn: async ({ signal }) => {
      const res = await apiFetch<Paginated<Producto>>("/productos/buscar", {
        query: { q: texto, page: 1, page_size: 100 },
        signal,
      });
      return { ...res, items: res.items.map(aStockItem) };
    },
    placeholderData: keepPreviousData,
  });
}
