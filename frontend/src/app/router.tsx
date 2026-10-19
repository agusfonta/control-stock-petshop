import { type ReactElement, Suspense, lazy, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router";
import { RedirectPreservandoQuery } from "@/app/RedirectPreservandoQuery";
import { RequireAuth } from "@/app/guards/RequireAuth";
import { RequireRole } from "@/app/guards/RequireRole";
import { AppShell } from "@/app/layout/AppShell";
import { LoginPage } from "@/features/auth/LoginPage";
import { useSession } from "@/features/auth/session";
import { ClienteDetallePage } from "@/features/clientes/ClienteDetallePage";
import { ClientesPage } from "@/features/clientes/ClientesPage";
import { PosPage } from "@/features/pos/PosPage";
import { VentaDetallePage } from "@/features/ventas/VentaDetallePage";
import { VentasPage } from "@/features/ventas/VentasPage";
import { NotFoundPage } from "@/shared/components/NotFoundPage";
import { Spinner } from "@/components/ui/spinner";

// Paginas no criticas (login/POS/ventas quedan eager): carga diferida por ruta.
const lazyPage = (
  loader: () => Promise<Record<string, unknown>>,
  name: string,
) =>
  lazy(async () => {
    const mod = await loader();
    return { default: mod[name] as () => ReactElement };
  });

const ComprasPage = lazyPage(
  () => import("@/features/compras/ComprasPage"),
  "ComprasPage",
);
const PedidoDetallePage = lazyPage(
  () => import("@/features/compras/PedidoDetallePage"),
  "PedidoDetallePage",
);
const DistribuidoraDetallePage = lazyPage(
  () => import("@/features/distribuidoras/DistribuidoraDetallePage"),
  "DistribuidoraDetallePage",
);
const DistribuidorasPage = lazyPage(
  () => import("@/features/distribuidoras/DistribuidorasPage"),
  "DistribuidorasPage",
);
const ProductosPage = lazyPage(
  () => import("@/features/productos/ProductosPage"),
  "ProductosPage",
);
const MargenesPage = lazyPage(
  () => import("@/features/reportes/MargenesPage"),
  "MargenesPage",
);
const MasVendidosPage = lazyPage(
  () => import("@/features/reportes/MasVendidosPage"),
  "MasVendidosPage",
);
const ReposicionPage = lazyPage(
  () => import("@/features/reportes/ReposicionPage"),
  "ReposicionPage",
);
const VentasDiaPage = lazyPage(
  () => import("@/features/reportes/VentasDiaPage"),
  "VentasDiaPage",
);

function PageFallback(): ReactElement {
  return (
    <div className="flex justify-center p-8">
      <Spinner className="size-6" />
    </div>
  );
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
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/pos" replace />} />
            <Route path="pos" element={<PosPage />} />
            <Route path="ventas" element={<VentasPage />} />
            <Route path="ventas/:id" element={<VentaDetallePage />} />
            <Route path="productos" element={<ProductosPage />} />
            <Route path="stock" element={<RedirectPreservandoQuery to="/productos" />} />
            <Route path="clientes" element={<ClientesPage />} />
            <Route path="clientes/:id" element={<ClienteDetallePage />} />
            <Route path="distribuidoras" element={<DistribuidorasPage />} />
            <Route
              path="distribuidoras/:id"
              element={<DistribuidoraDetallePage />}
            />
            <Route path="compras" element={<ComprasPage />} />
            <Route path="compras/pedidos/:id" element={<PedidoDetallePage />} />
            <Route
              path="reportes"
              element={<Navigate to="/reportes/ventas-dia" replace />}
            />
            <Route path="reportes/ventas-dia" element={<VentasDiaPage />} />
            <Route path="reportes/reposicion" element={<ReposicionPage />} />
            <Route element={<RequireRole permiso="reportes.completos" />}>
              <Route
                path="reportes/mas-vendidos"
                element={<MasVendidosPage />}
              />
              <Route path="reportes/margenes" element={<MargenesPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
