import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { toIsoDate } from "@/features/reportes/params";
import type {
  MargenesReporte,
  ReposicionReporte,
  VentasDiaReporte,
} from "@/shared/api/types";
import { duena, mostrador } from "@/test/fixtures";
import { renderApp } from "@/test/renderApp";
import { server } from "@/test/server";

function ventasDia(overrides: Partial<VentasDiaReporte> = {}): VentasDiaReporte {
  return {
    fecha: toIsoDate(new Date()),
    alcance: "todas",
    cantidad_ventas: 2,
    total_vendido: 5300,
    ticket_promedio: 2650,
    unidades_vendidas: 5,
    por_metodo: [
      { metodo: "efectivo", monto: 3800, cantidad_pagos: 1 },
      { metodo: "transferencia", monto: 1500, cantidad_pagos: 1 },
      { metodo: "tarjeta", monto: 0, cantidad_pagos: 0 },
      { metodo: "mp", monto: 0, cantidad_pagos: 0 },
    ],
    anuladas: { cantidad: 0, total: 0 },
    ...overrides,
  };
}

function mockVentasDia(respuesta: VentasDiaReporte): URLSearchParams[] {
  const consultas: URLSearchParams[] = [];
  server.use(
    http.get("/api/reportes/ventas-dia", ({ request }) => {
      const params = new URL(request.url).searchParams;
      consultas.push(params);
      return HttpResponse.json({ ...respuesta, fecha: params.get("fecha") ?? respuesta.fecha });
    }),
  );
  return consultas;
}

function secciones(): HTMLElement {
  return screen.getByRole("navigation", { name: "Secciones de reportes" });
}

describe("Ventas del dia", () => {
  it("la duena ve cantidad, total, ticket y el desglose sin Mercado Pago en cero", async () => {
    mockVentasDia(ventasDia());
    renderApp({ route: "/reportes/ventas-dia", user: duena });

    expect(await screen.findByText(/\$\s5\.300,00/)).toBeInTheDocument();
    expect(screen.getByText(/\$\s2\.650,00/)).toBeInTheDocument();
    expect(screen.getByText("Ventas", { selector: "p" })).toBeInTheDocument();
    const tabla = screen.getByRole("table", { name: "Ventas por medio de pago" });
    expect(within(tabla).getByText("Efectivo")).toBeInTheDocument();
    expect(within(tabla).getByText("Transferencia")).toBeInTheDocument();
    expect(within(tabla).queryByText("Mercado Pago")).not.toBeInTheDocument();
    for (const nombre of ["Ventas del día", "Reposición", "Más vendidos", "Márgenes"]) {
      expect(within(secciones()).getByRole("link", { name: nombre })).toBeInTheDocument();
    }
  });

  it("muestra Mercado Pago cuando tuvo monto y las anuladas aparte", async () => {
    mockVentasDia(
      ventasDia({
        por_metodo: [{ metodo: "mp", monto: "1200.00", cantidad_pagos: 1 }],
        anuladas: { cantidad: 1, total: 900 },
      }),
    );
    renderApp({ route: "/reportes/ventas-dia", user: duena });

    const tabla = await screen.findByRole("table", { name: "Ventas por medio de pago" });
    expect(within(tabla).getByText("Mercado Pago")).toBeInTheDocument();
    expect(screen.getByText(/Anuladas: 1 venta por/)).toBeInTheDocument();
  });

  it("el mostrador ve su alcance y no ve las secciones de la duena", async () => {
    mockVentasDia(ventasDia({ alcance: "propias", cantidad_ventas: 1, total_vendido: 1500, ticket_promedio: 1500 }));
    renderApp({ route: "/reportes/ventas-dia", user: mostrador });

    expect(await screen.findByText("Tus ventas de hoy")).toBeInTheDocument();
    expect(within(secciones()).getByRole("link", { name: "Reposición" })).toBeInTheDocument();
    expect(within(secciones()).queryByRole("link", { name: "Más vendidos" })).not.toBeInTheDocument();
    expect(within(secciones()).queryByRole("link", { name: "Márgenes" })).not.toBeInTheDocument();
  });

  it("sin ventas muestra ceros y el aviso", async () => {
    mockVentasDia(
      ventasDia({ cantidad_ventas: 0, total_vendido: 0, ticket_promedio: 0, unidades_vendidas: 0, por_metodo: [] }),
    );
    renderApp({ route: "/reportes/ventas-dia", user: duena });

    expect(await screen.findByText("No hubo ventas este día")).toBeInTheDocument();
    expect(screen.getAllByText(/\$\s0,00/).length).toBeGreaterThanOrEqual(2);
  });

  it("al elegir otra fecha consulta con ese dia", async () => {
    const consultas = mockVentasDia(ventasDia());
    const { user } = renderApp({ route: "/reportes/ventas-dia", user: duena });
    await screen.findByText(/\$\s5\.300,00/);

    await user.click(screen.getByRole("button", { name: "Día anterior" }));

    await waitFor(() => expect(consultas.length).toBeGreaterThanOrEqual(2));
    const ayer = new Date();
    ayer.setDate(ayer.getDate() - 1);
    expect(consultas.at(-1)?.get("fecha")).toBe(toIsoDate(ayer));
  });

  it("muestra un error con reintento si falla la carga", async () => {
    server.use(http.get("/api/reportes/ventas-dia", () => HttpResponse.json({ detail: "boom" }, { status: 500 })));
    renderApp({ route: "/reportes/ventas-dia", user: duena });

    expect(await screen.findByText("No pudimos cargar las ventas")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});

describe("Reposicion", () => {
  const reposicion: ReposicionReporte = {
    dias: 30,
    cobertura_max_dias: 7,
    items: [
      {
        producto_id: "p-1",
        sku: "RC-MINI-3KG",
        nombre: "Royal Canin Mini 3 kg",
        stock_actual: 2,
        stock_minimo: 5,
        bajo_minimo: true,
        unidades_vendidas: 15,
        venta_diaria: "0.50",
        cobertura_dias: 4,
        distribuidora_default_id: "d-1",
      },
      {
        producto_id: "p-2",
        sku: "JG-PELOTA",
        nombre: "Pelota de goma",
        stock_actual: 0,
        stock_minimo: 3,
        bajo_minimo: true,
        unidades_vendidas: 0,
        venta_diaria: 0,
        cobertura_dias: null,
        distribuidora_default_id: null,
      },
    ],
  };

  it("lista bajo minimo, cobertura y 'Sin ventas' con los parametros por defecto", async () => {
    const consultas: URLSearchParams[] = [];
    server.use(
      http.get("/api/reportes/reposicion", ({ request }) => {
        consultas.push(new URL(request.url).searchParams);
        return HttpResponse.json(reposicion);
      }),
    );
    renderApp({ route: "/reportes/reposicion", user: mostrador });

    await screen.findByText("Royal Canin Mini 3 kg");
    const tabla = screen.getByRole("table", { name: "Productos a reponer" });
    expect(within(tabla).getByText("Royal Canin Mini 3 kg")).toBeInTheDocument();
    expect(within(tabla).getByText("4 días")).toBeInTheDocument();
    expect(within(tabla).getByText("Sin ventas")).toBeInTheDocument();
    expect(within(tabla).getByText("Bajo mínimo")).toBeInTheDocument();
    expect(within(tabla).getByText("Sin stock")).toBeInTheDocument();
    expect(consultas[0]?.get("dias")).toBe("30");
    expect(consultas[0]?.get("cobertura_max_dias")).toBe("7");
  });

  it("'Crear pedido' navega a /compras con la distribuidora por defecto", async () => {
    server.use(http.get("/api/reportes/reposicion", () => HttpResponse.json(reposicion)));
    const { user } = renderApp({ route: "/reportes/reposicion", user: duena });

    await user.click(await screen.findByRole("button", { name: "Crear pedido de Royal Canin Mini 3 kg" }));

    // La pantalla de compras es de otro lote: alcanza con salir de Reposicion hacia /compras.
    await waitFor(() => expect(screen.queryByRole("table", { name: "Productos a reponer" })).not.toBeInTheDocument());
  });

  it("sin productos a reponer muestra el estado vacio", async () => {
    server.use(
      http.get("/api/reportes/reposicion", () => HttpResponse.json({ ...reposicion, items: [] })),
    );
    renderApp({ route: "/reportes/reposicion", user: duena });
    expect(await screen.findByText("No hay productos para reponer")).toBeInTheDocument();
  });
});

describe("Margenes y mas vendidos", () => {
  const margenes: MargenesReporte = {
    desde: "2026-09-08",
    hasta: "2026-10-07",
    totales: {
      ingresos: 10000,
      costo: 6000,
      margen_bruto: 4000,
      margen_pct: "0.6667",
      lineas_sin_costo: 2,
      ingresos_sin_costo: 800,
    },
    items: [
      {
        producto_id: "p-1",
        sku: "RC-MINI-3KG",
        nombre: "Royal Canin Mini 3 kg",
        unidades: 4,
        ingresos: 10000,
        costo: 6000,
        margen_bruto: 4000,
        margen_pct: "0.6667",
      },
      {
        producto_id: "p-2",
        sku: "OBS-1",
        nombre: "Obsequio sin costo",
        unidades: 1,
        ingresos: 0,
        costo: 0,
        margen_bruto: 0,
        margen_pct: null,
      },
    ],
    total: 2,
    page: 1,
    page_size: 20,
    total_pages: 1,
  };

  it("muestra totales, margen_pct null como raya y las lineas sin costo aparte", async () => {
    server.use(http.get("/api/reportes/margenes", () => HttpResponse.json(margenes)));
    renderApp({ route: "/reportes/margenes", user: duena });

    await screen.findByText("Obsequio sin costo");
    const tabla = screen.getByRole("table", { name: "Márgenes por producto" });
    const fila = within(tabla).getByText("Obsequio sin costo").closest("tr");
    expect(fila).not.toBeNull();
    expect(within(fila as HTMLElement).getByText("—")).toBeInTheDocument();
    expect(within(tabla).getByText("66,7%")).toBeInTheDocument();
    expect(screen.getByText("2 líneas sin costo informado")).toBeInTheDocument();
    expect(screen.getByText("Margen bruto", { selector: "p" }).parentElement).toHaveTextContent(/\$\s4\.000,00/);
    expect(screen.getByText("Margen sobre costo", { selector: "p" }).parentElement).toHaveTextContent("66,7%");
  });

  it("el mostrador no accede a Margenes ni a Mas vendidos", async () => {
    renderApp({ route: "/reportes/margenes", user: mostrador });
    expect(await screen.findByText("Sin permiso")).toBeInTheDocument();
  });

  it("Mas vendidos envia orden y limite elegidos, y respeta el periodo del servidor", async () => {
    const consultas: URLSearchParams[] = [];
    server.use(
      http.get("/api/reportes/mas-vendidos", ({ request }) => {
        consultas.push(new URL(request.url).searchParams);
        return HttpResponse.json({
          desde: "2026-09-08",
          hasta: "2026-10-07",
          orden: "cantidad",
          items: [{ producto_id: "p-1", sku: "S1", nombre: "Whiskas Adulto", activo: false, unidades: 9, monto: 4500 }],
        });
      }),
    );
    renderApp({ route: "/reportes/mas-vendidos", user: duena });

    await screen.findByText("Whiskas Adulto");
    const tabla = screen.getByRole("table", { name: "Productos más vendidos" });
    expect(within(tabla).getByText("Whiskas Adulto")).toBeInTheDocument();
    expect(within(tabla).getByText("Dado de baja")).toBeInTheDocument();
    expect(consultas[0]?.get("desde")).toBeNull();
    expect(consultas[0]?.get("hasta")).toBeNull();
    expect(consultas[0]?.get("orden")).toBe("cantidad");
    expect(consultas[0]?.get("limite")).toBe("10");
    expect(screen.getByText(/8\/9\/2026 al 7\/10\/2026/)).toBeInTheDocument();
  });
});
