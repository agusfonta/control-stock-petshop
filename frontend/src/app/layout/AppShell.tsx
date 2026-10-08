import type { ReactElement } from "react";
import { Outlet } from "react-router";
import { AppSidebar } from "@/app/layout/AppSidebar";
import { Topbar } from "@/app/layout/Topbar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

/** Tablet vertical y menor arrancan en modo iconos; PC, expandido. */
function abrirPorDefecto(): boolean {
  return typeof window === "undefined" || window.innerWidth >= 1024;
}

/** Layout autenticado: sidebar + topbar + contenido sin scroll horizontal de pagina. */
export function AppShell(): ReactElement {
  return (
    <SidebarProvider defaultOpen={abrirPorDefecto()}>
      <a
        href="#contenido"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Saltar al contenido
      </a>
      <AppSidebar />
      <SidebarInset className="min-w-0 overflow-x-clip">
        <Topbar />
        <main
          id="contenido"
          tabIndex={-1}
          className="mx-auto w-full max-w-7xl min-w-0 flex-1 px-4 py-6 outline-none md:px-6 md:py-8"
        >
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
