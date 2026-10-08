import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Comprobante } from "@/features/pos/Comprobante";
import { makeLineaVenta, makePagoVenta, makeVenta } from "@/features/ventas/testData";

const venta = makeVenta({
  total: "8300.00",
  lineas: [
    makeLineaVenta({ id: "l1", producto_nombre: "Royal Canin Mini Adult 3 kg", cantidad: 2, precio_unit: "3800.00", subtotal: "7600.00" }),
    makeLineaVenta({ id: "l2", producto_nombre: "Pelota chica", cantidad: 1, precio_unit: "700.00", subtotal: "700.00" }),
  ],
  pagos: [
    makePagoVenta({ id: "g1", metodo: "efectivo", monto: "5000.00" }),
    makePagoVenta({ id: "g2", metodo: "tarjeta", monto: "3300.00" }),
  ],
});

describe("Comprobante", () => {
  it("muestra comercio, numero corto, cliente, lineas, total, pagos y la leyenda", () => {
    render(<Comprobante venta={venta} clienteNombre="Ana Perez" />);
    expect(screen.getByRole("heading", { name: "Animall" })).toBeInTheDocument();
    expect(screen.getByText(/A1B2C3D4/)).toBeInTheDocument();
    expect(screen.getByText(/Ana Perez/)).toBeInTheDocument();
    const lineas = screen.getByRole("table", { name: /productos/i });
    expect(within(lineas).getByText("Royal Canin Mini Adult 3 kg")).toBeInTheDocument();
    expect(within(lineas).getByText(/^2 x .*3\.800,00$/)).toBeInTheDocument();
    expect(within(lineas).getByText(/7\.600,00/)).toBeInTheDocument();
    expect(screen.getByText("Total").closest("div")).toHaveTextContent("8.300,00");
    expect(screen.getByText("Efectivo").closest("div")).toHaveTextContent("5.000,00");
    expect(screen.getByText("Tarjeta").closest("div")).toHaveTextContent("3.300,00");
    expect(screen.getByText("Comprobante no válido como factura")).toBeInTheDocument();
  });

  it("incluye el vuelto solo si se informa", () => {
    const { rerender } = render(<Comprobante venta={venta} vueltoCents={170000} />);
    expect(screen.getByText("Vuelto").closest("div")).toHaveTextContent("1.700,00");
    rerender(<Comprobante venta={venta} />);
    expect(screen.queryByText("Vuelto")).not.toBeInTheDocument();
  });

  it("no incluye datos fiscales ni cliente cuando no hay", () => {
    render(<Comprobante venta={venta} />);
    expect(screen.queryByText(/CAE|CUIT|Factura [ABC]/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Cliente/)).not.toBeInTheDocument();
  });

  it("marca las ventas anuladas", () => {
    render(<Comprobante venta={{ ...venta, estado: "anulada" }} />);
    expect(screen.getByText("ANULADA")).toBeInTheDocument();
  });
});
