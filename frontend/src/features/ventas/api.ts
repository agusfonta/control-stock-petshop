/** Consultas y mutaciones de ventas (listado, detalle, anulacion) + indice de clientes (D12). */
import {
  type UseMutationResult,
  type UseQueryResult,
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { rangoQuery } from "@/features/ventas/filtros";
import { apiFetch } from "@/shared/api/client";
import type { ApiError } from "@/shared/api/errors";
import { queryKeys } from "@/shared/api/queryKeys";
import type { Cliente, EstadoVenta, Paginated, Venta, VentaResumen } from "@/shared/api/types";

export const PAGE_SIZE = 20;
const INDEX_PAGE_SIZE = 100;
const INDEX_STALE_MS = 5 * 60_000;

export interface VentasFiltros {
  /** `undefined`: confirmadas + anuladas (los borradores nunca se listan). */
  estado: Exclude<EstadoVenta, "borrador"> | undefined;
  /** `YYYY-MM-DD` local; `""` = sin limite. */
  desde: string;
  hasta: string;
  page: number;
}

export function useVentas(filtros: VentasFiltros): UseQueryResult<Paginated<VentaResumen>> {
  const { desde, hasta } = rangoQuery(filtros.desde, filtros.hasta);
  const query = { estado: filtros.estado, desde, hasta, page: filtros.page, page_size: PAGE_SIZE };
  return useQuery({
    queryKey: queryKeys.ventas.list(query),
    queryFn: ({ signal }) => apiFetch<Paginated<VentaResumen>>("/ventas", { query, signal }),
    placeholderData: keepPreviousData,
  });
}

export function useVenta(id: string): UseQueryResult<Venta> {
  return useQuery({
    queryKey: queryKeys.ventas.detail(id),
    queryFn: ({ signal }) => apiFetch<Venta>(`/ventas/${id}`, { signal }),
    // Un 404 (venta ajena o inexistente) no mejora reintentando.
    retry: false,
  });
}

/** Anula una venta confirmada: devuelve stock, asi que refresca todo lo que depende del stock (D6). */
export function useAnularVenta(id: string): UseMutationResult<Venta, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation<Venta, ApiError, string>({
    mutationFn: (motivo) => apiFetch<Venta>(`/ventas/${id}/anular`, { method: "POST", body: { motivo } }),
    onSuccess: async (venta) => {
      queryClient.setQueryData(queryKeys.ventas.detail(id), venta);
      await Promise.all(
        [
          queryKeys.ventas.all,
          queryKeys.stock.all,
          queryKeys.productos.all,
          queryKeys.reportes.all,
          queryKeys.clientes.all,
        ].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
      );
    },
  });
}

async function cargarTodos<T>(path: string, signal: AbortSignal): Promise<T[]> {
  const todos: T[] = [];
  for (let page = 1; ; page += 1) {
    const res = await apiFetch<Paginated<T>>(path, { query: { page, page_size: INDEX_PAGE_SIZE }, signal });
    todos.push(...res.items);
    if (page >= res.total_pages) break;
  }
  return todos;
}

/** Indice `id -> cliente` de los activos, para mostrar nombres en el listado de ventas (D12). */
export function useClientesIndex(): UseQueryResult<Map<string, Cliente>> {
  return useQuery({
    queryKey: [...queryKeys.indices.clientes, "map"] as const,
    staleTime: INDEX_STALE_MS,
    queryFn: async ({ signal }) => new Map((await cargarTodos<Cliente>("/clientes", signal)).map((c) => [c.id, c])),
  });
}

/** Cliente dado de baja (fuera del indice): consulta puntual por id; si no existe, `null`. */
export function useClientePuntual(id: string | null, habilitado: boolean): UseQueryResult<Cliente> {
  return useQuery({
    queryKey: queryKeys.clientes.detail(id ?? ""),
    queryFn: ({ signal }) => apiFetch<Cliente>(`/clientes/${id ?? ""}`, { signal }),
    enabled: habilitado && id !== null,
    retry: false,
  });
}
