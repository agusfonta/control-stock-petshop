import { Wallet } from "lucide-react";
import type { ReactElement } from "react";
import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCuenta, useDistribuidorasIndex } from "@/features/distribuidoras/api";
import type { Distribuidora } from "@/shared/api/types";
import { EmptyState } from "@/shared/components/EmptyState";
import { ErrorState } from "@/shared/components/ErrorState";
import { MoneyText } from "@/shared/components/MoneyText";
import { toCents } from "@/shared/lib/money";
import { cn } from "@/shared/lib/utils";

function Cifra({ etiqueta, children }: { etiqueta: string; children: ReactElement }): ReactElement {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{etiqueta}</dt>
      <dd className="mt-0.5 text-base font-medium">{children}</dd>
    </div>
  );
}

/** Cuenta de una distribuidora: recibido - pagado = saldo; el saldo deudor se resalta. */
function CuentaCard({ distribuidora, onPagar }: { distribuidora: Distribuidora; onPagar: (id: string) => void }): ReactElement {
  const cuenta = useCuenta(distribuidora.id, true);
  const saldo = cuenta.data === undefined ? 0 : toCents(cuenta.data.saldo);
  const deudor = saldo > 0;
  return (
    <Card className={cn("gap-0 py-0 shadow-none", deudor && "border-destructive/40")}>
      <CardContent className="space-y-3 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link
            to={`/distribuidoras/${distribuidora.id}`}
            className="font-semibold underline-offset-4 hover:underline"
          >
            {distribuidora.nombre}
          </Link>
          {deudor && (
            <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-destructive">
              Con deuda
            </Badge>
          )}
        </div>
        {cuenta.isError ? (
          <ErrorState title="No pudimos cargar la cuenta" onRetry={() => void cuenta.refetch()} />
        ) : cuenta.data === undefined ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <dl className="grid grid-cols-3 gap-3">
            <Cifra etiqueta="Recibido">
              <MoneyText value={cuenta.data.total_recibido} />
            </Cifra>
            <Cifra etiqueta="Pagado">
              <MoneyText value={cuenta.data.total_pagado} />
            </Cifra>
            <Cifra etiqueta={deudor ? "Saldo deudor" : "Saldo"}>
              <MoneyText value={cuenta.data.saldo} className={cn("font-semibold", deudor && "text-destructive")} />
            </Cifra>
          </dl>
        )}
        <Button type="button" variant="outline" size="sm" onClick={() => onPagar(distribuidora.id)}>
          <Wallet aria-hidden="true" /> Registrar pago
        </Button>
      </CardContent>
    </Card>
  );
}

interface CuentasTabProps {
  onPagar: (distribuidoraId: string) => void;
}

/** Cuenta corriente por distribuidora (solo dueña). */
export function CuentasTab({ onPagar }: CuentasTabProps): ReactElement {
  const distribuidoras = useDistribuidorasIndex();
  if (distribuidoras.isError) {
    return <ErrorState title="No pudimos cargar las distribuidoras" onRetry={() => void distribuidoras.refetch()} />;
  }
  if (distribuidoras.data === undefined) {
    return <Skeleton className="h-40 w-full rounded-xl" />;
  }
  const lista = [...distribuidoras.data.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  if (lista.length === 0) {
    return (
      <EmptyState
        icon={Wallet}
        title="No hay distribuidoras"
        description="Cargá una distribuidora para llevar su cuenta."
      />
    );
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {lista.map((d) => (
        <CuentaCard key={d.id} distribuidora={d} onPagar={onPagar} />
      ))}
    </div>
  );
}
