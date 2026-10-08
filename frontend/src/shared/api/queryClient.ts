import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/errors";

/** Reintenta una sola vez y solo errores de red/5xx; nunca 4xx (D6). */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;
  if (error instanceof ApiError) return error.status === 0 || error.status >= 500;
  return true;
}

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: shouldRetry,
        refetchOnWindowFocus: true,
      },
    },
  });
}

/** Singleton de la app; el logout lo vacia para no filtrar datos entre sesiones. */
export const queryClient = createQueryClient();
