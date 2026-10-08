import type { ReactElement } from "react";
import { NavLink, useLocation } from "react-router";
import type { NavGroup, NavItem } from "@/app/nav";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useAlertasStock } from "@/features/stock/api";

function isActivePath(pathname: string, to: string): boolean {
  return pathname === to || pathname.startsWith(`${to}/`);
}

function NavEntry({ item, bajoMinimo }: { item: NavItem; bajoMinimo: number }): ReactElement {
  const { isMobile, setOpenMobile, state } = useSidebar();
  const { pathname } = useLocation();
  const badge = item.alertas === true && bajoMinimo > 0 ? bajoMinimo : null;
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={isActivePath(pathname, item.to)}
        tooltip={item.label}
        className="h-9 text-[0.9375rem] pointer-coarse:h-11"
      >
        <NavLink to={item.to} onClick={() => isMobile && setOpenMobile(false)}>
          <item.icon aria-hidden="true" />
          <span>{item.label}</span>
        </NavLink>
      </SidebarMenuButton>
      {badge !== null && (
        <SidebarMenuBadge
          title={`${badge} ${badge === 1 ? "producto" : "productos"} bajo mínimo`}
          className="top-2! rounded-full bg-warning-soft px-2 font-semibold text-warning pointer-coarse:top-3!"
        >
          {badge}
        </SidebarMenuBadge>
      )}
      {badge !== null && state === "collapsed" && !isMobile && (
        <span aria-hidden="true" className="pointer-events-none absolute top-1.5 right-2 size-2 rounded-full bg-warning" />
      )}
    </SidebarMenuItem>
  );
}

/** Grupos de navegacion ya filtrados por rol. */
export function NavGroupList({ groups }: { groups: NavGroup[] }): ReactElement {
  const { data } = useAlertasStock();
  const bajoMinimo = data?.total_bajo_minimo ?? 0;
  return (
    <>
      {groups.map((group) => (
        <SidebarGroup key={group.label} className="py-1">
          {/* Un grupo de una sola entrada homonima no repite su etiqueta. */}
          {!(group.items.length === 1 && group.items[0]?.label === group.label) && (
            <SidebarGroupLabel className="text-[0.6875rem] font-semibold tracking-wider text-muted-foreground uppercase">
              {group.label}
            </SidebarGroupLabel>
          )}
          <SidebarGroupContent>
            <SidebarMenu>
              {group.items.map((item) => (
                <NavEntry key={item.to} item={item} bajoMinimo={bajoMinimo} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
    </>
  );
}
