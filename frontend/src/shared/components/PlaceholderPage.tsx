import { Construction } from "lucide-react";
import type { ReactElement } from "react";
import { EmptyState } from "@/shared/components/EmptyState";
import { PageHeader } from "@/shared/components/PageHeader";

interface PlaceholderPageProps {
  title: string;
  description?: string;
}

/** Pantalla provisoria de las tandas B2-B5: se reemplaza al implementar cada una. */
export function PlaceholderPage({ title, description }: PlaceholderPageProps): ReactElement {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={Construction}
        title="Próximamente"
        description="Esta pantalla se está preparando y va a estar disponible en breve."
      />
    </>
  );
}
