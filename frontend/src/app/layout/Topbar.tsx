import { Menu, PanelLeft } from "lucide-react";
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";
import { STORE_NAME } from "@/shared/lib/store";

/** Barra superior: abre el menu en telefono y compacta/expande el sidebar en tablet y PC. */
export function Topbar(): ReactElement {
  const { isMobile, toggleSidebar, state } = useSidebar();
  const label = isMobile ? "Abrir menú" : state === "expanded" ? "Compactar menú" : "Expandir menú";
  return (
    <div className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur md:px-6">
      <Button type="button" variant="ghost" size="icon" aria-label={label} onClick={toggleSidebar}>
        {isMobile ? <Menu aria-hidden="true" /> : <PanelLeft aria-hidden="true" />}
      </Button>
      {isMobile && <span className="text-base font-semibold tracking-tight">{STORE_NAME}</span>}
    </div>
  );
}
