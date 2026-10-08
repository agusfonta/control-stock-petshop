import {
  Boxes,
  CalendarDays,
  ClipboardList,
  type LucideIcon,
  Package,
  PackagePlus,
  Percent,
  Receipt,
  ShoppingCart,
  TrendingUp,
  Truck,
  Users,
} from "lucide-react";
import type { Rol } from "@/shared/api/types";
import { type Permiso, can } from "@/shared/lib/permissions";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  /** Si se define, la entrada solo se muestra a quien tenga el permiso (mismo mapa que las rutas). */
  permiso?: Permiso;
  /** Muestra el contador de productos bajo minimo (`GET /api/stock/alertas`). */
  alertas?: boolean;
}

export interface NavGroup {
  /** Etiqueta del grupo; en modo iconos se oculta. */
  label: string;
  items: NavItem[];
}

/** Navegacion lateral agrupada por area (UX1). */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Vender",
    items: [
      { label: "POS", to: "/pos", icon: ShoppingCart },
      { label: "Ventas", to: "/ventas", icon: Receipt },
    ],
  },
  {
    label: "Inventario",
    items: [
      { label: "Productos", to: "/productos", icon: Package },
      { label: "Stock", to: "/stock", icon: Boxes, alertas: true },
    ],
  },
  {
    label: "Compras",
    items: [
      { label: "Distribuidoras", to: "/distribuidoras", icon: Truck },
      { label: "Pedidos", to: "/compras", icon: ClipboardList },
    ],
  },
  {
    label: "Clientes",
    items: [{ label: "Clientes", to: "/clientes", icon: Users }],
  },
  {
    label: "Reportes",
    items: [
      { label: "Ventas del día", to: "/reportes/ventas-dia", icon: CalendarDays },
      { label: "Reposición", to: "/reportes/reposicion", icon: PackagePlus },
      { label: "Más vendidos", to: "/reportes/mas-vendidos", icon: TrendingUp, permiso: "reportes.completos" },
      { label: "Márgenes", to: "/reportes/margenes", icon: Percent, permiso: "reportes.completos" },
    ],
  },
];

/** Grupos filtrados por el rol; los grupos que quedan vacios se descartan. */
export function navForRole(rol: Rol | null | undefined): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => item.permiso === undefined || can(rol, item.permiso)),
  })).filter((group) => group.items.length > 0);
}
