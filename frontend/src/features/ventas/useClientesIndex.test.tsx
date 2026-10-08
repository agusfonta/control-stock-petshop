import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { useClientesIndex } from "@/features/ventas/api";
import { makeCliente } from "@/test/fixtures";
import { createTestQueryClient } from "@/test/render";
import { server } from "@/test/server";

describe("useClientesIndex (D12)", () => {
  it("recorre todas las paginas y devuelve un Map por id", async () => {
    const paginasPedidas: string[] = [];
    server.use(
      http.get("/api/clientes", ({ request }) => {
        const params = new URL(request.url).searchParams;
        const page = Number(params.get("page"));
        paginasPedidas.push(`${page}/${params.get("page_size")}`);
        const items = page === 1 ? [makeCliente({ id: "c-1" })] : [makeCliente({ id: "c-2", nombre: "Bruno" })];
        return HttpResponse.json({ items, total: 2, page, page_size: 100, total_pages: 2 });
      }),
    );
    const client = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useClientesIndex(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true), { timeout: 4000 });
    expect([...(result.current.data?.keys() ?? [])]).toEqual(["c-1", "c-2"]);
    expect(result.current.data?.get("c-2")?.nombre).toBe("Bruno");
    expect(paginasPedidas).toEqual(["1/100", "2/100"]);
  });
});
