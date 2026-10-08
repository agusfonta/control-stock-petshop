import { LogOut } from "lucide-react";
import type { ReactElement } from "react";
import { useNavigate } from "react-router";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from "@/components/ui/sidebar";
import { useSession } from "@/features/auth/session";
import { ROL_LABEL } from "@/shared/lib/permissions";

/** Usuario + rol (se compacta a la inicial en modo iconos) y "Cerrar sesion". */
export function UserFooter(): ReactElement | null {
  const user = useSession((s) => s.user);
  const logout = useSession((s) => s.logout);
  const navigate = useNavigate();
  const { isMobile, setOpenMobile } = useSidebar();
  if (user === null) return null;

  function cerrarSesion(): void {
    if (isMobile) setOpenMobile(false);
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-3 rounded-lg px-2 py-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
        <span
          aria-hidden="true"
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-semibold text-accent-foreground uppercase"
        >
          {user.email.charAt(0)}
        </span>
        <div className="min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
          <p className="truncate text-sm font-medium" title={user.email}>
            {user.email}
          </p>
          <p className="text-xs text-muted-foreground">{ROL_LABEL[user.rol]}</p>
        </div>
      </div>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            type="button"
            tooltip="Cerrar sesión"
            aria-label="Cerrar sesión"
            className="h-9 text-muted-foreground pointer-coarse:h-11"
            onClick={cerrarSesion}
          >
            <LogOut aria-hidden="true" />
            <span>Cerrar sesión</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </div>
  );
}
