import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type {
  CompararResponse,
  Cuenta,
  Distribuidora,
  DistribuidoraInput,
  ListaPrecio,
  Paginated,
  Producto,
} from "@/shared/api/types";

export const PAGE_SIZE = 20;
const INDEX_PAGE_SIZE = 100;
const INDEX_STALE_MS = 5 * 60_000;

/** Recorre todas las paginas de un listado paginado (indices de nombres, D12). */
async function cargarTodas<T>(path: string, signal: AbortSignal): Promise<T[]> {
  const todas: T[] = [];
  for (let page = 1; ; page += 1) {
    const res = await apiFetch<Paginated<T>>(path, { query: { page, page_size: INDEX_PAGE_SIZE }, signal });
    todas.push(...res.items);
    if (page >= res.total_pages) break;
  }
  return todas;
}

/** Indice `id -> distribuidora` de las activas (para nombres en pedidos, pagos y cuentas). */
export function useDistribuidorasIndex(): UseQueryResult<Map<string, Distribuidora>> {
  return useQuery({
    queryKey: [...queryKeys.indices.distribuidoras, "map"] as const,
    staleTime: INDEX_STALE_MS,
    queryFn: async ({ signal }) => {
      const todas = await cargarTodas<Distribuidora>("/distribuidoras", signal);
      return new Map(todas.map((d) => [d.id, d]));
    },
  });
}

/** Indice `id -> producto` de los activos (para nombres en listas de precios y pedidos). */
export function useProductosIndex(): UseQueryResult<Map<string, Producto>> {
  return useQuery({
    queryKey: [...queryKeys.indices.productos, "map"] as const,
    staleTime: INDEX_STALE_MS,
    queryFn: async ({ signal }) => {
      const todos = await cargarTodas<Producto>("/productos", signal);
      return new Map(todos.map((p) => [p.id, p]));
    },
  });
}

export function useDistribuidoras(page: number): UseQueryResult<Paginated<Distribuidora>> {
  return useQuery({
    queryKey: queryKeys.distribuidoras.list({ page }),
    queryFn: ({ signal }) =>
      apiFetch<Paginated<Distribuidora>>("/distribuidoras", { query: { page, page_size: PAGE_SIZE }, signal }),
    placeholderData: keepPreviousData,
  });
}

export function useDistribuidora(id: string): UseQueryResult<Distribuidora> {
  return useQuery({
    queryKey: queryKeys.distribuidoras.detail(id),
    queryFn: ({ signal }) => apiFetch<Distribuidora>(`/distribuidoras/${id}`, { signal }),
  });
}

/** Prefijos a invalidar tras cambiar distribuidoras (listado, detalle, indice, comparador). */
function useInvalidarDistribuidoras(): () => Promise<void> {
  const qc = useQueryClient();
  return async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.distribuidoras.all }),
      qc.invalidateQueries({ queryKey: queryKeys.indices.distribuidoras }),
    ]);
  };
}

export function useCrearDistribuidora(): UseMutationResult<Distribuidora, Error, DistribuidoraInput> {
  const invalidar = useInvalidarDistribuidoras();
  return useMutation({
    mutationFn: (body) => apiFetch<Distribuidora>("/distribuidoras", { method: "POST", body }),
    onSuccess: invalidar,
  });
}

export function useEditarDistribuidora(): UseMutationResult<
  Distribuidora,
  Error,
  { id: string; body: DistribuidoraInput }
> {
  const invalidar = useInvalidarDistribuidoras();
  return useMutation({
    mutationFn: ({ id, body }) => apiFetch<Distribuidora>(`/distribuidoras/${id}`, { method: "PUT", body }),
    onSuccess: invalidar,
  });
}

export function useBajaDistribuidora(): UseMutationResult<undefined, Error, string> {
  const invalidar = useInvalidarDistribuidoras();
  return useMutation({
    mutationFn: (id) => apiFetch<undefined>(`/distribuidoras/${id}`, { method: "DELETE" }),
    onSuccess: invalidar,
  });
}

export function useListaPrecios(distribuidoraId: string): UseQueryResult<ListaPrecio[]> {
  return useQuery({
    queryKey: queryKeys.distribuidoras.precios(distribuidoraId),
    enabled: distribuidoraId !== "",
    queryFn: ({ signal }) => apiFetch<ListaPrecio[]>(`/distribuidoras/${distribuidoraId}/listas`, { signal }),
  });
}

function useInvalidarListas(distribuidoraId: string): () => Promise<void> {
  const qc = useQueryClient();
  return async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.distribuidoras.precios(distribuidoraId) }),
      qc.invalidateQueries({ queryKey: ["distribuidoras", "comparar"] }),
    ]);
  };
}

/** `409` si el producto ya figura en la lista (el llamador lo informa). */
export function useAgregarPrecio(
  distribuidoraId: string,
): UseMutationResult<ListaPrecio, Error, { producto_id: string; costo: string }> {
  const invalidar = useInvalidarListas(distribuidoraId);
  return useMutation({
    mutationFn: (body) =>
      apiFetch<ListaPrecio>(`/distribuidoras/${distribuidoraId}/listas`, { method: "POST", body }),
    onSuccess: invalidar,
  });
}

export function useCambiarCosto(
  distribuidoraId: string,
): UseMutationResult<ListaPrecio, Error, { producto_id: string; costo: string }> {
  const invalidar = useInvalidarListas(distribuidoraId);
  return useMutation({
    mutationFn: ({ producto_id, costo }) =>
      apiFetch<ListaPrecio>(`/distribuidoras/${distribuidoraId}/listas/${producto_id}`, {
        method: "PUT",
        body: { costo },
      }),
    onSuccess: invalidar,
  });
}

export function useQuitarPrecio(distribuidoraId: string): UseMutationResult<undefined, Error, string> {
  const invalidar = useInvalidarListas(distribuidoraId);
  return useMutation({
    mutationFn: (productoId) =>
      apiFetch<undefined>(`/distribuidoras/${distribuidoraId}/listas/${productoId}`, { method: "DELETE" }),
    onSuccess: invalidar,
  });
}

/** Costos de un producto por distribuidora, del mas barato al mas caro. */
export function useComparar(productoId: string | null): UseQueryResult<CompararResponse> {
  return useQuery({
    queryKey: queryKeys.distribuidoras.comparar(productoId ?? ""),
    enabled: productoId !== null,
    queryFn: ({ signal }) =>
      apiFetch<CompararResponse>("/distribuidoras/comparar", { query: { producto_id: productoId }, signal }),
  });
}

/** Cuenta corriente con la distribuidora (solo dueña: pasar `enabled=false` al mostrador). */
export function useCuenta(distribuidoraId: string, enabled: boolean): UseQueryResult<Cuenta> {
  return useQuery({
    queryKey: queryKeys.distribuidoras.cuenta(distribuidoraId),
    enabled,
    queryFn: ({ signal }) => apiFetch<Cuenta>(`/compras/distribuidoras/${distribuidoraId}/cuenta`, { signal }),
  });
}
