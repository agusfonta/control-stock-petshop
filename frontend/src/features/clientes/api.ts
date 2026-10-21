import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type { Cliente, ClienteInput, ClienteListItem, Mascota, MascotaInput, Paginated, VentaResumen } from "@/shared/api/types";

export const PAGE_SIZE = 20;

/** Listado paginado; con texto usa `/clientes/buscar` (nombre, email o telefono). */
export function useClientes({ page, q }: { page: number; q: string }): UseQueryResult<Paginated<ClienteListItem>> {
  const texto = q.trim();
  return useQuery({
    queryKey: texto === "" ? queryKeys.clientes.list({ page }) : queryKeys.clientes.list({ page, q: texto }),
    queryFn: ({ signal }) =>
      texto === ""
        ? apiFetch<Paginated<ClienteListItem>>("/clientes", { query: { page, page_size: PAGE_SIZE }, signal })
        : apiFetch<Paginated<ClienteListItem>>("/clientes/buscar", {
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

/** Mascotas activas del cliente (lista simple, sin paginar). */
export function useMascotas(clienteId: string, enabled = true): UseQueryResult<Mascota[]> {
  return useQuery({
    queryKey: queryKeys.clientes.mascotas(clienteId),
    enabled,
    queryFn: ({ signal }) => apiFetch<Mascota[]>(`/clientes/${clienteId}/mascotas`, { signal }),
  });
}

/** Tabla, detalle, historial y mascotas cuelgan del prefijo `clientes`: una mascota cambia la lista tambien. */
function useInvalidarMascotas(): () => Promise<void> {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: queryKeys.clientes.all });
}

export function useCrearMascota(clienteId: string): UseMutationResult<Mascota, Error, MascotaInput> {
  const invalidar = useInvalidarMascotas();
  return useMutation({
    mutationFn: (body) => apiFetch<Mascota>(`/clientes/${clienteId}/mascotas`, { method: "POST", body }),
    onSuccess: invalidar,
  });
}

export function useEditarMascota(
  clienteId: string,
): UseMutationResult<Mascota, Error, { id: string; body: MascotaInput }> {
  const invalidar = useInvalidarMascotas();
  return useMutation({
    mutationFn: ({ id, body }) => apiFetch<Mascota>(`/clientes/${clienteId}/mascotas/${id}`, { method: "PUT", body }),
    onSuccess: invalidar,
  });
}

export function useBajaMascota(clienteId: string): UseMutationResult<undefined, Error, string> {
  const invalidar = useInvalidarMascotas();
  return useMutation({
    mutationFn: (id) => apiFetch<undefined>(`/clientes/${clienteId}/mascotas/${id}`, { method: "DELETE" }),
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
