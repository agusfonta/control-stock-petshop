import type { LucideIcon } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { cn } from "@/shared/lib/utils";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  /** Accion principal permitida por rol (el llamador decide si se muestra). */
  action?: ReactNode;
  className?: string;
}

/** Estado vacio con explicacion y, si el rol puede, la accion principal (UX10). */
export function EmptyState({ title, description, icon: Icon, action, className }: EmptyStateProps): ReactElement {
  return (
    <Empty className={cn("border", className)}>
      <EmptyHeader>
        {Icon !== undefined && (
          <EmptyMedia variant="icon">
            <Icon aria-hidden="true" />
          </EmptyMedia>
        )}
        <EmptyTitle>{title}</EmptyTitle>
        {description !== undefined && <EmptyDescription>{description}</EmptyDescription>}
      </EmptyHeader>
      {action !== undefined && <EmptyContent>{action}</EmptyContent>}
    </Empty>
  );
}
