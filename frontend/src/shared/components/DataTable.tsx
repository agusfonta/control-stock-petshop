import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/shared/lib/utils";

export interface DataTableColumn<T> {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Importes y cantidades: `right`. */
  align?: "left" | "right" | "center";
  className?: string;
}

interface DataTablePagination {
  /** Pagina actual, base 1. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  /** `undefined` mientras no hay datos (junto con `isLoading`). */
  rows: T[] | undefined;
  getRowKey: (row: T) => string;
  isLoading?: boolean;
  skeletonRows?: number;
  /** Se muestra cuando no hay filas (tipicamente un `EmptyState`). */
  empty?: ReactNode;
  /** Nombre accesible de la tabla. */
  label: string;
  onRowClick?: (row: T) => void;
  pagination?: DataTablePagination;
  className?: string;
}

const ALIGN: Record<NonNullable<DataTableColumn<unknown>["align"]>, string> = {
  left: "text-left",
  right: "text-right",
  center: "text-center",
};

/** Tabla con esqueleto, vacio, paginacion y scroll horizontal interno (nunca de pagina). */
export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  isLoading = false,
  skeletonRows = 5,
  empty,
  label,
  onRowClick,
  pagination,
  className,
}: DataTableProps<T>): ReactElement {
  if (!isLoading && rows !== undefined && rows.length === 0 && empty !== undefined) {
    return <>{empty}</>;
  }
  const totalPages = pagination === undefined ? 1 : Math.max(1, Math.ceil(pagination.total / pagination.pageSize));

  return (
    <div className={cn("overflow-hidden rounded-xl border bg-card", className)}>
      <Table aria-label={label} aria-busy={isLoading}>
        <TableHeader className="bg-muted/50">
          <TableRow className="hover:bg-transparent">
            {columns.map((col) => (
              <TableHead
                key={col.id}
                className={cn("h-11 px-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase", ALIGN[col.align ?? "left"], col.className)}
              >
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading || rows === undefined
            ? Array.from({ length: skeletonRows }, (_, i) => (
                <TableRow key={`sk-${i}`} className="h-12 hover:bg-transparent">
                  {columns.map((col) => (
                    <TableCell key={col.id} className="px-4">
                      <Skeleton className="h-4 w-full max-w-40" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            : rows.map((row) => (
                <TableRow
                  key={getRowKey(row)}
                  className={cn("h-12 pointer-coarse:h-14", onRowClick !== undefined && "cursor-pointer")}
                  onClick={onRowClick === undefined ? undefined : () => onRowClick(row)}
                >
                  {columns.map((col) => (
                    <TableCell key={col.id} className={cn("px-4", ALIGN[col.align ?? "left"], col.className)}>
                      {col.cell(row)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
        </TableBody>
      </Table>
      {pagination !== undefined && (
        <nav aria-label="Paginación" className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm">
          <p className="text-muted-foreground" aria-live="polite">
            {pagination.total === 1 ? "1 resultado" : `${pagination.total} resultados`}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground tabular-nums">
              Página {pagination.page} de {totalPages}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
            >
              <ChevronLeft aria-hidden="true" />
              Anterior
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={pagination.page >= totalPages}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
            >
              Siguiente
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </nav>
      )}
    </div>
  );
}
