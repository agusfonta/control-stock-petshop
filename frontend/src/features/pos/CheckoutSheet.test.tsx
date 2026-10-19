import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { type ReactElement, useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CheckoutSheet } from "@/features/pos/CheckoutSheet";
import { useCartStore } from "@/features/pos/useCartStore";
import { makeLineaVenta, makeVenta } from "@/features/ventas/testData";
import type { Venta } from "@/shared/api/types";
import { makeProducto } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const royal = makeProducto({ id: "p-1", precio_venta: "3800.00", stock_actual: 5 });
const caro = makeProducto({ id: "p-2", precio_venta: "38500.00", stock_actual: 5 });
const onSuccess = vi.fn<(venta: Venta, vuelto: number | null) => void>();
const onOpenChange = vi.fn<(open: boolean) => void>();

function Host(): ReactElement {
  const [open, setOpen] = useState(true);
  return (
    <CheckoutSheet
      open={open}
      onOpenChange={(v) => {
        onOpenChange(v);
        setOpen(v);
      }}
      onSuccess={onSuccess}
    />
  );
}

interface Capturas {
  borradores: number;
  confirmaciones: unknown[];
}

const BORRADOR_CARO: Partial<Venta> = {
  total: "38500.00",
  lineas: [makeLineaVenta({ producto_id: "p-2", precio_unit: "38500.00", subtotal: "38500.00" })],
};

function montarApi(confirmar?: (n: number) => Response, borrador: Partial<Venta> = {}): Capturas {
  const c: Capturas = { borradores: 0, confirmaciones: [] };
  server.use(
    http.post("/api/ventas", () => {
      c.borradores += 1;
      return HttpResponse.json(makeVenta({ id: "v-1", estado: "borrador", ...borrador }), { status: 201 });
    }),
    http.post("/api/ventas/:id/confirmar", async ({ request }) => {
      c.confirmaciones.push(await request.json());
      return confirmar?.(c.confirmaciones.length) ?? HttpResponse.json(makeVenta({ id: "v-1" }));
    }),
    http.get("/api/stock/alertas", () => HttpResponse.json({ total_bajo_minimo: 0, items: [] })),
  );
  return c;
}

const ESPERA = { timeout: 4000 };

beforeEach(() => {
  onSuccess.mockReset();
  onOpenChange.mockReset();
  useCartStore.getState().clear();
  useCartStore.getState().addProduct(royal, 1);
});

function filas(): HTMLElement[] {
  return Array.from(document.body.querySelectorAll<HTMLElement>("[data-pago-row]"));
}

function fila(indice: number): HTMLElement {
  const f = filas()[indice];
  if (f === undefined) throw new Error(`falta la fila ${indice + 1}`);
  return f;
}

function cargarCaro(): void {
  useCartStore.getState().clear();
  useCartStore.getState().addProduct(caro, 1);
}

describe("CheckoutSheet: pagos", () => {
  it("propone efectivo por el total y habilita Confirmar venta, sin campo de monto de efectivo", async () => {
    renderWithProviders(<Host />);
    expect(await screen.findByRole("textbox", { name: "Paga con" })).toHaveValue("");
    expect(screen.queryByRole("textbox", { name: /monto efectivo/i })).toBeNull();
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 3.800,00");
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeEnabled();
  });

  it("ofrece solo efectivo, transferencia y tarjeta", async () => {
    renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    const medios = screen.getAllByRole("radio").map((r) => r.textContent?.trim());
    expect(medios).toEqual(["Efectivo", "Transferencia", "Tarjeta"]);
  });

  it("paga con $ 5.000 muestra el vuelto y confirma con un pago efectivo de 3800", async () => {
    const api = montarApi();
    const { user } = renderWithProviders(<Host />);
    await user.type(await screen.findByRole("textbox", { name: /paga con/i }), "5000");
    expect(screen.getByText(/vuelto/i).closest("div")).toHaveTextContent(/1\.200,00/);
    await user.click(screen.getByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), ESPERA);
    expect(api.confirmaciones).toEqual([{ pagos: [{ metodo: "efectivo", monto: "3800.00" }] }]);
    expect(onSuccess.mock.calls[0]?.[1]).toBe(120000);
    expect(useCartStore.getState().lineas).toHaveLength(0);
  });

  it("pago dividido incompleto (transferencia + tarjeta, sin efectivo) muestra 'Faltan' y deshabilita la confirmacion", async () => {
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(within(fila(0)).getByRole("radio", { name: /transferencia/i }));
    const transferencia = screen.getByRole("textbox", { name: /monto transferencia/i });
    await user.clear(transferencia);
    await user.type(transferencia, "1800");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    await user.click(within(fila(1)).getByRole("radio", { name: /tarjeta/i }));
    const tarjeta = screen.getByRole("textbox", { name: /monto tarjeta/i });
    await user.clear(tarjeta);
    await user.type(tarjeta, "1500");
    expect(screen.getByText(/faltan/i)).toHaveTextContent("$ 500,00");
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeDisabled();
  });

  it("muestra 'Sobran' y bloquea la confirmacion cuando los otros medios superan el total (efectivo derivado 0)", async () => {
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    await user.type(screen.getByRole("textbox", { name: /monto transferencia/i }), "4000");
    expect(screen.getByText(/sobran/i)).toHaveTextContent("$ 200,00");
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 0,00");
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeDisabled();
  });

  it("con los otros medios justo en el total el efectivo derivado es 0 y tampoco se confirma", async () => {
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    await user.type(screen.getByRole("textbox", { name: /monto transferencia/i }), "3800");
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 0,00");
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeDisabled();
  });

  it("un medio ya usado queda deshabilitado en las otras filas y 'Agregar otro medio' se deshabilita con 3", async () => {
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    expect(within(fila(1)).getByRole("radio", { name: /efectivo/i })).toBeDisabled();
    expect(within(fila(0)).getByRole("radio", { name: /transferencia/i })).toBeDisabled();
    expect(within(fila(0)).getByRole("radio", { name: /tarjeta/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /agregar otro medio/i })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    expect(filas()).toHaveLength(3);
    expect(screen.getByRole("button", { name: /agregar otro medio/i })).toBeDisabled();
    expect(screen.getAllByRole("textbox", { name: /paga con/i })).toHaveLength(1);
  });
});

describe("CheckoutSheet: confirmacion", () => {
  it("409 con faltantes marca 'Disponible' en el carrito, conserva las lineas y cierra el panel", async () => {
    montarApi(() =>
      HttpResponse.json(
        { detail: { mensaje: "Stock insuficiente", faltantes: [{ producto_id: "p-1", solicitado: 3, disponible: 1 }] } },
        { status: 409 },
      ),
    );
    const { user } = renderWithProviders(<Host />);
    await user.click(await screen.findByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false), ESPERA);
    expect(useCartStore.getState().lineas[0]).toMatchObject({ productoId: "p-1", disponible: 1 });
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("error de red + Reintentar envia la misma idempotency_key y los mismos pagos: una sola venta", async () => {
    const api = montarApi((n) => (n === 1 ? HttpResponse.error() : HttpResponse.json(makeVenta({ id: "v-1" }))));
    const { user } = renderWithProviders(<Host />);
    await user.click(await screen.findByRole("button", { name: /confirmar venta/i }));
    const reintentar = await screen.findByRole("button", { name: /reintentar/i }, ESPERA);
    const clave = useCartStore.getState().checkout?.idempotencyKey;
    await user.click(reintentar);
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1), ESPERA);
    expect(api.borradores).toBe(1);
    expect(api.confirmaciones).toHaveLength(2);
    expect(api.confirmaciones[1]).toEqual(api.confirmaciones[0]);
    expect(useCartStore.getState().checkout).toBeNull();
    expect(clave).toBeDefined();
  });

  it("un 422 se muestra en el panel y deja corregir los pagos", async () => {
    montarApi(() => HttpResponse.json({ detail: "La suma de pagos no coincide" }, { status: 422 }));
    const { user } = renderWithProviders(<Host />);
    await user.click(await screen.findByRole("button", { name: /confirmar venta/i }));
    expect(await screen.findByText("La suma de pagos no coincide", undefined, ESPERA)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeEnabled();
  });
});

describe("CheckoutSheet: Paga con dentro de la fila de efectivo", () => {
  it("la fila de efectivo tiene solo 'Paga con' y no hay tarjeta 'Paga con' aparte", async () => {
    renderWithProviders(<Host />);
    const paga = await screen.findByRole("textbox", { name: "Paga con" });
    const contenedor = paga.closest<HTMLElement>("[data-pago-row]");
    expect(contenedor).not.toBeNull();
    if (contenedor === null) return;
    expect(within(contenedor).getAllByRole("textbox")).toHaveLength(1);
    expect(screen.getAllByText("Paga con")).toHaveLength(1);
  });

  it("pago mixto: efectivo a cobrar derivado, vuelto solo sobre el efectivo y pagos exactos", async () => {
    cargarCaro();
    const api = montarApi(undefined, BORRADOR_CARO);
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    await user.type(screen.getByRole("textbox", { name: /monto transferencia/i }), "18500");
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 20.000,00");
    expect(screen.getAllByRole("textbox", { name: /paga con/i })).toHaveLength(1);
    await user.type(screen.getByRole("textbox", { name: /paga con/i }), "25000");
    expect(screen.getByText(/vuelto/i).closest("div")).toHaveTextContent(/5\.000,00/);
    await user.click(screen.getByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), ESPERA);
    expect(api.confirmaciones).toEqual([
      { pagos: [{ metodo: "efectivo", monto: "20000.00" }, { metodo: "transferencia", monto: "18500.00" }] },
    ]);
    expect(onSuccess.mock.calls[0]?.[1]).toBe(500000);
  });

  it("quitar la fila de efectivo descarta su 'paga con' y al volver a agregarla arranca vacia", async () => {
    cargarCaro();
    const api = montarApi(undefined, BORRADOR_CARO);
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    await user.type(screen.getByRole("textbox", { name: /monto transferencia/i }), "18500");
    await user.type(screen.getByRole("textbox", { name: /paga con/i }), "25000");
    await user.click(within(fila(0)).getByRole("button", { name: /quitar pago efectivo/i }));
    expect(filas()).toHaveLength(1);
    expect(screen.queryByRole("textbox", { name: /paga con/i })).toBeNull();
    expect(screen.getByText(/faltan/i)).toHaveTextContent("$ 20.000,00");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    expect(screen.getByRole("textbox", { name: /paga con/i })).toHaveValue("");
    expect(screen.queryByText(/vuelto/i)).toBeNull();
    await user.click(screen.getByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), ESPERA);
    expect(api.confirmaciones).toEqual([
      { pagos: [{ metodo: "transferencia", monto: "18500.00" }, { metodo: "efectivo", monto: "20000.00" }] },
    ]);
    expect(onSuccess.mock.calls[0]?.[1]).toBeNull();
  });

  it("cambiar una fila a otro medio descarta su 'paga con' aunque vuelva a efectivo", async () => {
    const { user } = renderWithProviders(<Host />);
    await user.type(await screen.findByRole("textbox", { name: /paga con/i }), "5000");
    await user.click(within(fila(0)).getByRole("radio", { name: /transferencia/i }));
    expect(screen.queryByRole("textbox", { name: /paga con/i })).toBeNull();
    await user.click(within(fila(0)).getByRole("radio", { name: /efectivo/i }));
    expect(screen.getByRole("textbox", { name: /paga con/i })).toHaveValue("");
    expect(screen.queryByText(/vuelto/i)).toBeNull();
  });

  it("el foco inicial va a 'Paga con' y Enter confirma", async () => {
    montarApi();
    const { user } = renderWithProviders(<Host />);
    const paga = await screen.findByRole("textbox", { name: /paga con/i });
    await waitFor(() => expect(paga).toHaveFocus());
    await user.keyboard("5000{Enter}");
    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), ESPERA);
    expect(onSuccess.mock.calls[0]?.[1]).toBe(120000);
  });
});

describe("CheckoutSheet: Paga con, casos borde", () => {
  it("paga con menor al efectivo muestra el aviso y no informa vuelto", async () => {
    montarApi();
    const { user } = renderWithProviders(<Host />);
    await user.type(await screen.findByRole("textbox", { name: /paga con/i }), "3000");
    expect(screen.getByText("Lo que recibís es menos que el efectivo a cobrar.")).toBeInTheDocument();
    expect(screen.queryByText(/vuelto/i)).toBeNull();
    await user.click(screen.getByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), ESPERA);
    expect(onSuccess.mock.calls[0]?.[1]).toBeNull();
  });

  it("paga con vacio confirma con vuelto null", async () => {
    montarApi();
    const { user } = renderWithProviders(<Host />);
    await user.click(await screen.findByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), ESPERA);
    expect(onSuccess.mock.calls[0]?.[1]).toBeNull();
  });

  it("cambiar el monto de otro medio recalcula el efectivo a cobrar, los atajos y el vuelto", async () => {
    cargarCaro();
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    const transferencia = screen.getByRole("textbox", { name: /monto transferencia/i });
    await user.type(transferencia, "18500");
    expect(within(fila(0)).getByRole("button", { name: /20\.000,00/ })).toBeInTheDocument();
    await user.click(within(fila(0)).getByRole("button", { name: /25\.000,00/ }));
    expect(within(fila(0)).getByText(/vuelto/i).closest("div")).toHaveTextContent(/5\.000,00/);
    await user.clear(transferencia);
    await user.type(transferencia, "16500");
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 22.000,00");
    expect(within(fila(0)).getByText(/vuelto/i).closest("div")).toHaveTextContent(/3\.000,00/);
    expect(within(fila(0)).getByRole("button", { name: /22\.000,00/ })).toBeInTheDocument();
  });

  it("'Completar' solo existe para medios que no son efectivo", async () => {
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    expect(screen.queryByRole("button", { name: "Completar" })).toBeNull();
    await user.click(within(fila(0)).getByRole("radio", { name: /transferencia/i }));
    const monto = screen.getByRole("textbox", { name: /monto transferencia/i });
    await user.clear(monto);
    await user.type(monto, "1000");
    await user.click(screen.getByRole("button", { name: "Completar" }));
    expect(monto).toHaveValue("3800");
  });
});

describe("CheckoutSheet: el segundo medio se autocompleta con lo que falta", () => {
  const diezMil = makeProducto({ id: "p-3", precio_venta: "10000.00", stock_actual: 5 });
  const BORRADOR_DIEZ_MIL: Partial<Venta> = {
    total: "10000.00",
    lineas: [makeLineaVenta({ producto_id: "p-3", precio_unit: "10000.00", subtotal: "10000.00" })],
  };

  beforeEach(() => {
    useCartStore.getState().clear();
    useCartStore.getState().addProduct(diezMil, 1);
  });

  it("paga con 9000 sobre 10.000: la transferencia nace con 1000, sin vuelto, y se confirma con los pagos esperados", async () => {
    const api = montarApi(undefined, BORRADOR_DIEZ_MIL);
    const { user } = renderWithProviders(<Host />);
    await user.type(await screen.findByRole("textbox", { name: "Paga con" }), "9000");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    expect(screen.getByRole("textbox", { name: /monto transferencia/i })).toHaveValue("1000");
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 9.000,00");
    expect(screen.queryByText(/vuelto/i)).toBeNull();
    await user.click(screen.getByRole("button", { name: /confirmar venta/i }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), ESPERA);
    expect(api.confirmaciones).toEqual([
      { pagos: [{ metodo: "efectivo", monto: "9000.00" }, { metodo: "transferencia", monto: "1000.00" }] },
    ]);
    expect(onSuccess.mock.calls[0]?.[1]).toBeNull();
  });

  it("editar el monto sugerido recalcula el efectivo a cobrar", async () => {
    const { user } = renderWithProviders(<Host />);
    await user.type(await screen.findByRole("textbox", { name: "Paga con" }), "9000");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    const monto = screen.getByRole("textbox", { name: /monto transferencia/i });
    await user.clear(monto);
    await user.type(monto, "2500");
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 7.500,00");
    expect(screen.getByRole("button", { name: /confirmar venta/i })).toBeEnabled();
  });

  it("con 'Paga con' vacio el monto del nuevo medio arranca vacio", async () => {
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    expect(screen.getByRole("textbox", { name: /monto transferencia/i })).toHaveValue("");
  });

  it("con 'Paga con' igual o mayor al total el monto del nuevo medio arranca vacio", async () => {
    const { user } = renderWithProviders(<Host />);
    const paga = await screen.findByRole("textbox", { name: "Paga con" });
    await user.type(paga, "12000");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    expect(screen.getByRole("textbox", { name: /monto transferencia/i })).toHaveValue("");
    await user.click(within(fila(1)).getByRole("button", { name: /quitar pago transferencia/i }));
    await user.clear(paga);
    await user.type(paga, "10000");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    expect(screen.getByRole("textbox", { name: /monto transferencia/i })).toHaveValue("");
  });

  it("quitar la fila sugerida devuelve el efectivo al total", async () => {
    const { user } = renderWithProviders(<Host />);
    await user.type(await screen.findByRole("textbox", { name: "Paga con" }), "9000");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    await user.click(within(fila(1)).getByRole("button", { name: /quitar pago transferencia/i }));
    expect(filas()).toHaveLength(1);
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 10.000,00");
  });

  it("sin efectivo en juego se mantiene la sugerencia 'lo que falta' y 'Completar' sigue funcionando", async () => {
    const { user } = renderWithProviders(<Host />);
    await screen.findByRole("textbox", { name: "Paga con" });
    await user.click(within(fila(0)).getByRole("radio", { name: /transferencia/i }));
    const transferencia = screen.getByRole("textbox", { name: /monto transferencia/i });
    await user.clear(transferencia);
    await user.type(transferencia, "4000");
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    await user.click(within(fila(1)).getByRole("radio", { name: /tarjeta/i }));
    const tarjeta = screen.getByRole("textbox", { name: /monto tarjeta/i });
    await user.clear(tarjeta);
    await user.type(tarjeta, "1000");
    await user.click(screen.getAllByRole("button", { name: "Completar" })[1] as HTMLElement);
    expect(tarjeta).toHaveValue("6000");
    await user.click(screen.getByRole("button", { name: /quitar pago tarjeta/i }));
    await user.click(screen.getByRole("button", { name: /agregar otro medio/i }));
    expect(within(fila(1)).getByRole("radio", { name: /efectivo/i })).toBeChecked();
    expect(screen.getByText(/^efectivo a cobrar/i)).toHaveTextContent("$ 6.000,00");
  });
});
