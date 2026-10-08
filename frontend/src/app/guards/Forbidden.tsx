import { ShieldAlert } from "lucide-react";
import type { ReactElement } from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/shared/components/EmptyState";

/** Pantalla "Sin permiso" para rutas exclusivas de dueña (spec frontend-shell). */
export function Forbidden(): ReactElement {
  return (
    <EmptyState
      icon={ShieldAlert}
      title="Sin permiso"
      description="Tu usuario no tiene acceso a esta pantalla. Si lo necesitás, pedíselo a la dueña."
      action={
        <Button asChild>
          <Link to="/pos">Volver al inicio</Link>
        </Button>
      }
    />
  );
}
