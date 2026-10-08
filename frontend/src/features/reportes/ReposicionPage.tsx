import { PackageCheck, ShoppingBasket } from "lucide-react";
import { type ReactElement, useState } from "react";
import { useNavigate } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ReportesLayout } from "@/features/reportes/ReportesLayout";
import { REPOSICION_DEFAULTS, type ReposicionParams, useReposicion } from "@/features/reportes/api";
import { formatUnidadesDia, pedidoUrl } from "@/features/reportes/params";
import { StockBadge } from "@/features/stock/StockBadge";
import type { ReposicionItem } from "@/shared/api/types";
import { DataTable, type DataTableColumn } from "@/shared/components/DataTable";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";

const DIAS = [7, 15, 30, 60, 90, 180];
const COBERTURAS = [3, 7, 14, 30, 60, 90];

interface OpcionesProps {
  id: string;
  label: string;
  valor: number;
  opciones: number[];
  onChange: (valor: number) => void;
}

function SelectorDias({ id, label, valor, opciones, onChange }: OpcionesProps): ReactElement {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select value={String(valor)} onValueChange={(v) => onChange(Number(v))}>
        <SelectTrigger id={id} className="min-w-36">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {opciones.map((o) => (
            <SelectItem key={o} value={String(o)}>
              {o} días
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** Productos bajo minimo o con poca cobertura segun la rotacion; lo ven dueña y mostrador. */
export function ReposicionPage(): ReactElement {
  const navigate = useNavigate();
  const [params, setParams] = useState<ReposicionParams>(REPOSICION_DEFAULTS);
  const reporte = useReposicion(params);
  const items = reporte.data?.items;

  const columnas: DataTableColumn<ReposicionItem>[] = [
    {
      id: "producto",
      header: "Producto",
      cell: (p) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{p.nombre}</p>
          <p className="truncate font-mono text-xs text-muted-foreground">{p.sku}</p>
        </div>
      ),
    },
    {
      id: "estado",
      header: "Estado",
      cell: (p) =>
        p.bajo_minimo ? (
          <StockBadge stockActual={p.stock_actual} stockMinimo={p.stock_minimo} />
        ) : (
          <Badge variant="outline" className="border-warning/30 bg-warning-soft text-warning">
            Poca cobertura
          </Badge>
        ),
    },
    { id: "stock", header: "Stock", align: "right", cell: (p) => <span className="tabular-nums">{p.stock_actual}</span> },
    { id: "minimo", header: "Mínimo", align: "right", cell: (p) => <span className="tabular-nums">{p.stock_minimo}</span> },
    {
      id: "venta",
      header: "Venta diaria",
      align: "right",
      cell: (p) => <span className="tabular-nums">{formatUnidadesDia(p.venta_diaria)}</span>,
    },
    {
      id: "cobertura",
      header: "Cobertura",
      align: "right",
      cell: (p) =>
        p.cobertura_dias === null ? (
          <span className="text-muted-foreground">Sin ventas</span>
        ) : (
          <span className="tabular-nums">{p.cobertura_dias === 1 ? "1 día" : `${p.cobertura_dias} días`}</span>
        ),
    },
    {
      id: "accion",
      header: <span className="sr-only">Acción</span>,
      align: "right",
      cell: (p) => (
        <Button
          type="button"
          size="sm"
          variant="outline"
          aria-label={`Crear pedido de ${p.nombre}`}
          onClick={() => void navigate(pedidoUrl(p))}
        >
          <ShoppingBasket aria-hidden="true" />
          Crear pedido
        </Button>
      ),
    },
  ];

  const filtros = (
    <>
      <SelectorDias
        id="repo-dias"
        label="Ventas de los últimos"
        valor={params.dias}
        opciones={DIAS}
        onChange={(dias) => setParams((p) => ({ ...p, dias }))}
      />
      <SelectorDias
        id="repo-cobertura"
        label="Alcanza para menos de"
        valor={params.cobertura_max_dias}
        opciones={COBERTURAS}
        onChange={(cobertura_max_dias) => setParams((p) => ({ ...p, cobertura_max_dias }))}
      />
    </>
  );

  return (
    <ReportesLayout
      title="Reposición"
      description="Qué conviene pedir según el stock mínimo y el ritmo de ventas."
      filtros={filtros}
    >
      {reporte.isError && items === undefined ? (
        <ErrorState title="No pudimos cargar la reposición" onRetry={() => void reporte.refetch()} />
      ) : (
        <DataTable
          label="Productos a reponer"
          columns={columnas}
          rows={items}
          isLoading={reporte.isLoading}
          getRowKey={(p) => p.producto_id}
          empty={
            <EmptyState
              icon={PackageCheck}
              title="No hay productos para reponer"
              description="Todo tiene stock por encima del mínimo y cobertura suficiente con estos parámetros."
            />
          }
        />
      )}
    </ReportesLayout>
  );
}
