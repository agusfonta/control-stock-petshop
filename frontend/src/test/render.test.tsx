import { useQuery } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { useLocation } from "react-router";
import { describe, expect, it } from "vitest";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/shared/api/client";
import { makeProducto, paginated } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

function Probe(): React.ReactElement {
  const location = useLocation();
  const { data } = useQuery({
    queryKey: ["probe"],
    queryFn: () => apiFetch<ReturnType<typeof paginated<ReturnType<typeof makeProducto>>>>("/productos"),
  });
  return (
    <div>
      <span>ruta:{location.pathname}</span>
      <span>{data === undefined ? "cargando" : data.items[0]?.nombre}</span>
      <Button>Aceptar</Button>
    </div>
  );
}

describe("entorno de tests (humo)", () => {
  it("renderWithProviders monta router, react-query, MSW y componentes shadcn", async () => {
    server.use(http.get("/api/productos", () => HttpResponse.json(paginated([makeProducto()]))));

    const { findByText, getByRole } = renderWithProviders(<Probe />, { route: "/pos" });

    expect(await findByText("ruta:/pos")).toBeInTheDocument();
    expect(await findByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(getByRole("button", { name: "Aceptar" })).toBeEnabled();
  });
});
