import type { ReactElement } from "react";
import { Link } from "react-router";
import { NavGroupList } from "@/app/layout/NavGroupList";
import { UserFooter } from "@/app/layout/UserFooter";
import { navForRole } from "@/app/nav";
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarSeparator } from "@/components/ui/sidebar";
import { useSession } from "@/features/auth/session";
import { STORE_NAME } from "@/shared/lib/store";

/** Marca: logo recortado (pata + carrito) que sirve tanto expandido como en modo iconos. */
function Brand(): ReactElement {
  return (
    <Link
      to="/pos"
      aria-label={`${STORE_NAME}: ir al inicio`}
      className="flex items-center gap-3 rounded-lg p-1 group-data-[collapsible=icon]:justify-center"
    >
      <span
        aria-hidden="true"
        className="size-10 shrink-0 rounded-lg bg-blush bg-no-repeat group-data-[collapsible=icon]:size-8"
        style={{ backgroundImage: "url(/logo.png)", backgroundSize: "210%", backgroundPosition: "58% 12%" }}
      />
      <span className="leading-tight group-data-[collapsible=icon]:hidden">
        <span className="block text-base font-semibold tracking-tight">{STORE_NAME}</span>
        <span className="block text-xs text-muted-foreground">Control de stock</span>
      </span>
    </Link>
  );
}

export function AppSidebar(): ReactElement {
  const rol = useSession((s) => s.user?.rol);
  return (
    <Sidebar collapsible="icon" aria-label="Navegación principal">
      <SidebarHeader className="bg-blush/60 p-3 group-data-[collapsible=icon]:p-2">
        <Brand />
      </SidebarHeader>
      <SidebarSeparator className="mx-0" />
      <SidebarContent>
        <NavGroupList groups={navForRole(rol)} />
      </SidebarContent>
      <SidebarFooter className="border-t p-2">
        <UserFooter />
      </SidebarFooter>
    </Sidebar>
  );
}
