import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type {
  MargenesReporte,
  MasVendidosReporte,
  ReposicionReporte,
  VentasDiaReporte,
} from "@/shared/api/types";

/** `fecha` `YYYY-MM-DD`; sin fecha el servidor usa hoy. El alcance (todas/propias) lo decide el rol. */
export function useVentasDia(fecha: string | undefined): UseQueryResult<VentasDiaReporte> {
  return useQuery({
    queryKey: queryKeys.reportes.ventasDia(fecha),
    queryFn: ({ signal }) => apiFetch<VentasDiaReporte>("/reportes/ventas-dia", { query: { fecha }, signal }),
    placeholderData: keepPreviousData,
  });
}

export interface ReposicionParams {
  dias: number;
  cobertura_max_dias: number;
}

export const REPOSICION_DEFAULTS: ReposicionParams = { dias: 30, cobertura_max_dias: 7 };

export function useReposicion(params: ReposicionParams): UseQueryResult<ReposicionReporte> {
  return useQuery({
    queryKey: queryKeys.reportes.reposicion({ ...params }),
    queryFn: ({ signal }) =>
      apiFetch<ReposicionReporte>("/reportes/reposicion", {
        query: { dias: params.dias, cobertura_max_dias: params.cobertura_max_dias },
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

export interface MasVendidosParams {
  desde: string | undefined;
  hasta: string | undefined;
  orden: "cantidad" | "monto";
  limite: number;
}

/** Solo duena (`reportes.completos`): el mostrador recibe 403, por eso la pantalla esta tras `RequireRole`. */
export function useMasVendidos(params: MasVendidosParams, enabled = true): UseQueryResult<MasVendidosReporte> {
  return useQuery({
    queryKey: queryKeys.reportes.masVendidos({ ...params }),
    queryFn: ({ signal }) =>
      apiFetch<MasVendidosReporte>("/reportes/mas-vendidos", {
        query: { desde: params.desde, hasta: params.hasta, orden: params.orden, limite: params.limite },
        signal,
      }),
    enabled,
    placeholderData: keepPreviousData,
  });
}

interface MargenesParams {
  desde: string | undefined;
  hasta: string | undefined;
  page: number;
  pageSize: number;
}

export function useMargenes(params: MargenesParams, enabled = true): UseQueryResult<MargenesReporte> {
  return useQuery({
    queryKey: queryKeys.reportes.margenes({ ...params }),
    queryFn: ({ signal }) =>
      apiFetch<MargenesReporte>("/reportes/margenes", {
        query: { desde: params.desde, hasta: params.hasta, page: params.page, page_size: params.pageSize },
        signal,
      }),
    enabled,
    placeholderData: keepPreviousData,
  });
}
