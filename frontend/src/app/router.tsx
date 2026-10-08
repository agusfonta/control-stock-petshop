import { type ReactElement, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router";
import { RequireAuth } from "@/app/guards/RequireAuth";
import { RequireRole } from "@/app/guards/RequireRole";
import { AppShell } from "@/app/layout/AppShell";
import { LoginPage } from "@/features/auth/LoginPage";
import { useSession } from "@/features/auth/session";
import { ClienteDetallePage } from "@/features/clientes/ClienteDetallePage";
import { ClientesPage } from "@/features/clientes/ClientesPage";
import { ComprasPage } from "@/features/compras/ComprasPage";
import { PedidoDetallePage } from "@/features/compras/PedidoDetallePage";
import { DistribuidoraDetallePage } from "@/features/distribuidoras/DistribuidoraDetallePage";
import { DistribuidorasPage } from "@/features/distribuidoras/DistribuidorasPage";
import { ProductosPage } from "@/features/productos/ProductosPage";
import { StockPage } from "@/features/stock/StockPage";
import { PosPage } from "@/features/pos/PosPage";
import { MargenesPage } from "@/features/reportes/MargenesPage";
import { MasVendidosPage } from "@/features/reportes/MasVendidosPage";
import { ReposicionPage } from "@/features/reportes/ReposicionPage";
import { VentasDiaPage } from "@/features/reportes/VentasDiaPage";
import { VentaDetallePage } from "@/features/ventas/VentaDetallePage";
import { VentasPage } from "@/features/ventas/VentasPage";
import { NotFoundPage } from "@/shared/components/NotFoundPage";
import { PlaceholderPage } from "@/shared/components/PlaceholderPage";

interface PlaceholderRoute {
  path: string;
  title: string;
  description: string;
}

/** Pantallas de B2-B5: placeholders con la ruta, el titulo y el rol definitivos. */
const COMMON_ROUTES: PlaceholderRoute[] = [
];

function placeholder({ path, title, description }: PlaceholderRoute): ReactElement {
  return <Route key={path} path={path} element={<PlaceholderPage title={title} description={description} />} />;
}

/** Restaura la sesion una sola vez al montar (pista + refresh + me). */
function useSessionBootstrap(): void {
  const status = useSession((s) => s.status);
  const init = useSession((s) => s.init);
  useEffect(() => {
    if (status === "loading") void init();
  }, [status, init]);
}

/** Arbol de rutas de la app (sin Router: lo provee main.tsx o el render de tests). */
export function AppRoutes(): ReactElement {
  useSessionBootstrap();
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/pos" replace />} />
          <Route path="pos" element={<PosPage />} />
          <Route path="ventas" element={<VentasPage />} />
          <Route path="ventas/:id" element={<VentaDetallePage />} />
          <Route path="productos" element={<ProductosPage />} />
          <Route path="stock" element={<StockPage />} />
          <Route path="clientes" element={<ClientesPage />} />
          <Route path="clientes/:id" element={<ClienteDetallePage />} />
          <Route path="distribuidoras" element={<DistribuidorasPage />} />
          <Route path="distribuidoras/:id" element={<DistribuidoraDetallePage />} />
          <Route path="compras" element={<ComprasPage />} />
          <Route path="compras/pedidos/:id" element={<PedidoDetallePage />} />
          {COMMON_ROUTES.map(placeholder)}
          <Route path="reportes" element={<Navigate to="/reportes/ventas-dia" replace />} />
          <Route path="reportes/ventas-dia" element={<VentasDiaPage />} />
          <Route path="reportes/reposicion" element={<ReposicionPage />} />
          <Route element={<RequireRole permiso="reportes.completos" />}>
            <Route path="reportes/mas-vendidos" element={<MasVendidosPage />} />
            <Route path="reportes/margenes" element={<MargenesPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
