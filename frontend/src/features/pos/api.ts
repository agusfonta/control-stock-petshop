/** Consultas y mutaciones del POS: busqueda de productos y clientes, alta inline de cliente. */
import {
  type QueryClient,
  type UseMutationResult,
  type UseQueryResult,
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import type { ApiError } from "@/shared/api/errors";
import { queryKeys } from "@/shared/api/queryKeys";
import type { Cliente, Paginated, Producto } from "@/shared/api/types";

export const MIN_CHARS_BUSQUEDA = 2;
export const DEBOUNCE_MS = 250;
const PAGE_SIZE = 20;
const STALE_BUSQUEDA_MS = 10_000;

const PARAMS_PRODUCTOS = { page_size: PAGE_SIZE };

function fetchProductos(q: string, signal?: AbortSignal): Promise<Paginated<Producto>> {
  return apiFetch<Paginated<Producto>>("/productos/buscar", { query: { q, page_size: PAGE_SIZE }, signal });
}

/** Busqueda del POS (10 s de frescura, conserva el resultado previo mientras tipea). */
export function useBuscarProductos(q: string): UseQueryResult<Paginated<Producto>> {
  const texto = q.trim();
  return useQuery({
    queryKey: queryKeys.productos.buscar(texto, PARAMS_PRODUCTOS),
    queryFn: ({ signal }) => fetchProductos(texto, signal),
    enabled: texto.length >= MIN_CHARS_BUSQUEDA,
    staleTime: STALE_BUSQUEDA_MS,
    placeholderData: keepPreviousData,
  });
}

/** Consulta inmediata para Enter / lector: sin esperar el debounce (D10); comparte cache con la busqueda. */
export function buscarProductosAhora(queryClient: QueryClient, q: string): Promise<Paginated<Producto>> {
  const texto = q.trim();
  return queryClient.fetchQuery({
    queryKey: queryKeys.productos.buscar(texto, PARAMS_PRODUCTOS),
    queryFn: ({ signal }) => fetchProductos(texto, signal),
    staleTime: STALE_BUSQUEDA_MS,
  });
}

export function useBuscarClientes(q: string): UseQueryResult<Paginated<Cliente>> {
  const texto = q.trim();
  return useQuery({
    queryKey: queryKeys.clientes.buscar(texto),
    queryFn: ({ signal }) =>
      apiFetch<Paginated<Cliente>>("/clientes/buscar", { query: { q: texto, page_size: 8 }, signal }),
    enabled: texto.length >= MIN_CHARS_BUSQUEDA,
    staleTime: STALE_BUSQUEDA_MS,
    placeholderData: keepPreviousData,
  });
}

/** Alta rapida de cliente con solo el nombre; refresca listados e indice de clientes. */
export function useCrearCliente(): UseMutationResult<Cliente, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation<Cliente, ApiError, string>({
    mutationFn: (nombre) => apiFetch<Cliente>("/clientes", { method: "POST", body: { nombre } }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.clientes.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.indices.clientes }),
      ]);
    },
  });
}
