import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { KpiCard } from "@/shared/components/KpiCard";
import { MoneyText } from "@/shared/components/MoneyText";

interface Fila {
  id: string;
  nombre: string;
}
const columnas: DataTableColumn<Fila>[] = [{ id: "nombre", header: "Nombre", cell: (f) => f.nombre }];
const filas: Fila[] = [
  { id: "1", nombre: "Alimento" },
  { id: "2", nombre: "Juguete" },
];

describe("MoneyText", () => {
  it("formatea pesos argentinos desde numero y desde string", () => {
    const { rerender } = render(<MoneyText value={24999.5} />);
    expect(screen.getByText(/24\.999,50/)).toBeInTheDocument();
    rerender(<MoneyText value="380050.00" />);
    expect(screen.getByText(/380\.050,00/)).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("muestra el titulo y Reintentar llama al callback", async () => {
    const onRetry = vi.fn();
    render(<ErrorState title="No pudimos cargar los clientes" onRetry={onRetry} />);

    expect(screen.getByText("No pudimos cargar los clientes")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("sin onRetry no muestra el boton", () => {
    render(<ErrorState title="Error" />);
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
  });
});

describe("EmptyState y KpiCard", () => {
  it("EmptyState muestra explicacion y accion", () => {
    render(<EmptyState title="Sin distribuidoras" description="Todavía no cargaste ninguna." action={<button>Nueva distribuidora</button>} />);
    expect(screen.getByText("Todavía no cargaste ninguna.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nueva distribuidora" })).toBeInTheDocument();
  });

  it("KpiCard muestra etiqueta, valor y pista", () => {
    render(<KpiCard label="Ventas" value="2" hint="Hoy" />);
    expect(screen.getByText("Ventas")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Hoy")).toBeInTheDocument();
  });
});

describe("ConfirmDialog", () => {
  it("solo ejecuta la accion al confirmar", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="¿Dar de baja?"
        description="El cliente deja de aparecer."
        confirmLabel="Dar de baja"
        destructive
        onConfirm={onConfirm}
      />,
    );
    const dialog = screen.getByRole("alertdialog");

    await userEvent.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(onConfirm).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByRole("button", { name: "Dar de baja" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe("DataTable", () => {
  it("renderiza filas y llama onRowClick", async () => {
    const onRowClick = vi.fn();
    render(<DataTable label="Productos" columns={columnas} rows={filas} getRowKey={(f) => f.id} onRowClick={onRowClick} />);

    await userEvent.click(screen.getByText("Juguete"));

    expect(onRowClick).toHaveBeenCalledWith(filas[1]);
  });

  it("muestra esqueleto mientras carga y no las filas", () => {
    render(<DataTable label="Productos" columns={columnas} rows={undefined} isLoading getRowKey={(f) => f.id} />);
    expect(screen.getByRole("table", { name: "Productos" })).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByText("Alimento")).not.toBeInTheDocument();
  });

  it("sin filas muestra el estado vacio", () => {
    render(
      <DataTable label="Productos" columns={columnas} rows={[]} getRowKey={(f) => f.id} empty={<p>Nada para mostrar</p>} />,
    );
    expect(screen.getByText("Nada para mostrar")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("pagina: total, pagina actual y botones habilitados segun los limites", async () => {
    const onPageChange = vi.fn();
    render(
      <DataTable
        label="Productos"
        columns={columnas}
        rows={filas}
        getRowKey={(f) => f.id}
        pagination={{ page: 1, pageSize: 20, total: 45, onPageChange }}
      />,
    );

    expect(screen.getByText("45 resultados")).toBeInTheDocument();
    expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /anterior/i })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /siguiente/i }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});
