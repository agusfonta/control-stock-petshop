import { ArrowLeft, ClipboardList, Pencil, Wallet } from "lucide-react";
import { type ReactElement, useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DistribuidoraSheet } from "@/features/distribuidoras/DistribuidoraSheet";
import { ListaPrecios } from "@/features/distribuidoras/ListaPrecios";
import { useCuenta, useDistribuidora } from "@/features/distribuidoras/api";
import { ApiError } from "@/shared/api/errors";
import { ErrorState } from "@/shared/components/ErrorState";
import { KpiCard } from "@/shared/components/KpiCard";
import { MoneyText } from "@/shared/components/MoneyText";
import { PageHeader } from "@/shared/components/PageHeader";
import { toCents } from "@/shared/lib/money";
import { useCan } from "@/shared/lib/permissions";

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string | null }): ReactElement {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="mt-0.5 text-sm">{valor ?? <span className="text-muted-foreground">—</span>}</dd>
    </div>
  );
}

/** Ficha de una distribuidora: datos, lista de precios y (solo dueña) su cuenta. */
export function DistribuidoraDetallePage(): ReactElement {
  const { id = "" } = useParams();
  const puedeEditar = useCan("distribuidoras.editar");
  const puedeVerCuenta = useCan("compras.pagos");
  const distribuidora = useDistribuidora(id);
  const cuenta = useCuenta(id, puedeVerCuenta);
  const [editando, setEditando] = useState(false);

  const volver = (
    <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
      <Link to="/distribuidoras">
        <ArrowLeft aria-hidden="true" /> Distribuidoras
      </Link>
    </Button>
  );

  if (distribuidora.isLoading) {
    return (
      <>
        {volver}
        <Skeleton className="h-24 w-full rounded-xl" />
      </>
    );
  }
  if (distribuidora.isError || distribuidora.data === undefined) {
    const noExiste = distribuidora.error instanceof ApiError && distribuidora.error.status === 404;
    return (
      <>
        {volver}
        <ErrorState
          title={noExiste ? "No encontramos esa distribuidora" : "No pudimos cargar la distribuidora"}
          description={noExiste ? "Puede que haya sido dada de baja." : undefined}
          onRetry={noExiste ? undefined : () => void distribuidora.refetch()}
        />
      </>
    );
  }

  const d = distribuidora.data;
  const saldo = cuenta.data === undefined ? 0 : toCents(cuenta.data.saldo);
  return (
    <>
      {volver}
      <PageHeader
        title={d.nombre}
        description={d.activo ? undefined : "Distribuidora dada de baja"}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to={`/compras?nuevo=1&distribuidora=${d.id}`}>
                <ClipboardList aria-hidden="true" /> Hacer un pedido
              </Link>
            </Button>
            {puedeEditar && (
              <Button type="button" variant="outline" onClick={() => setEditando(true)}>
                <Pencil aria-hidden="true" /> Editar
              </Button>
            )}
          </>
        }
      />
      <div className="space-y-6">
        <Card>
          <CardContent>
            <dl className="grid gap-4 sm:grid-cols-3">
              <Dato etiqueta="Contacto" valor={d.contacto} />
              <Dato etiqueta="CUIT" valor={d.cuit} />
              <Dato etiqueta="Condiciones" valor={d.condiciones} />
            </dl>
          </CardContent>
        </Card>
        {puedeVerCuenta && (
          <section aria-label="Cuenta" className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Cuenta</h2>
              <Button asChild variant="outline" size="sm">
                <Link to={`/compras?tab=pagos&nuevo=1&distribuidora=${d.id}`}>
                  <Wallet aria-hidden="true" /> Registrar pago
                </Link>
              </Button>
            </div>
            {cuenta.isError ? (
              <ErrorState title="No pudimos cargar la cuenta" onRetry={() => void cuenta.refetch()} />
            ) : (
              <div className="grid gap-3 sm:grid-cols-3">
                <KpiCard label="Recibido" value={<MoneyText value={cuenta.data?.total_recibido ?? 0} />} />
                <KpiCard label="Pagado" value={<MoneyText value={cuenta.data?.total_pagado ?? 0} />} />
                <KpiCard
                  label={saldo > 0 ? "Saldo deudor" : "Saldo"}
                  value={<MoneyText value={cuenta.data?.saldo ?? 0} className={saldo > 0 ? "text-destructive" : undefined} />}
                />
              </div>
            )}
          </section>
        )}
        <ListaPrecios distribuidoraId={d.id} />
      </div>
      <DistribuidoraSheet open={editando} onOpenChange={setEditando} distribuidora={d} />
    </>
  );
}
