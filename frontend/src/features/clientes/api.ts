import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type { Cliente, ClienteInput, Paginated, VentaResumen } from "@/shared/api/types";

export const PAGE_SIZE = 20;

/** Listado paginado; con texto usa `/clientes/buscar` (nombre, email o telefono). */
export function useClientes({ page, q }: { page: number; q: string }): UseQueryResult<Paginated<Cliente>> {
  const texto = q.trim();
  return useQuery({
    queryKey: texto === "" ? queryKeys.clientes.list({ page }) : queryKeys.clientes.list({ page, q: texto }),
    queryFn: ({ signal }) =>
      texto === ""
        ? apiFetch<Paginated<Cliente>>("/clientes", { query: { page, page_size: PAGE_SIZE }, signal })
        : apiFetch<Paginated<Cliente>>("/clientes/buscar", {
            query: { q: texto, page, page_size: PAGE_SIZE },
            signal,
          }),
    placeholderData: keepPreviousData,
  });
}

export function useCliente(id: string): UseQueryResult<Cliente> {
  return useQuery({
    queryKey: queryKeys.clientes.detail(id),
    queryFn: ({ signal }) => apiFetch<Cliente>(`/clientes/${id}`, { signal }),
  });
}

/** Historial del cliente: confirmadas y anuladas, mas reciente primero (el mostrador ve solo las suyas). */
export function useHistorialCliente(id: string, page: number): UseQueryResult<Paginated<VentaResumen>> {
  return useQuery({
    queryKey: queryKeys.clientes.historial(id, { page }),
    queryFn: ({ signal }) =>
      apiFetch<Paginated<VentaResumen>>(`/clientes/${id}/ventas`, {
        query: { page, page_size: PAGE_SIZE },
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

function useInvalidarClientes(): () => Promise<void> {
  const qc = useQueryClient();
  return async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.clientes.all }),
      qc.invalidateQueries({ queryKey: queryKeys.indices.clientes }),
    ]);
  };
}

export function useCrearCliente(): UseMutationResult<Cliente, Error, ClienteInput> {
  const invalidar = useInvalidarClientes();
  return useMutation({
    mutationFn: (body) => apiFetch<Cliente>("/clientes", { method: "POST", body }),
    onSuccess: invalidar,
  });
}

export function useEditarCliente(): UseMutationResult<Cliente, Error, { id: string; body: ClienteInput }> {
  const invalidar = useInvalidarClientes();
  return useMutation({
    mutationFn: ({ id, body }) => apiFetch<Cliente>(`/clientes/${id}`, { method: "PUT", body }),
    onSuccess: invalidar,
  });
}

export function useBajaCliente(): UseMutationResult<undefined, Error, string> {
  const invalidar = useInvalidarClientes();
  return useMutation({
    mutationFn: (id) => apiFetch<undefined>(`/clientes/${id}`, { method: "DELETE" }),
    onSuccess: invalidar,
  });
}
