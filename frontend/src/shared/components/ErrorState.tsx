import { CircleAlert, RotateCw } from "lucide-react";
import type { ReactElement } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/shared/lib/utils";

interface ErrorStateProps {
  /** Ej.: "No pudimos cargar los clientes". */
  title: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

/** Error de carga entendible con boton "Reintentar" (UX10). */
export function ErrorState({
  title,
  description = "Revisá tu conexión e intentá de nuevo.",
  onRetry,
  className,
}: ErrorStateProps): ReactElement {
  return (
    <Alert variant="destructive" className={cn("items-center", className)}>
      <CircleAlert aria-hidden="true" />
      <AlertTitle className="line-clamp-none">{title}</AlertTitle>
      <AlertDescription>
        <p>{description}</p>
        {onRetry !== undefined && (
          <Button type="button" variant="outline" size="sm" className="mt-2 text-foreground" onClick={onRetry}>
            <RotateCw aria-hidden="true" />
            Reintentar
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}
