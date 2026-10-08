import { Banknote, ClipboardList } from "lucide-react";
import type { ReactElement } from "react";
import { useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CuentasTab } from "@/features/compras/CuentasTab";
import { PagoSheet } from "@/features/compras/PagoSheet";
import { PagosTab } from "@/features/compras/PagosTab";
import { PedidoSheet } from "@/features/compras/PedidoSheet";
import { PedidosTab } from "@/features/compras/PedidosTab";
import { PageHeader } from "@/shared/components/PageHeader";
import { useCan } from "@/shared/lib/permissions";

type Pestana = "pedidos" | "pagos" | "cuentas";

function esPestana(valor: string | null): valor is Pestana {
  return valor === "pedidos" || valor === "pagos" || valor === "cuentas";
}

/**
 * Compras: pedidos (ambos roles) y, solo con `compras.pagos`, pagos y cuentas.
 * El estado de pestana y de los formularios vive en la URL (`?tab=`, `?nuevo=1&distribuidora=&producto=`),
 * asi Reposicion y las fichas de distribuidora pueden abrir el alta ya preparada.
 */
export function ComprasPage(): ReactElement {
  const puedeVerPagos = useCan("compras.pagos");
  const [params, setParams] = useSearchParams();
  const solicitada = params.get("tab");
  const tab: Pestana = esPestana(solicitada) && (puedeVerPagos || solicitada === "pedidos") ? solicitada : "pedidos";
  const nuevo = params.get("nuevo") === "1";
  const distribuidoraInicial = params.get("distribuidora") ?? "";
  const productoInicial = params.get("producto") ?? "";

  function abrirNuevo(): void {
    setParams(new URLSearchParams({ tab, nuevo: "1" }));
  }

  /** Cierra el formulario limpiando `nuevo`, `distribuidora` y `producto`. */
  function cerrarNuevo(): void {
    setParams(new URLSearchParams({ tab }), { replace: true });
  }

  function cambiarPestana(valor: string): void {
    if (esPestana(valor)) setParams(new URLSearchParams({ tab: valor }));
  }

  const accion =
    tab === "pedidos" ? (
      <Button type="button" onClick={abrirNuevo}>
        <ClipboardList aria-hidden="true" /> Nuevo pedido
      </Button>
    ) : tab === "pagos" ? (
      <Button type="button" onClick={abrirNuevo}>
        <Banknote aria-hidden="true" /> Registrar pago
      </Button>
    ) : undefined;

  return (
    <>
      <PageHeader
        title="Compras"
        description={
          puedeVerPagos
            ? "Pedidos a distribuidoras, pagos y cuentas."
            : "Pedidos a distribuidoras: armalos y recibilos cuando llega la mercadería."
        }
        actions={accion}
      />
      <Tabs value={tab} onValueChange={cambiarPestana} className="gap-4">
        <TabsList>
          <TabsTrigger value="pedidos">Pedidos</TabsTrigger>
          {puedeVerPagos && <TabsTrigger value="pagos">Pagos</TabsTrigger>}
          {puedeVerPagos && <TabsTrigger value="cuentas">Cuentas</TabsTrigger>}
        </TabsList>
        <TabsContent value="pedidos">
          <PedidosTab onNuevo={abrirNuevo} />
        </TabsContent>
        {puedeVerPagos && (
          <TabsContent value="pagos">
            <PagosTab onRegistrar={abrirNuevo} />
          </TabsContent>
        )}
        {puedeVerPagos && (
          <TabsContent value="cuentas">
            <CuentasTab onPagar={(id) => setParams(new URLSearchParams({ tab: "pagos", nuevo: "1", distribuidora: id }))} />
          </TabsContent>
        )}
      </Tabs>
      <PedidoSheet
        open={nuevo && tab === "pedidos"}
        onOpenChange={(open) => {
          if (!open) cerrarNuevo();
        }}
        distribuidoraInicial={distribuidoraInicial}
        productoInicial={productoInicial}
      />
      {puedeVerPagos && (
        <PagoSheet
          open={nuevo && tab === "pagos"}
          onOpenChange={(open) => {
            if (!open) cerrarNuevo();
          }}
          distribuidoraInicial={distribuidoraInicial}
        />
      )}
    </>
  );
}
