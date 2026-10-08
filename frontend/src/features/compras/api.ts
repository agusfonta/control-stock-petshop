import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type {
  AlertasStock,
  EstadoPedido,
  PagoDistribuidora,
  PagoDistribuidoraCreate,
  Paginated,
  Pedido,
  PedidoCreate,
} from "@/shared/api/types";

export const PAGE_SIZE = 20;

export interface PedidosFiltros {
  page: number;
  estado: EstadoPedido | null;
  distribuidoraId: string | null;
}

/** Listado paginado de pedidos, filtrable por estado y distribuidora. */
export function usePedidos({ page, estado, distribuidoraId }: PedidosFiltros): UseQueryResult<Paginated<Pedido>> {
  return useQuery({
    queryKey: queryKeys.pedidos.list({ page, estado, distribuidoraId }),
    queryFn: ({ signal }) =>
      apiFetch<Paginated<Pedido>>("/compras/pedidos", {
        query: { page, page_size: PAGE_SIZE, estado, distribuidora_id: distribuidoraId },
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

export function usePedido(id: string): UseQueryResult<Pedido> {
  return useQuery({
    queryKey: queryKeys.pedidos.detail(id),
    queryFn: ({ signal }) => apiFetch<Pedido>(`/compras/pedidos/${id}`, { signal }),
  });
}

/** Productos bajo el stock minimo, para sugerir en el armado de un pedido. */
export function useBajoMinimo(enabled: boolean): UseQueryResult<AlertasStock> {
  return useQuery({
    queryKey: queryKeys.stock.alertas,
    enabled,
    queryFn: ({ signal }) => apiFetch<AlertasStock>("/stock/alertas", { signal }),
  });
}

export function useCrearPedido(): UseMutationResult<Pedido, Error, PedidoCreate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => apiFetch<Pedido>("/compras/pedidos", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.pedidos.all }),
  });
}

/** Recibir suma el stock y actualiza costos: refresca stock, alertas, catalogo, pedidos y cuenta (D6). */
export function useRecibirPedido(): UseMutationResult<Pedido, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => apiFetch<Pedido>(`/compras/pedidos/${id}/recibir`, { method: "POST" }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.stock.all }),
        qc.invalidateQueries({ queryKey: queryKeys.productos.all }),
        qc.invalidateQueries({ queryKey: queryKeys.indices.productos }),
        qc.invalidateQueries({ queryKey: queryKeys.pedidos.all }),
        qc.invalidateQueries({ queryKey: ["distribuidoras", "cuenta"] }),
        qc.invalidateQueries({ queryKey: queryKeys.reportes.all }),
      ]);
    },
  });
}

export function useCancelarPedido(): UseMutationResult<Pedido, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => apiFetch<Pedido>(`/compras/pedidos/${id}/cancelar`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.pedidos.all }),
  });
}

/** Pagos a distribuidoras (solo dueña): filtrable por distribuidora. */
export function usePagos(
  page: number,
  distribuidoraId: string | null,
  enabled: boolean,
): UseQueryResult<Paginated<PagoDistribuidora>> {
  return useQuery({
    queryKey: queryKeys.pagos.list({ page, distribuidoraId }),
    enabled,
    queryFn: ({ signal }) =>
      apiFetch<Paginated<PagoDistribuidora>>("/compras/pagos", {
        query: { page, page_size: PAGE_SIZE, distribuidora_id: distribuidoraId },
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

/** Pagos y cuentas dependen entre si: cualquier cambio refresca ambos. */
function useInvalidarPagos(): () => Promise<void> {
  const qc = useQueryClient();
  return async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.pagos.all }),
      qc.invalidateQueries({ queryKey: ["distribuidoras", "cuenta"] }),
    ]);
  };
}

export function useRegistrarPago(): UseMutationResult<PagoDistribuidora, Error, PagoDistribuidoraCreate> {
  const invalidar = useInvalidarPagos();
  return useMutation({
    mutationFn: (body) => apiFetch<PagoDistribuidora>("/compras/pagos", { method: "POST", body }),
    onSuccess: invalidar,
  });
}

export function useAnularPago(): UseMutationResult<undefined, Error, string> {
  const invalidar = useInvalidarPagos();
  return useMutation({
    mutationFn: (id) => apiFetch<undefined>(`/compras/pagos/${id}`, { method: "DELETE" }),
    onSuccess: invalidar,
  });
}
