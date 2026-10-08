import { SearchX } from "lucide-react";
import type { ReactElement } from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/shared/components/EmptyState";

/** 404 amistoso, dentro del shell. */
export function NotFoundPage(): ReactElement {
  return (
    <EmptyState
      icon={SearchX}
      title="No encontramos esta página"
      description="La dirección no existe o fue movida. Volvé al inicio para seguir trabajando."
      action={
        <Button asChild>
          <Link to="/pos">Volver al inicio</Link>
        </Button>
      }
    />
  );
}
