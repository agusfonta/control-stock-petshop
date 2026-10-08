import { Ban, CalendarX2, ChevronLeft, ChevronRight, Package, Receipt, Ticket, Wallet } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { METODO_LABEL } from "@/features/pos/comprobanteFormat";
import { ReportesLayout } from "@/features/reportes/ReportesLayout";
import { useVentasDia } from "@/features/reportes/api";
import { fechaLegible, toIsoDate } from "@/features/reportes/params";
import type { VentasDiaReporte } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { KpiCard } from "@/shared/components/KpiCard";
import { MoneyText } from "@/shared/components/MoneyText";
import { toCents } from "@/shared/lib/money";

type FilaMetodo = VentasDiaReporte["por_metodo"][number];

/** `mp` solo aparece si tuvo monto (decision por defecto 12). */
export function metodosVisibles(filas: FilaMetodo[]): FilaMetodo[] {
  return filas.filter((f) => f.metodo !== "mp" || toCents(f.monto) > 0);
}

function moverDia(iso: string, delta: number): string {
  const [y = 0, m = 1, d = 1] = iso.split("-").map(Number);
  return toIsoDate(new Date(y, m - 1, d + delta));
}

const COLUMNAS: DataTableColumn<FilaMetodo>[] = [
  { id: "metodo", header: "Medio de pago", cell: (f) => <span className="font-medium">{METODO_LABEL[f.metodo]}</span> },
  { id: "pagos", header: "Pagos", align: "right", cell: (f) => <span className="tabular-nums">{f.cantidad_pagos}</span> },
  { id: "monto", header: "Monto", align: "right", cell: (f) => <MoneyText value={f.monto} /> },
];

/** Ventas de un dia: indicadores, desglose por medio y anuladas; el mostrador ve solo las propias (UX11). */
export function VentasDiaPage(): ReactElement {
  const hoy = toIsoDate(new Date());
  const [fecha, setFecha] = useState(hoy);
  const dia = fecha === "" ? hoy : fecha;
  const reporte = useVentasDia(dia);
  const data = reporte.data;
  const propias = data?.alcance === "propias";
  const esHoy = dia === hoy;

  const filtros = (
    <>
      <div className="space-y-1.5">
        <Label htmlFor="reporte-fecha">Fecha</Label>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="icon" aria-label="Día anterior" onClick={() => setFecha(moverDia(dia, -1))}>
            <ChevronLeft aria-hidden="true" />
          </Button>
          <Input
            id="reporte-fecha"
            type="date"
            value={fecha}
            max={hoy}
            onChange={(e) => setFecha(e.target.value)}
            className="w-auto min-w-40"
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label="Día siguiente"
            disabled={dia >= hoy}
            onClick={() => setFecha(moverDia(dia, 1))}
          >
            <ChevronRight aria-hidden="true" />
          </Button>
        </div>
      </div>
      <Button type="button" variant="outline" disabled={esHoy} onClick={() => setFecha(hoy)}>
        Hoy
      </Button>
    </>
  );

  return (
    <ReportesLayout
      title="Ventas del día"
      description={
        propias
          ? "Solo se cuentan las ventas que hiciste vos."
          : "Resumen de ventas confirmadas, por fecha."
      }
      filtros={filtros}
    >
      {reporte.isError && data === undefined ? (
        <ErrorState title="No pudimos cargar las ventas" onRetry={() => void reporte.refetch()} />
      ) : data === undefined ? (
        <p role="status" className="text-sm text-muted-foreground">
          Cargando ventas…
        </p>
      ) : (
        <Contenido data={data} esHoy={dia === hoy} />
      )}
    </ReportesLayout>
  );
}

function Contenido({ data, esHoy }: { data: VentasDiaReporte; esHoy: boolean }): ReactElement {
  const propias = data.alcance === "propias";
  const metodos = metodosVisibles(data.por_metodo);
  const anuladas = data.anuladas;
  return (
    <>
      <p className="text-sm font-medium" aria-live="polite">
        {propias ? (esHoy ? "Tus ventas de hoy" : `Tus ventas del ${fechaLegible(data.fecha)}`) : `Ventas del ${fechaLegible(data.fecha)}`}
      </p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Ventas" value={data.cantidad_ventas} icon={Receipt} />
        <KpiCard label="Total vendido" value={<MoneyText value={data.total_vendido} />} icon={Wallet} />
        <KpiCard label="Ticket promedio" value={<MoneyText value={data.ticket_promedio} />} icon={Ticket} />
        <KpiCard label="Unidades" value={data.unidades_vendidas} icon={Package} />
      </div>
      {data.cantidad_ventas === 0 ? (
        <EmptyState
          icon={CalendarX2}
          title="No hubo ventas este día"
          description={propias ? "Probá con otra fecha para ver tus ventas." : "Probá con otra fecha o revisá que las ventas estén confirmadas."}
        />
      ) : (
        <section aria-labelledby="por-medio" className="space-y-2">
          <h2 id="por-medio" className="text-base font-semibold">
            Por medio de pago
          </h2>
          <DataTable label="Ventas por medio de pago" columns={COLUMNAS} rows={metodos} getRowKey={(f) => f.metodo} />
        </section>
      )}
      {anuladas.cantidad > 0 && (
        <p className="flex items-center gap-2 rounded-xl border bg-card px-4 py-3 text-sm text-muted-foreground">
          <Ban className="size-4 shrink-0" aria-hidden="true" />
          <span>
            Anuladas: {anuladas.cantidad === 1 ? "1 venta" : `${anuladas.cantidad} ventas`} por <MoneyText value={anuladas.total} />
            . No están incluidas en los totales de arriba.
          </span>
        </p>
      )}
    </>
  );
}
