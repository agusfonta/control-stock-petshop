import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type {
  AjusteStockRequest,
  AjusteStockResponse,
  Distribuidora,
  MargenMinimoRequest,
  Paginated,
  Producto,
  ProductoCreate,
  ProductoUpdate,
} from "@/shared/api/types";

export const PAGE_SIZE = 20;

interface ProductosParams {
  page: number;
  /** Texto de busqueda ya normalizado (vacio = listado completo). */
  q: string;
}

/** Listado paginado; con texto usa `/productos/buscar` (SKU exacto o nombre parcial). */
export function useProductos({ page, q }: ProductosParams): UseQueryResult<Paginated<Producto>> {
  const texto = q.trim();
  return useQuery({
    queryKey: texto === "" ? queryKeys.productos.list({ page }) : queryKeys.productos.buscar(texto, { page }),
    queryFn: ({ signal }) =>
      texto === ""
        ? apiFetch<Paginated<Producto>>("/productos", { query: { page, page_size: PAGE_SIZE }, signal })
        : apiFetch<Paginated<Producto>>("/productos/buscar", {
            query: { q: texto, page, page_size: PAGE_SIZE },
            signal,
          }),
    placeholderData: keepPreviousData,
  });
}

/** Prefijos a invalidar tras cambiar el catalogo o su stock (D6). */
function useInvalidarCatalogo(): () => Promise<void> {
  const qc = useQueryClient();
  return async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.productos.all }),
      qc.invalidateQueries({ queryKey: queryKeys.stock.all }),
      qc.invalidateQueries({ queryKey: queryKeys.indices.productos }),
    ]);
  };
}

export function useCrearProducto(): UseMutationResult<Producto, Error, ProductoCreate> {
  const invalidar = useInvalidarCatalogo();
  return useMutation({
    mutationFn: (body) => apiFetch<Producto>("/productos", { method: "POST", body }),
    onSuccess: invalidar,
  });
}

export function useEditarProducto(): UseMutationResult<Producto, Error, { id: string; body: ProductoUpdate }> {
  const invalidar = useInvalidarCatalogo();
  return useMutation({
    mutationFn: ({ id, body }) => apiFetch<Producto>(`/productos/${id}`, { method: "PUT", body }),
    onSuccess: invalidar,
  });
}

export function useMargenMinimo(): UseMutationResult<Producto, Error, { id: string; body: MargenMinimoRequest }> {
  const invalidar = useInvalidarCatalogo();
  return useMutation({
    mutationFn: ({ id, body }) => apiFetch<Producto>(`/productos/${id}/margen-minimo`, { method: "PATCH", body }),
    onSuccess: invalidar,
  });
}

export function useBajaProducto(): UseMutationResult<undefined, Error, string> {
  const invalidar = useInvalidarCatalogo();
  return useMutation({
    mutationFn: (id) => apiFetch<undefined>(`/productos/${id}`, { method: "DELETE" }),
    onSuccess: invalidar,
  });
}

/** Ajuste manual con motivo (dueña). Refresca stock, alertas y catalogo (D6). */
export function useAjustarStock(): UseMutationResult<
  AjusteStockResponse,
  Error,
  { id: string; body: AjusteStockRequest }
> {
  const invalidar = useInvalidarCatalogo();
  return useMutation({
    mutationFn: ({ id, body }) =>
      apiFetch<AjusteStockResponse>(`/productos/${id}/ajustar`, { method: "POST", body }),
    onSuccess: invalidar,
  });
}

/** Distribuidoras activas (todas las paginas) para el selector de "distribuidora por defecto". */
export function useDistribuidorasActivas(enabled = true): UseQueryResult<Distribuidora[]> {
  return useQuery({
    queryKey: [...queryKeys.indices.distribuidoras, "lista"] as const,
    enabled,
    staleTime: 5 * 60_000,
    queryFn: async ({ signal }) => {
      const todas: Distribuidora[] = [];
      for (let page = 1; ; page += 1) {
        const res = await apiFetch<Paginated<Distribuidora>>("/distribuidoras", {
          query: { page, page_size: 100 },
          signal,
        });
        todas.push(...res.items);
        if (page >= res.total_pages) break;
      }
      return todas;
    },
  });
}
