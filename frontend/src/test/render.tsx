import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type RenderOptions, type RenderResult, render } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router";

interface ProvidersOptions extends Omit<RenderOptions, "wrapper"> {
  /** Entradas iniciales del historial (por defecto `["/"]`). */
  route?: string | string[];
  queryClient?: QueryClient;
}

export interface RenderWithProvidersResult extends RenderResult {
  user: UserEvent;
  queryClient: QueryClient;
}

/** Cliente de tests: sin reintentos ni cache entre casos. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
}

/** Renderiza con Router en memoria + React Query + `userEvent` listo para usar. */
export function renderWithProviders(
  ui: ReactElement,
  { route = "/", queryClient = createTestQueryClient(), ...options }: ProvidersOptions = {},
): RenderWithProvidersResult {
  const entries = Array.isArray(route) ? route : [route];
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={entries}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  return { ...render(ui, { wrapper: Wrapper, ...options }), user: userEvent.setup(), queryClient };
}
